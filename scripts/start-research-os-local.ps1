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
function Get-FreeLoopbackPort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  try {
    $listener.Start()
    return [int]$listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

# Zero means choose an available loopback port for this run. Explicit values
# remain supported for diagnostics and externally managed Tailscale Serve.
if ($Port -le 0) { $Port = Get-FreeLoopbackPort }
if ($FriendPort -le 0) { $FriendPort = Get-FreeLoopbackPort }
if ($Port -eq $FriendPort) { throw "API and Friend Service must use different ports." }
$FriendUrl = "http://127.0.0.1:$FriendPort"

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
  $LogDir
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
$env:RESEARCH_OS_API_HOST = $HostAddress
$env:RESEARCH_OS_API_PORT = "$Port"
$env:RESEARCH_OS_FRIEND_URL = $FriendUrl
$env:RESEARCH_OS_FRIEND_OWNER = "owner"
$env:RESEARCH_OS_AI_ROUTE = "friend"
$env:HOST = $HostAddress
$env:PORT = "$Port"

function Test-FriendHealth {
  try {
    $health = Invoke-RestMethod "$FriendUrl/owner/health" -TimeoutSec 2
    return ($health.status -eq "ok")
  } catch {
    return $false
  }
}

function Start-FriendService {
  if (Test-FriendHealth) {
    Write-Host "Friend Service already running at $FriendUrl."
    return $null
  }

  $startArgs = @{
    FilePath = "python"
    ArgumentList = @(
      $FriendScript,
      "--owner-id", "owner",
      "--host", "127.0.0.1",
      "--port", "$FriendPort",
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

  for ($i = 0; $i -lt 40; $i++) {
    if (Test-FriendHealth) {
      Write-Host "Friend Service ready at $FriendUrl (PID $($process.Id))."
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
  throw "Friend Service did not become ready at $FriendUrl. See $FriendErrLog"
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
Write-Host "Friend URL     : $FriendUrl"
Write-Host "Local API URL  : http://127.0.0.1:$Port"
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
  for ($i = 0; $i -lt 60; $i++) {
    if ($process.HasExited) {
      $detail = if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 | Out-String } else { "no stderr log" }
      if ($friendProcess -and -not $friendProcess.HasExited) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
      Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
      Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
      throw "Research OS API exited before becoming ready. $detail"
    }
    try {
      $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2
      if ($health.status -eq "ok") { $apiReady = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $apiReady) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    if ($friendProcess -and -not $friendProcess.HasExited) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
    throw "Research OS API did not become ready at http://127.0.0.1:$Port. See $ErrLog"
  }

  try {
    & $ServeScript -ApiPort $Port -ExpectedHostname $ExpectedServeHostname
  } catch {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    if ($friendProcess -and -not $friendProcess.HasExited) { Stop-Process -Id $friendProcess.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $FriendPidFile -Force -ErrorAction SilentlyContinue
    throw
  }

  Write-Host "Research OS Local API started in background (PID $($process.Id))."
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
  for ($i = 0; $i -lt 60; $i++) {
    if ($foregroundApi.HasExited) {
      $detail = if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 | Out-String } else { "no stderr log" }
      throw "Research OS API exited before becoming ready. $detail"
    }
    try {
      $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2
      if ($health.status -eq "ok") { $apiReady = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $apiReady) { throw "Research OS API did not become ready at http://127.0.0.1:$Port. See $ErrLog" }

  & $ServeScript -ApiPort $Port -ExpectedHostname $ExpectedServeHostname
  Write-Host "Research OS API is ready at https://$ExpectedServeHostname"
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
