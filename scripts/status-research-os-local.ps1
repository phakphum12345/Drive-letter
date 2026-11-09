param(
  [string]$DataDir = "$env:USERPROFILE\ResearchOSData",
  [string]$HealthUrl = ""
)

$ErrorActionPreference = "Stop"
$registryPath = Join-Path $DataDir "runtime\api.json"
$apiUrl = ""

if (Test-Path $registryPath -PathType Leaf) {
  try {
    $record = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json
    $port = [int]$record.port
    if ($record.schema_version -eq 1 -and $record.service -eq "api" -and
        $record.host -eq "127.0.0.1" -and $port -ge 1 -and $port -le 65535 -and
        $record.url -eq "http://127.0.0.1:$port") {
      $apiUrl = [string]$record.url
    }
  } catch {}
}

if (-not [string]::IsNullOrWhiteSpace($HealthUrl)) {
  $apiUrl = $HealthUrl.TrimEnd("/")
}

if ([string]::IsNullOrWhiteSpace($apiUrl)) {
  Write-Host "Runtime endpoint: not registered"
  exit 1
}

$portValue = ([uri]$apiUrl).Port
$listener = Get-NetTCPConnection -LocalPort $portValue -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
  Write-Host "Listener : running"
  Write-Host "Endpoint : $apiUrl"
  Write-Host "PID      : $($listener.OwningProcess)"
} else {
  Write-Host "Listener : stopped"
  Write-Host "Endpoint : $apiUrl"
}

try {
  $health = Invoke-RestMethod -Uri "$apiUrl/health" -TimeoutSec 3
  Write-Host "Health   : $($health.status)"
  Write-Host "Service  : $($health.service)"
  Write-Host "Version  : $($health.version)"
  exit 0
} catch {
  Write-Host "Health   : unavailable"
  exit 1
}
