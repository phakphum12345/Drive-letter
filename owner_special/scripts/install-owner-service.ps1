param(
    [ValidateSet('install','uninstall')][string]$Action,
    [string]$Root = "$env:ProgramFiles\Research OS Owner Special",
    [string]$DataDir = "$env:ProgramData\ResearchOSOwnerSpecial",
    [string]$ServiceName = 'ResearchOSOwnerFriendService',
    [string]$OwnerId = 'owner',
    [int]$Port = 0,
    # CI-only deterministic provider override. Production installs omit this argument
    # and retain the existing Local/Ollama default selected by ServiceHost.
    [ValidateSet('mock')][string]$TestProvider
)
$ErrorActionPreference = 'Stop'

function Show-OwnerServiceDiagnostics {
    Write-Host '--- Owner Friend service diagnostics ---'
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host ((($service | Format-List Name,Status,StartType) | Out-String).Trim())
        sc.exe queryex $ServiceName | Out-Host
    } else {
        Write-Host 'Service is not registered.'
    }
    foreach ($name in @('service.err.log','service.out.log')) {
        $path = Join-Path $DataDir "service\logs\$name"
        Write-Host "--- $path ---"
        if (Test-Path $path) { Get-Content $path -Tail 120 | Out-Host } else { Write-Host '<missing>' }
    }
    $pythonPath = [IO.Path]::GetFullPath((Join-Path $Root 'runtime\python\python.exe'))
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $_.Name -ieq 'python.exe' -and $_.ExecutablePath -and
            ([IO.Path]::GetFullPath($_.ExecutablePath) -ieq $pythonPath)
        } | Select-Object ProcessId,Name,ExecutablePath,CommandLine | Format-List | Out-Host
    } catch {
        Write-Host "Bundled Python diagnostics failed: $($_.Exception.Message)"
    }
}

function Get-OwnerBundledPythonProcesses {
    # The bundled interpreter is shared by API and Owner Friend. The executable
    # path alone is not process ownership; require this install's exact entrypoint.
    $pythonPath = [IO.Path]::GetFullPath((Join-Path $Root 'runtime\python\python.exe'))
    $entrypoint = [IO.Path]::GetFullPath((Join-Path $Root 'owner_special\scripts\run_friend_service.py'))
    return @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        if ($_.Name -ine 'python.exe' -or -not $_.ExecutablePath -or -not $_.CommandLine) {
            return $false
        }
        if ([IO.Path]::GetFullPath($_.ExecutablePath) -ine $pythonPath) {
            return $false
        }
        # Match the full entrypoint path, not a generic Python runtime path.
        return $_.CommandLine.IndexOf($entrypoint, [StringComparison]::OrdinalIgnoreCase) -ge 0
    })
}

function Get-OwnerRuntimePort {
    $registryPath = Join-Path $env:ProgramData 'ResearchOS\runtime\friend.json'
    if (-not (Test-Path $registryPath -PathType Leaf)) { return 0 }
    try {
        $record = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json
        $value = [int]$record.port
        if ($record.schema_version -eq 1 -and $record.service -eq 'friend' -and
            $record.host -eq '127.0.0.1' -and $value -ge 1 -and $value -le 65535 -and
            $record.url -eq "http://127.0.0.1:$value") { return $value }
    } catch {}
    return 0
}

function Get-OwnerListeners([int]$ListenPort) {
    if ($ListenPort -lt 1 -or $ListenPort -gt 65535) { return @() }
    return @(Get-NetTCPConnection -ErrorAction Stop | Where-Object {
        $_.LocalPort -eq $ListenPort -and $_.State -eq 'Listen'
    })
}

function Stop-OwnerBundledPythonFallback {
    $running = @()
    for ($i = 0; $i -lt 20; $i++) {
        $running = @(Get-OwnerBundledPythonProcesses)
        if ($running.Count -eq 0) { return }
        Start-Sleep -Milliseconds 250
    }

    Write-Host "Bundled Python remained after service shutdown; forcing exact packaged runtime process(es)."
    foreach ($process in $running) {
        Write-Host "Stopping bundled Python PID $($process.ProcessId): $($process.ExecutablePath)"
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        } catch {
            if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) { throw }
        }
    }

    for ($i = 0; $i -lt 20; $i++) {
        $running = @(Get-OwnerBundledPythonProcesses)
        if ($running.Count -eq 0) { return }
        Start-Sleep -Milliseconds 250
    }

    Show-OwnerServiceDiagnostics
    throw "Bundled runtime\python\python.exe remained alive after forced shutdown"
}

function Remove-OwnerService {
    $previousPort = Get-OwnerRuntimePort
    $existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.Status -ne 'Stopped') {
            Write-Host "Stopping Owner Friend service before service replacement..."
            Stop-Service -Name $ServiceName -Force -ErrorAction Stop
            $existing = Get-Service -Name $ServiceName -ErrorAction Stop
            $existing.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
            $existing.Refresh()
            if ($existing.Status -ne 'Stopped') {
                Show-OwnerServiceDiagnostics
                throw "Owner Friend service did not stop cleanly: $($existing.Status)"
            }
        }

        sc.exe delete $ServiceName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Show-OwnerServiceDiagnostics
            throw "Failed to delete Owner Friend service registration: sc.exe exit $LASTEXITCODE"
        }

        for ($i = 0; $i -lt 60; $i++) {
            if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 250
        }
        if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
            Show-OwnerServiceDiagnostics
            throw 'Owner Friend service registration remained after delete'
        }
    }

    Stop-OwnerBundledPythonFallback
    if (@(Get-OwnerBundledPythonProcesses).Count -ne 0) {
        Show-OwnerServiceDiagnostics
        throw 'Bundled Python verification failed after service removal'
    }

    $listeners = @()
    for ($i = 0; $i -lt 40; $i++) {
        $listeners = @(Get-OwnerListeners $previousPort)
        if ($listeners.Count -eq 0) { break }
        Start-Sleep -Milliseconds 250
    }
    if ($listeners.Count -gt 0) {
        Show-OwnerServiceDiagnostics
        $pids = ($listeners | ForEach-Object OwningProcess | Sort-Object -Unique) -join ','
        throw "Owner Friend listener on port $Port remained after runtime shutdown. PID(s): $pids"
    }
}

if ($Action -eq 'uninstall') {
    Remove-OwnerService
    Write-Host "Owner Friend service removed. Owner data preserved at $DataDir"
    exit 0
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
$runtimeDir = Join-Path $env:ProgramData 'ResearchOS\runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$icacls = Join-Path $env:WINDIR 'System32\icacls.exe'
& $icacls $runtimeDir '/inheritance:r' '/grant:r' '*S-1-5-18:(OI)(CI)(F)' '*S-1-5-32-544:(OI)(CI)(F)' '*S-1-5-32-545:(OI)(CI)(RX)' '/T' '/C' | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not protect runtime endpoint registry ACLs at $runtimeDir (icacls exit $LASTEXITCODE)."
}
$hostExe = Join-Path $Root 'service_host\ResearchOS.Owner.ServiceHost.exe'
$pythonExe = Join-Path $Root 'runtime\python\python.exe'
$entrypoint = Join-Path $Root 'owner_special\scripts\run_friend_service.py'
foreach ($required in @($hostExe,$pythonExe,$entrypoint)) {
    if (-not (Test-Path $required -PathType Leaf)) { throw "Owner service package file missing: $required" }
}

Remove-OwnerService
$binary = "`"$hostExe`" --root `"$Root`" --python `"$pythonExe`" --data-dir `"$DataDir`" --owner-id `"$OwnerId`" --port $Port --service-name `"$ServiceName`""
if ($TestProvider) {
    $binary += ' --provider ' + $TestProvider
    Write-Host "Owner Friend CI-only provider override: $TestProvider"
}
# A bounded cost ceiling may be supplied by the isolated installer E2E
# process. Inno Setup and this child PowerShell inherit that process environment,
# so the ServiceHost receives the argument from its first start. Normal installs
# leave this unset and preserve the production Local/Ollama behavior.
$testCostCeiling = [Environment]::GetEnvironmentVariable('RESEARCH_OS_RESOURCE_ESTIMATED_COST_USD', 'Process')
if (-not [string]::IsNullOrWhiteSpace($testCostCeiling)) {
    $parsedCostCeiling = [decimal]::Zero
    $culture = [Globalization.CultureInfo]::InvariantCulture
    if (-not [decimal]::TryParse($testCostCeiling, [Globalization.NumberStyles]::Number, $culture, [ref]$parsedCostCeiling) -or $parsedCostCeiling -le 0) {
        throw 'RESEARCH_OS_RESOURCE_ESTIMATED_COST_USD must be a positive invariant-culture amount when supplied to the installer'
    }
    $binary += ' --resource-cost-ceiling-usd ' + $parsedCostCeiling.ToString($culture)
    Write-Host 'Owner Friend CI-only cost reservation ceiling configured through ServiceHost arguments.'
}
New-Service -Name $ServiceName -BinaryPathName $binary -DisplayName 'Research OS Owner Friend Service' -Description 'Local loopback Friend Runtime for Research OS Owner Special' -StartupType Automatic | Out-Null
Start-Service -Name $ServiceName

$ready = $false
$actualPort = 0
$registryPath = Join-Path $env:ProgramData 'ResearchOS\runtime\friend.json'
for ($i = 0; $i -lt 100; $i++) {
    try {
        if (Test-Path $registryPath -PathType Leaf) {
            $record = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json
            $candidate = [int]$record.port
            if ($record.schema_version -eq 1 -and $record.service -eq 'friend' -and
                $record.host -eq '127.0.0.1' -and $candidate -ge 1 -and $candidate -le 65535 -and
                $record.url -eq "http://127.0.0.1:$candidate") {
                $health = Invoke-RestMethod -Uri "$($record.url)/owner/health" -TimeoutSec 2
                if ($health.status -eq 'ok') { $actualPort = $candidate; $ready = $true; break }
            }
        }
    } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $ready) {
    Show-OwnerServiceDiagnostics
    throw 'Owner Friend Windows Service did not publish a valid dynamic endpoint and become HTTP-ready after installation'
}

$listeners = @(Get-OwnerListeners $actualPort)
if ($listeners.Count -lt 1) { throw 'Owner Friend service has no listening socket after installation' }
if ($listeners | Where-Object { $_.LocalAddress -notin @('127.0.0.1','::1') }) { throw 'Owner Friend service is not loopback-only' }
Write-Host "Owner Friend service installed and ready on 127.0.0.1:$actualPort"
