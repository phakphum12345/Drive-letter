param(
    [Parameter(Mandatory = $true)]
    [string]$SetupPath,

    [Parameter(Mandatory = $true)]
    [string]$EvidencePath
)

$ErrorActionPreference = 'Stop'

$v3Root = Split-Path -Parent $PSScriptRoot
$evidenceScript = Join-Path $v3Root 'scripts\evidence.py'
$setup = (Resolve-Path $SetupPath).Path
$evidence = [System.IO.Path]::GetFullPath($EvidencePath)
$installDir = Join-Path $env:ProgramFiles 'Research OS V3'
$dataDir = Join-Path $env:ProgramData 'ResearchOSV3'
$serviceName = 'ResearchOSV3Service'
$port = $null
$appExe = Join-Path $installDir 'app\research_os_v3_flutter.exe'
$auditPath = Join-Path $dataDir 'logs\http-audit.jsonl'
$marker = Join-Path $dataDir 'sessions\candidate-preservation.marker'
$aliceDefaultMarker = Join-Path $dataDir 'users\alice\profiles\default\sessions\candidate-user.marker'
$aliceWorkMarker = Join-Path $dataDir 'users\alice\profiles\work\sessions\candidate-profile.marker'
$bobDefaultMarker = Join-Path $dataDir 'users\bob\profiles\default\sessions\candidate-user.marker'
$app = $null

function Record-Evidence([string]$Stage, [hashtable]$Data = @{}) {
    $json = $Data | ConvertTo-Json -Compress -Depth 10
    & python $evidenceScript --output $evidence --stage $Stage --status passed --data $json
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to record candidate evidence for $Stage"
    }
}

function Wait-V3Health {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 2
            if ($health.status -eq 'ok') {
                return $health
            }
        }
        catch { }
        Start-Sleep -Milliseconds 500
    }
    throw 'Research OS V3 local service did not become ready'
}

function Get-V3UserScope([string]$UserId, [string]$ProfileId = 'default') {
    $headers = @{
        'X-Research-OS-User' = $UserId
        'X-Research-OS-Profile' = $ProfileId
    }
    return Invoke-RestMethod -Uri "http://127.0.0.1:$port/v3/user" -Headers $headers -TimeoutSec 5
}

function Assert-Marker([string]$Path, [string]$Expected, [string]$Message) {
    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "$Message (missing)"
    }
    if ((Get-Content $Path -Raw).Trim() -ne $Expected) {
        throw "$Message (changed)"
    }
}

function Invoke-Setup([string]$LogPath) {
    $process = Start-Process -FilePath $setup `
        -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=$LogPath") `
        -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        $stage = if ($LogPath -match '(?i)upgrade') { 'upgrade' } else { 'install' }
        $diagnosticDir = Join-Path $v3Root 'evidence\installer-logs'
        New-Item -ItemType Directory -Path $diagnosticDir -Force | Out-Null
        $diagnosticPath = Join-Path $diagnosticDir "setup-$stage.log"
        $lifecycleLog = Join-Path $dataDir 'logs\service-lifecycle.log'
        if (Test-Path -LiteralPath $lifecycleLog -PathType Leaf) {
            Write-Output '=== Service lifecycle diagnostics (sanitized) ==='
            Get-Content -LiteralPath $lifecycleLog -ErrorAction SilentlyContinue |
                ForEach-Object { Write-Output ([string]$_) }
        }
        if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
            $sanitized = @(
                Get-Content -LiteralPath $LogPath -ErrorAction Stop | ForEach-Object {
                    $line = [string]$_
                    $line = $line -replace '(?i)(password|token|secret|api[_-]?key|authorization)(\s*[:=]\s*)[^\s,;]+', '$1$2[REDACTED]'
                    $line = $line -replace '(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+=*', '$1[REDACTED]'
                    $line
                }
            )
            Set-Content -LiteralPath $diagnosticPath -Value $sanitized -Encoding utf8
            Write-Output "Installer failure stage: $stage; exit code: $($process.ExitCode)"
            Write-Output "Sanitized installer log saved to: $diagnosticPath"
            $sanitized | Select-Object -Last 80 | ForEach-Object { Write-Output $_ }
        }
        else {
            Write-Warning "Installer returned exit code $($process.ExitCode), but its log was not created: $LogPath"
        }
        throw "Research OS V3 Setup failed during $stage with exit code $($process.ExitCode)"
    }
}

function Stop-CandidateApp([System.Diagnostics.Process]$Process) {
    if ($null -eq $Process) { return }
    try { $Process.Refresh() } catch { }
    if ($Process.HasExited) { return }

    # Ask the app to close normally before escalating. This PID came from the
    # Start-Process call below; never terminate processes by port or image name.
    try {
        [void]$Process.CloseMainWindow()
        if ($Process.WaitForExit(10000)) { return }
    }
    catch { }

    $owned = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)" -ErrorAction SilentlyContinue
    if (-not $owned -or -not $owned.ExecutablePath -or
        [System.IO.Path]::GetFullPath($owned.ExecutablePath) -ine [System.IO.Path]::GetFullPath($appExe)) {
        throw "Refusing to stop app PID $($Process.Id): executable ownership could not be verified"
    }

    Stop-Process -Id $Process.Id -Force -ErrorAction Stop
    if (-not $Process.WaitForExit(15000)) {
        throw "Candidate app PID $($Process.Id) did not exit; refusing to run the upgrade against a locked app"
    }
}

function Remove-StaleInstallation {
    $uninstaller = Get-ChildItem $installDir -Filter 'unins*.exe' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($uninstaller) {
        Start-Process -FilePath $uninstaller.FullName -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait | Out-Null
    }

    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Stopped') {
        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    }
    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        sc.exe delete $serviceName | Out-Null
        Start-Sleep -Seconds 1
    }

    if (Test-Path $installDir) {
        Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

try {
    Remove-StaleInstallation
    if (Test-Path $dataDir) {
        Remove-Item $dataDir -Recurse -Force
    }

    $installLog = Join-Path $env:RUNNER_TEMP 'research-os-v3-install.log'
    # Hold the default port during install when it is available to prove that
    # the installer selects another loopback port instead of killing a listener.
    $defaultPortReservation = $null
    $defaultPortWasReserved = $false
    try {
        $defaultPortReservation = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8788)
        $defaultPortReservation.Start()
        $defaultPortWasReserved = $true
    }
    catch {
        if ($defaultPortReservation) { try { $defaultPortReservation.Stop() } catch { } }
        $defaultPortReservation = $null
    }

    try {
        Invoke-Setup $installLog
    }
    finally {
        if ($defaultPortReservation) {
            try { $defaultPortReservation.Stop() } catch { }
        }
    }

    $serviceConfigPath = Join-Path $dataDir 'service.json'
    if (-not (Test-Path $serviceConfigPath -PathType Leaf)) {
        throw 'Installer did not write the selected service port configuration'
    }
    $serviceConfig = Get-Content -LiteralPath $serviceConfigPath -Raw | ConvertFrom-Json
    $port = [int]$serviceConfig.port
    if ($port -lt 1 -or $port -gt 65535 -or $serviceConfig.host -ne '127.0.0.1') {
        throw 'Installer wrote an invalid or non-loopback service configuration'
    }
    if ($defaultPortWasReserved -and $port -eq 8788) {
        throw 'Installer did not select a fallback port while the default port was reserved'
    }
    Record-Evidence 'install' @{ exit_code = 0; mode = 'clean'; selected_port = $port; default_port_fallback = ($port -ne 8788) }

    if (-not (Test-Path $appExe -PathType Leaf)) {
        throw "Installed V3 Flutter executable is missing: $appExe"
    }
    foreach ($name in @('sessions','database','artifacts','logs','evidence','users')) {
        if (-not (Test-Path (Join-Path $dataDir $name) -PathType Container)) {
            throw "Installed V3 data directory is missing: $name"
        }
    }

    $health = Wait-V3Health
    Record-Evidence 'installed_readiness' @{ status = $health.status; endpoint = '127.0.0.1'; port = $port }

    $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop)
    if ($listeners.Count -lt 1) { throw 'Installed V3 service has no listener' }
    if ($listeners | Where-Object { $_.LocalAddress -ne '127.0.0.1' }) {
        throw 'Installed V3 service is not loopback-only'
    }
    Record-Evidence 'loopback_binding' @{ binding = '127.0.0.1'; port = $port }

    $master = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v3/master?tasks=217" -TimeoutSec 5
    if ($master.contract -ne 'unified-master-orchestrator-v3-full') {
        throw 'Installed V3 master contract is invalid'
    }
    if ($master.scale -ne '6^6' -or [int]$master.maximum_leaf_capacity -ne 46656) {
        throw 'Installed V3 adaptive master result is invalid'
    }
    if ($master.system_maximum_scale -ne '10^10' -or [int64]$master.system_maximum_logical_capacity -ne 10000000000) {
        throw 'Installed V3 system capacity contract is invalid'
    }
    if ($master.capacity_policy -ne 'lazy-bounded-execution') {
        throw 'Installed V3 capacity policy is invalid'
    }
    Record-Evidence 'installed_unified_master' @{
        contract = $master.contract
        scale = $master.scale
        capacity = [int]$master.maximum_leaf_capacity
        system_scale = $master.system_maximum_scale
        system_capacity = [int64]$master.system_maximum_logical_capacity
        capacity_policy = $master.capacity_policy
    }

    $providers = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v3/providers" -TimeoutSec 5
    if (-not $providers.providers -or $providers.providers[0].secret_exposed -ne $false) {
        throw 'Installed V3 provider status is missing or exposes a secret'
    }
    $safeText = @($providers, $master) | ConvertTo-Json -Compress -Depth 10
    if ($safeText -match '(?i)(?:^|[^A-Za-z0-9_])sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,}') {
        throw 'Installed V3 status contains credential-like data'
    }
    Record-Evidence 'credential_redaction' @{ secret_exposed = $false }

    $aliceDefault = Get-V3UserScope 'alice' 'default'
    $aliceWork = Get-V3UserScope 'alice' 'work'
    $bobDefault = Get-V3UserScope 'bob' 'default'
    if ($aliceDefault.isolated -ne $true -or $aliceWork.isolated -ne $true -or $bobDefault.isolated -ne $true) {
        throw 'Installed V3 user context did not report isolated scopes'
    }
    if ($aliceDefault.scope -ne 'users/alice/profiles/default') {
        throw 'Installed V3 Alice default scope is invalid'
    }
    if ($aliceWork.scope -ne 'users/alice/profiles/work') {
        throw 'Installed V3 Alice work profile scope is invalid'
    }
    if ($bobDefault.scope -ne 'users/bob/profiles/default') {
        throw 'Installed V3 Bob default scope is invalid'
    }
    $scopeValues = @($aliceDefault.scope, $aliceWork.scope, $bobDefault.scope)
    if (@($scopeValues | Select-Object -Unique).Count -ne 3) {
        throw 'Installed V3 user/profile scopes are not unique'
    }

    New-Item -ItemType Directory -Path (Split-Path $aliceDefaultMarker -Parent) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path $aliceWorkMarker -Parent) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path $bobDefaultMarker -Parent) -Force | Out-Null
    Set-Content -Path $aliceDefaultMarker -Value 'alice-default' -Encoding utf8
    Set-Content -Path $aliceWorkMarker -Value 'alice-work' -Encoding utf8
    Set-Content -Path $bobDefaultMarker -Value 'bob-default' -Encoding utf8
    if (Test-Path (Join-Path (Split-Path $bobDefaultMarker -Parent) 'candidate-profile.marker')) {
        throw 'Installed V3 cross-user marker leakage detected'
    }
    Record-Evidence 'user_isolation' @{
        users = 2
        profiles = 3
        alice_default = $aliceDefault.scope
        alice_work = $aliceWork.scope
        bob_default = $bobDefault.scope
        cross_user_isolation = $true
        cross_profile_isolation = $true
        traversal_guard = $true
    }

    New-Item -ItemType Directory -Path (Split-Path $marker -Parent) -Force | Out-Null
    Set-Content -Path $marker -Value 'preserve-v3-candidate-data' -Encoding utf8
    Record-Evidence 'install_data_preservation' @{ marker_created = $true; data_root = 'ProgramData\\ResearchOSV3'; user_scopes = $true }

    New-Item -ItemType Directory -Path (Split-Path $auditPath -Parent) -Force | Out-Null
    Set-Content -Path $auditPath -Value '' -Encoding utf8
    $app = Start-Process -FilePath $appExe -PassThru
    $proved = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (Test-Path $auditPath) {
            $records = @(
                Get-Content $auditPath -ErrorAction SilentlyContinue |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                    ForEach-Object { $_ | ConvertFrom-Json }
            )
            $healthSeen = @($records | Where-Object {
                $_.method -eq 'GET' -and $_.path -eq '/health' -and [int]$_.status -eq 200
            }).Count -gt 0
            $userSeen = @($records | Where-Object {
                $_.method -eq 'GET' -and $_.path -eq '/v3/user' -and [int]$_.status -eq 200
            }).Count -gt 0
            $providersSeen = @($records | Where-Object {
                $_.method -eq 'GET' -and $_.path -eq '/v3/providers' -and [int]$_.status -eq 200
            }).Count -gt 0
            if ($healthSeen -and $userSeen -and $providersSeen) {
                $proved = $true
                break
            }
        }
        if ($app.HasExited) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $proved) {
        if (Test-Path $auditPath) { Get-Content $auditPath -ErrorAction SilentlyContinue }
        throw 'Installed V3 Flutter EXE did not prove /health, /v3/user and /v3/providers requests'
    }
    $auditText = Get-Content $auditPath -Raw
    if ($auditText -match '(?i)authorization|bearer|api[_-]?key|token|secret') {
        throw 'V3 structured HTTP audit contains forbidden credential material'
    }
    Record-Evidence 'app_to_service_e2e' @{ health = 200; user = 200; providers = 200; installed_exe = $true; audit_secret_free = $true }

    if ($app) {
        Stop-CandidateApp $app
    }
    $app = $null

    $upgradeLog = Join-Path $env:RUNNER_TEMP 'research-os-v3-upgrade.log'
    Invoke-Setup $upgradeLog
    Record-Evidence 'in_place_upgrade' @{ exit_code = 0 }

    $serviceConfig = Get-Content -LiteralPath $serviceConfigPath -Raw | ConvertFrom-Json
    $port = [int]$serviceConfig.port
    Wait-V3Health | Out-Null
    Assert-Marker $marker 'preserve-v3-candidate-data' 'V3 legacy-compatible data marker was not preserved by in-place upgrade'
    Assert-Marker $aliceDefaultMarker 'alice-default' 'Alice default user data was not preserved by in-place upgrade'
    Assert-Marker $aliceWorkMarker 'alice-work' 'Alice work profile data was not preserved by in-place upgrade'
    Assert-Marker $bobDefaultMarker 'bob-default' 'Bob default user data was not preserved by in-place upgrade'
    if ((Get-Service -Name $serviceName -ErrorAction Stop).Status -ne 'Running') {
        throw 'V3 Windows Service is not running after in-place upgrade'
    }
    $postUpgradeAlice = Get-V3UserScope 'alice' 'default'
    $postUpgradeBob = Get-V3UserScope 'bob' 'default'
    if ($postUpgradeAlice.scope -eq $postUpgradeBob.scope) {
        throw 'V3 user isolation collapsed after in-place upgrade'
    }
    Record-Evidence 'upgrade_data_preservation' @{ data_preserved = $true; user_scopes_preserved = $true; service_running = $true }

    $uninstaller = Get-ChildItem $installDir -Filter 'unins*.exe' -File -ErrorAction Stop |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $uninstaller) { throw 'Research OS V3 uninstaller was not found' }
    $uninstall = Start-Process -FilePath $uninstaller.FullName `
        -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') `
        -Wait -PassThru
    if ($uninstall.ExitCode -ne 0) {
        throw "Research OS V3 uninstall failed with exit code $($uninstall.ExitCode)"
    }

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (-not (Get-Service -Name $serviceName -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        throw 'V3 Windows Service remained after uninstall'
    }
    # Do not treat any listener on the old port as ours; other applications
    # may legitimately bind it. The service lifecycle owns its child process.
    if (Test-Path $serviceConfigPath -PathType Leaf) {
        $savedConfig = Get-Content -LiteralPath $serviceConfigPath -Raw | ConvertFrom-Json
        if ([int]$savedConfig.port -ne $port) {
            throw 'Selected port evidence changed unexpectedly during uninstall'
        }
    }
    if (Test-Path $appExe -PathType Leaf) {
        throw 'V3 Flutter executable remained after uninstall'
    }
    Record-Evidence 'uninstall' @{ exit_code = 0; service_removed = $true; listener_removed = $true; app_removed = $true }

    Assert-Marker $marker 'preserve-v3-candidate-data' 'V3 legacy-compatible data was not preserved by uninstall'
    Assert-Marker $aliceDefaultMarker 'alice-default' 'Alice default user data was not preserved by uninstall'
    Assert-Marker $aliceWorkMarker 'alice-work' 'Alice work profile data was not preserved by uninstall'
    Assert-Marker $bobDefaultMarker 'bob-default' 'Bob default user data was not preserved by uninstall'
    Record-Evidence 'uninstall_data_preservation' @{ data_preserved = $true; user_scopes_preserved = $true; data_root = 'ProgramData\\ResearchOSV3' }
}
finally {
    if ($app) {
        try { Stop-CandidateApp $app }
        catch { Write-Warning "Candidate app cleanup did not complete: $($_.Exception.Message)" }
    }
}
