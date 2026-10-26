[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [Parameter(Mandatory = $true)][string]$ExpectedSha,
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$RunAttempt
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$actualSha = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualSha -cne $ExpectedSha) { throw "Checkout SHA mismatch. expected=$ExpectedSha actual=$actualSha" }
if ($ExpectedSha -notmatch '^[0-9a-f]{40}$') { throw 'ExpectedSha must be a full 40-character Git commit SHA.' }
$configRelativePaths = @(
    'current/recon-back-box/config/recon-back-box.config.json',
    'current/recon-back-box/config/artifact-intake.config.json',
    'current/recon-back-box/config/website-learning.config.json',
    'current/recon-back-box/config/recon-policy.config.json'
)
$configs = @()
foreach ($relativePath in $configRelativePaths) {
    $sourcePath = Join-Path $repo ($relativePath.Replace('/', [IO.Path]::DirectorySeparatorChar))
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { throw "Required config missing: $relativePath" }
    try { $payload = Get-Content -LiteralPath $sourcePath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "Invalid JSON config $relativePath : $($_.Exception.Message)" }
    if ([int]$payload.schema_version -ne 1 -or [string]::IsNullOrWhiteSpace([string]$payload.config_id)) { throw "Config schema or config_id invalid: $relativePath" }
    if ($relativePath -like '*website-learning.config.json') {
        if ($payload.discovery.max_depth -lt 0 -or $payload.discovery.max_pages_per_run -lt 1 -or $payload.discovery.max_requests_per_minute -lt 1) { throw 'Website learning limits are invalid.' }
        if ($payload.discovery.allowed_domains.Count -eq 0) { Write-Output 'LEARNING_SCOPE=EMPTY_ALLOWLIST; crawling must remain inactive until domains are explicitly approved.' }
    }
    $destinationPath = Join-Path $OutputRoot ($relativePath.Replace('/', [IO.Path]::DirectorySeparatorChar))
    New-Item -ItemType Directory -Path (Split-Path -Parent $destinationPath) -Force | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath
    $hash = (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $configs += [ordered]@{source_path=$relativePath;snapshot_path=$relativePath;sha256=$hash;bytes=(Get-Item -LiteralPath $destinationPath).Length;schema_version=[int]$payload.schema_version;config_id=[string]$payload.config_id}
}
$manifest = [ordered]@{schema='RECON_BACK_BOX_CONFIG_SNAPSHOT_V1';source_repository=$env:GITHUB_REPOSITORY;source_sha=$actualSha;workflow_run_id=$RunId;workflow_run_attempt=$RunAttempt;captured_at_utc=[DateTime]::UtcNow.ToString('o');authority='FINAL_GATE';snapshot_only=$true;source_configs_modified_or_deleted=$false;configs=$configs}
$manifestPath = Join-Path $OutputRoot 'recon-back-box-manifest.json'
$manifestJson = ConvertTo-Json -InputObject $manifest -Depth 12
[IO.File]::WriteAllText($manifestPath, $manifestJson + [char]10, (New-Object System.Text.UTF8Encoding($false)))
Write-Output 'RECON_BACK_BOX_CONFIG_SNAPSHOT=PASS'
Write-Output "SOURCE_SHA=$actualSha"
Write-Output "CONFIG_COUNT=$($configs.Count)"
Write-Output "MANIFEST=$manifestPath"
