param(
  [Parameter(Mandatory = $true)]
  [ValidateRange(1, 65535)]
  [int]$ApiPort,
  [string]$ExpectedHostname = "phakphumwir.tail4b06c9.ts.net"
)

$ErrorActionPreference = "Stop"

$tailscale = Get-Command "tailscale.exe" -ErrorAction SilentlyContinue
if (-not $tailscale) { $tailscale = Get-Command "tailscale" -ErrorAction SilentlyContinue }
if (-not $tailscale) {
  $defaultPath = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
  if (Test-Path $defaultPath -PathType Leaf) {
    $tailscalePath = $defaultPath
  } else {
    throw "Tailscale CLI was not found. Install and sign in to Tailscale on the Research OS host before publishing the Flutter API endpoint."
  }
} else {
  $tailscalePath = $tailscale.Source
}

$statusJson = & $tailscalePath status --json 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "Tailscale is not ready or this device is not signed in. Details: $($statusJson | Out-String)"
}
try {
  $status = ($statusJson | Out-String) | ConvertFrom-Json
} catch {
  throw "Tailscale status did not return valid JSON: $($_.Exception.Message)"
}

$actualHostname = ([string]$status.Self.DNSName).TrimEnd(".").ToLowerInvariant()
$expected = $ExpectedHostname.TrimEnd(".").ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($actualHostname) -or $actualHostname -ne $expected) {
  throw "Wrong Tailscale host. Expected '$expected', got '$actualHostname'. Refusing to publish the Research OS API on another device."
}

$target = "http://127.0.0.1:$ApiPort"
$serveOutput = & $tailscalePath serve --bg $target 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "Could not update Tailscale Serve to the automatically selected API port $ApiPort. Enable HTTPS for Serve in the tailnet and retry. Details: $($serveOutput | Out-String)"
}

$serveStatus = & $tailscalePath serve status 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "Tailscale Serve configuration could not be verified. Details: $($serveStatus | Out-String)"
}
$serveText = $serveStatus | Out-String
if ($serveText -notmatch [regex]::Escape($expected) -or $serveText -notmatch [regex]::Escape($target)) {
  throw "Tailscale Serve verification failed: expected https://$expected to proxy to $target. Details: $serveText"
}

Write-Host "RESEARCH_OS_TAILSCALE_SERVE=PASS"
Write-Host "RESEARCH_OS_PUBLIC_API=https://$expected"
Write-Host "RESEARCH_OS_INTERNAL_API=$target"
