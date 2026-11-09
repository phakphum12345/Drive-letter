param(
  [string]$DataDir = "$env:USERPROFILE\ResearchOSData",
  [string]$PidFile = "",
  [string]$FriendPidFile = ""
)

$ErrorActionPreference = "Stop"
$RunDir = Join-Path $DataDir "run"
if ([string]::IsNullOrWhiteSpace($PidFile)) { $PidFile = Join-Path $RunDir "research-os-api.pid" }
if ([string]::IsNullOrWhiteSpace($FriendPidFile)) { $FriendPidFile = Join-Path $RunDir "research-os-friend.pid" }

function Stop-ManagedProcess([string]$Path, [string]$ExpectedEntrypoint) {
  if (-not (Test-Path $Path -PathType Leaf)) { return }
  $rawPid = (Get-Content -LiteralPath $Path -Raw).Trim()
  $pidValue = 0
  if ([int]::TryParse($rawPid, [ref]$pidValue) -and $pidValue -gt 0) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue
    if ($process -and $process.Name -ieq "python.exe" -and
        $process.CommandLine -and
        $process.CommandLine.IndexOf($ExpectedEntrypoint, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
      Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
      Write-Host "Stopped managed Research OS process $ExpectedEntrypoint (PID $pidValue)."
    } elseif ($process) {
      Write-Warning "PID $pidValue no longer identifies the expected Research OS entrypoint; it was not terminated."
    }
  }
  Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

Stop-ManagedProcess $PidFile "render_server.py"
Stop-ManagedProcess $FriendPidFile "run_friend_service.py"
Write-Host "Research OS Local API and managed Friend process shutdown requested."
