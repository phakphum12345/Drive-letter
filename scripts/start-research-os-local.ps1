param(
  [string]$DataDir = "$env:USERPROFILE\ResearchOSData",
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 0,
  [int]$FriendPort = 0,
  [ValidateSet("gemini", "mock", "local", "openai-compatible", "anthropic")]
  [string]$Provider = "local",
  [switch]$Background
)

$ErrorActionPreference = "Stop"

# Tailscale Serve configuration on Windows requires an elevated terminal.
# Re-launch this same script through UAC so users do not need to configure
# privileges or ports manually.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  $arguments = @(
    "-NoProfile",
    "-ExecutionPolicy Bypass",
    "-File `"$PSCommandPath`"",
    "-DataDir `"$DataDir`"",
    "-HostAddress `"$HostAddress`"",
    "-Port $Port",
    "-FriendPort $FriendPort",
    "-Provider $Provider"
  )
  if ($Background) { $arguments += "-Background" }
  try {
    $elevated = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList ($arguments -join " ") -Wait -PassThru
    exit $elevated.ExitCode
  } catch {
    throw "Research OS setup needs Administrator approval to configure Tailscale Serve. No services were started. $($_.Exception.Message)"
  }
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
# Establish the repository import boundary for every child Python process. The local
# launcher intentionally starts render_server.py from tools/research_os_api, while
# Platform modules remain canonical under the repository-level tools package.
$repoPythonPath = $RepoRoot
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $env:PYTHONPATH = $repoPythonPath
} elseif (($env:PYTHONPATH -split [IO.Path]::PathSeparator) -notcontains $repoPythonPath) {
  $env:PYTHONPATH = "$repoPythonPath$([IO.Path]::PathSeparator)$env:PYTHONPATH"
}
$ApiDir = Join-Path $RepoRoot "tools\research_os_api"
$FriendScript = Join-Path $RepoRoot "owner_special\scripts\run_friend_service.py"
$ServeScript = Join-Path $PSScriptRoot "configure-research-os-tailscale-serve.ps1"
$ExpectedServeHostname = "phakphumwir.tail4b06c9.ts.net"
$RunDir = Join-Path $DataDir "run"
$LogDir = Join-Path $DataDir "logs"
$PidFile = Join-Path $RunDir "research-os-api.pid"
$FriendPidFile = Join-Path $RunDir "research-os-friend.pid"
$OutLog = Join-Path $LogDir "research-os-api.out.log"
$ErrLog = Join-Path $LogDir "research-os-api.err.log"
$FriendOutLog = Join-Path $LogDir "research-os-friend.out.log"
$FriendErrLog = Join-Path $LogDir "research-os-friend.err.log"
$FriendDataDir = Join-Path $DataDir "owner-friend"
$FriendAuditPath = Join-Path $LogDir "research-os-friend.audit.jsonl"
$RuntimeDir = Join-Path $DataDir "runtime"
$FriendUrl = ""

function Get-RuntimeEndpoint([string]$Service) {
  $paths = @(
    (Join-Path $RuntimeDir "$Service.json"),
    (Join-Path $env:ProgramData "ResearchOS\runtime\$Service.json")
  ) | Select-Object -Unique
  $path = $paths | Where-Object { Test-Path $_ -PathType Leaf } | Select-Object -First 1
  if (-not $path) { return $null }
  try {
    $record = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $port = [int]$record.port
    if ($record.schema_version -ne 1 -or $record.service -ne $Service -or
        $record.host -ne "127.0.0.1" -or $port -lt 1 -or $port -gt 65535 -or
        $record.url -ne "http://127.0.0.1:$port") { return $null }
    return $record
  } catch { return $null }
}

if (-not (Test-Path $ApiDir)) {
  throw "Research OS API directory not found: $ApiDir"
}
if (-not (Test-Path $FriendScript)) {
  throw "Research OS Friend service entrypoint not found: $FriendScript"
}

@(
  $DataDir,
  (Join-Path $DataDir "sessions"),
  (Join-Path $DataDir "database"),
  (Join-Path $DataDir "artifacts"),
  (Join-Path $DataDir "backups"),
  $FriendDataDir,
  $RunDir,
  $LogDir,
  $RuntimeDir
) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

$env:RESEARCH_OS_DATA_DIR = $DataDir
$env:RESEARCH_OS_CONVERSATION_STORE = Join-Path $DataDir "sessions\conversations.json"
$env:RESEARCH_OS_PROVIDER = $Provider
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_BASE_URL)) {
  $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
}
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MODEL)) {
  $env:OLLAMA_MODEL = "llama3.2:3b"
}
$env:RESEARCH_OS_RUNTIME_DIR = $RuntimeDir
$env:RESEARCH_OS_API_HOST = $HostAddress
$env:RESEARCH_OS_API_PORT = "$Port"
$env:RESEARCH_OS_FRIEND_URL = ""
$env:RESEARCH_OS_FRIEND_OWNER = "owner"
$env:RESEARCH_OS_AI_ROUTE = "friend"
$env:HOST = $HostAddress
$env:PORT = "$Port"

function Test-FriendHealth {
  if ([string]::IsNullOrWhiteSpace($script:FriendUrl)) { return $false }
  try {
    $health = Invoke-RestMethod "$script:FriendUrl/owner/health" -TimeoutSec 2
    return ($health.status -eq "ok")
  } catch {
    return $false
  }
}

function Start-FriendService {
  $existingEndpoint = Get-RuntimeEndpoint "friend"
  if ($existingEndpoint) {
    $script:FriendUrl = [string]$existingEndpoint.url
    if (Test-FriendHealth) {
      $env:RESEARCH_OS_FRIEND_URL = $script:FriendUrl
      Write-Host "Friend Service already running at $script:FriendUrl."
      return $null
    }
  }
  Remove-Item (Join-Path $RuntimeDir "friend.json") -Force -ErrorAction SilentlyContinue

  $startArgs = @{
    FilePath = "python"
    ArgumentList = @(
      $FriendScript,
      "--owner-id", "owner",
      "--host", "127.0.0.1",
      "--port", "0",
      "--data-root", $FriendDataDir,
      "--audit-path", $FriendAuditPath,
      "--repository-root", $RepoRoot
    )
    WorkingDirectory = $RepoRoot
    WindowStyle = "Hidden"
    RedirectStandardOutput = $FriendOutLog
    RedirectStandardError = $FriendErrLog
    PassThru = $true
  }
  $process = Start-Process @startArgs
  Set-Content -Path $FriendPidFile -Value $process.Id -NoNewline

  for ($i = 0; $i -lt 60; $i++) {
    $endpoint = Get-RuntimeEndpoint "friend"
    if ($endpoint) { $script:FriendUrl = [string]$endpoint.url }
    if (Test-FriendHealth) {
      $env:RESEARCH_OS_FRIEND_URL = $script:FriendUrl
      Write-Host "Friend Service ready at $script:FriendUrl (PID $($process.Id))."
      return $process
    }
    if ($process.HasExited) {
      $detail = if (Test-Path $FriendErrLog) { Get-Content $FriendErrLog -Tail 20 | Out-String } else { "no stderr log" }
      throw "Friend Service exited before becoming ready. $detail"
    }
    Start-Sleep -Milliseconds 250
  }

  if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  }
  throw "Friend Service did not publish a valid dynamic endpoint and become ready. See $FriendErrLog"
}

function Stop-ProcessFromPidFile([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  $pidText = (Get-Content $Path -Raw).Trim()
  $pidValue = 0
  if ([int]::TryParse($pidText, [ref]$pidValue)) {
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $Path -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Research OS Local API + Friend Service"
Write-Host "Data directory : $DataDir"
Write-Host "Provider       : $Provider"
Write-Host "Friend URL     : generated at startup"
Write-Host "Local API URL  : generated at startup"
Write-Host "Bind address   : $HostAddress (loopback-only by default)"
Write-Host "Tailscale Serve : configured automatically after API startup"
Write-Host "Public API      : https://$ExpectedServeHostname"
Write-Host ""
Write-Host "Friend Service is a required local dependency for RESEARCH_OS_AI_ROUTE=friend."
Write-Host "Secrets are NOT stored by this script."
Write-Host "Local default: Ollama at $($env:OLLAMA_BASE_URL) using model $($env:OLLAMA_MODEL)."
Write-Host ""

$friendProcess = Start-FriendService

if ($Background) {
  if (Test-Path $PidFile) {
    $existingPidText = (Get-Content $PidFile -Raw).Trim()
    $existingPid = 0
    if ([int]::TryParse($existingPidText, [ref]$existingPid)) {
      $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
      if ($existing) {
        Write-Host "Research OS Local API is already running (PID $existingPid)."
        if ($friendProcess) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
        exit 0
      }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  }

  $startArgs = @{
    FilePath = "python"
    ArgumentList = "render_server.py"
    WorkingDirectory = $ApiDir
    WindowStyle = "Hidden"
    RedirectStandardOutput = $OutLog
    RedirectStandardError = $ErrLog
    PassThru = $true
  }
  $process = Start-Process @startArgs
  Set-Content -Path $PidFile -Value $process.Id -NoNewline

  $apiReady = $false
  $apiUrl = ""
  $apiPort = 0
  for ($i = 0; $i -lt 60; $i++) {
    if ($process.HasExited) {
      $detail = if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 | Out-String } else { "no stderr log" }
      if ($friendProcess -and -not $friendProcess.HasExited) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
      Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
      Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
      throw "Research OS API exited before becoming ready. $detail"
    }
    $endpoint = Get-RuntimeEndpoint "api"
    if ($endpoint) {
      $apiUrl = [string]$endpoint.url
      $apiPort = [int]$endpoint.port
      try {
        $health = Invoke-RestMethod "$apiUrl/health" -TimeoutSec 2
        if ($health.status -eq "ok") { $apiReady = $true; break }
      } catch {}
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $apiReady) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    if ($friendProcess -and -not $friendProcess.HasExited) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
    throw "Research OS API did not publish a valid dynamic endpoint and become ready. See $ErrLog"
  }

  try {
    & $ServeScript -ApiPort $apiPort -ExpectedHostname $ExpectedServeHostname
  } catch {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    if ($friendProcess -and -not $friendProcess.HasExited) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
    throw
  }

  Write-Host "Research OS Local API started at $apiUrl (PID $($process.Id))."
  Write-Host "Friend Service PID : $($friendProcess.Id)"
  Write-Host "API PID file       : $PidFile"
  Write-Host "Logs               : $LogDir"
  Write-Host "Flutter endpoint   : https://$ExpectedServeHostname"
  exit 0
}

$foregroundApi = $null
try {
  $foregroundArgs = @{
    FilePath = "python"
    ArgumentList = "render_server.py"
    WorkingDirectory = $ApiDir
    WindowStyle = "Hidden"
    RedirectStandardOutput = $OutLog
    RedirectStandardError = $ErrLog
    PassThru = $true
  }
  $foregroundApi = Start-Process @foregroundArgs
  Set-Content -Path $PidFile -Value $foregroundApi.Id -NoNewline

  $apiReady = $false
  $apiUrl = ""
  $apiPort = 0
  for ($i = 0; $i -lt 60; $i++) {
    if ($foregroundApi.HasExited) {
      $detail = if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 | Out-String } else { "no stderr log" }
      throw "Research OS API exited before becoming ready. $detail"
    }
    $endpoint = Get-RuntimeEndpoint "api"
    if ($endpoint) {
      $apiUrl = [string]$endpoint.url
      $apiPort = [int]$endpoint.port
      try {
        $health = Invoke-RestMethod "$apiUrl/health" -TimeoutSec 2
        if ($health.status -eq "ok") { $apiReady = $true; break }
      } catch {}
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $apiReady) { throw "Research OS API did not publish a valid dynamic endpoint and become ready. See $ErrLog" }

  & $ServeScript -ApiPort $apiPort -ExpectedHostname $ExpectedServeHostname
  Write-Host "Research OS API is ready at $apiUrl and https://$ExpectedServeHostname"
  Write-Host "Press Ctrl+C to stop the local API and Friend Service."
  Wait-Process -Id $foregroundApi.Id
}
finally {
  if ($foregroundApi -and -not $foregroundApi.HasExited) {
    Stop-Process -Id $foregroundApi.Id -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  if ($friendProcess -and -not $friendProcess.HasExited) {
    Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
}
