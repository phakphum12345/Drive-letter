param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall')]
    [string]$Action,

    [string]$ServiceName = 'ResearchOSV3Service',
    [ValidateRange(1, 65535)]
    [int]$Port = 8788,
    [ValidateRange(0, 1000)]
    [int]$PortScanCount = 100
)

$ErrorActionPreference = 'Stop'

$appRoot = Split-Path -Parent $PSScriptRoot
$serviceExe = Join-Path $appRoot 'service\ResearchOS.V3.ServiceHost.exe'
$v3Root = Join-Path $appRoot 'v3'
$pythonExe = Join-Path $v3Root 'runtime\python\python.exe'
$dataDir = Join-Path $env:ProgramData 'ResearchOSV3'
$configPath = Join-Path $dataDir 'service.json'
$lifecycleLogPath = Join-Path $dataDir 'logs\service-lifecycle.log'

function Write-ServiceLifecycleLog([string]$Message) {
    try {
        $logDir = Split-Path -Parent $lifecycleLogPath
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        $line = '[{0}] {1}' -f [DateTimeOffset]::UtcNow.ToString('O'), $Message
        Add-Content -LiteralPath $lifecycleLogPath -Value $line -Encoding utf8
    }
    catch {
        # Diagnostics must never replace the original service lifecycle error.
    }
}

function Test-LoopbackPortAvailable([int]$CandidatePort) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $CandidatePort)
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($listener) {
            try { $listener.Stop() } catch { }
        }
    }
}

function Find-AvailableLoopbackPort([int]$StartPort, [int]$ScanCount) {
    $lastPort = [Math]::Min(65535, $StartPort + $ScanCount)
    for ($candidate = $StartPort; $candidate -le $lastPort; $candidate++) {
        if (Test-LoopbackPortAvailable $candidate) {
            return $candidate
        }
    }
    throw "No available loopback port found from $StartPort through $lastPort"
}

function Remove-V3Service {
    Write-ServiceLifecycleLog "Remove-V3Service started; service=$ServiceName"
    $serviceInfo = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
    $servicePid = if ($serviceInfo) { [int]$serviceInfo.ProcessId } else { 0 }
    $serviceExeFullPath = [System.IO.Path]::GetFullPath($serviceExe)
    $serviceProcessSnapshot = $null
    if ($servicePid -gt 0) {
        $serviceProcessSnapshot = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid" -ErrorAction SilentlyContinue
        if (-not $serviceProcessSnapshot -or -not $serviceProcessSnapshot.ExecutablePath -or
            [System.IO.Path]::GetFullPath($serviceProcessSnapshot.ExecutablePath) -ine $serviceExeFullPath) {
            throw "Refusing to stop service '$ServiceName': PID $servicePid is not the expected V3 ServiceHost executable"
        }
    }
    $serviceProcessCreationDate = if ($serviceProcessSnapshot) { [string]$serviceProcessSnapshot.CreationDate } else { '' }
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

    Write-ServiceLifecycleLog ("Initial service state: status={0}; pid={1}" -f $(if ($service) { $service.Status } else { 'NotFound' }), $servicePid)
    if ($service -and $service.Status -ne 'Stopped') {
        Write-ServiceLifecycleLog "Requesting service stop"
        Stop-Service -Name $ServiceName -Force
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($service) {
            $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
            Write-ServiceLifecycleLog "Service Control Manager reports Stopped"
        }
    }

    # SCM can report Stopped before the service process has released its image.
    # Wait for the exact ServiceHost PID to exit before Inno Setup replaces files.
    if ($servicePid -gt 0) {
        Write-ServiceLifecycleLog "Waiting for captured service PID $servicePid to release ServiceHost image"
        $serviceProcessExited = $false
        for ($attempt = 0; $attempt -lt 120; $attempt++) {
            $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid" -ErrorAction SilentlyContinue
            if (-not $processInfo) {
                $serviceProcessExited = $true
                break
            }
            if ($processInfo.ExecutablePath -and
                [System.IO.Path]::GetFullPath($processInfo.ExecutablePath) -ine $serviceExeFullPath) {
                $serviceProcessExited = $true
                break
            }
            Start-Sleep -Milliseconds 250
        }
        Write-ServiceLifecycleLog ("Service PID wait completed: exited={0}" -f $serviceProcessExited)
        if (-not $serviceProcessExited) {
            # SCM may report Stopped before the owned service-host process has
            # fully exited. Escalate only after rechecking that the service is
            # stopped, SCM no longer assigns a PID, and this is the same process
            # (PID + creation time + executable path) captured before shutdown.
            $serviceAfterStop = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
            $serviceInfoAfterStop = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
            $currentProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid" -ErrorAction SilentlyContinue
            $sameOwnedProcess = $currentProcess -and $currentProcess.ExecutablePath -and
                ([string]$currentProcess.CreationDate -eq $serviceProcessCreationDate) -and
                ([System.IO.Path]::GetFullPath($currentProcess.ExecutablePath) -ieq $serviceExeFullPath)
            $serviceStopped = (-not $serviceAfterStop -or $serviceAfterStop.Status -eq 'Stopped') -and
                (-not $serviceInfoAfterStop -or [int]$serviceInfoAfterStop.ProcessId -eq 0)
            if (-not $serviceStopped -or -not $sameOwnedProcess) {
                throw "Windows service host PID $servicePid did not exit and its stopped-state process identity could not be safely verified"
            }

            Write-ServiceLifecycleLog "SCM is stopped and PID identity is unchanged; terminating only the captured V3 ServiceHost process"
            Stop-Process -Id $servicePid -Force -ErrorAction Stop
            $serviceProcessExited = $false
            for ($attempt = 0; $attempt -lt 40; $attempt++) {
                $currentProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid" -ErrorAction SilentlyContinue
                if (-not $currentProcess -or
                    [string]$currentProcess.CreationDate -ne $serviceProcessCreationDate -or
                    -not $currentProcess.ExecutablePath -or
                    [System.IO.Path]::GetFullPath($currentProcess.ExecutablePath) -ine $serviceExeFullPath) {
                    $serviceProcessExited = $true
                    break
                }
                Start-Sleep -Milliseconds 250
            }
            Write-ServiceLifecycleLog ("Targeted service-host cleanup completed: exited={0}" -f $serviceProcessExited)
            if (-not $serviceProcessExited) {
                throw "Verified V3 service host PID $servicePid remained after targeted cleanup"
            }
        }
    }

    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
        Write-ServiceLifecycleLog "Requesting service registration deletion"
        sc.exe delete $ServiceName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to delete Windows service $ServiceName"
        }
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
                break
            }
            Start-Sleep -Milliseconds 250
        }
        if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
            Write-ServiceLifecycleLog "Service registration still exists after deletion wait"
            throw "Windows service $ServiceName remains registered after deletion"
        }
    }
    Write-ServiceLifecycleLog "Remove-V3Service completed successfully"
    # Never terminate a process merely because it owns the configured port.
    # A listener may belong to an unrelated application.
}

if ($Action -eq 'uninstall') {
    try {
        Remove-V3Service
    }
    catch {
        Write-ServiceLifecycleLog ("Remove-V3Service FAILED: {0}" -f ($_ | Out-String).Trim())
        throw
    }
    Write-Host "Research OS V3 service removed. Data preserved at $dataDir"
    exit 0
}

if (-not (Test-Path $serviceExe -PathType Leaf)) {
    throw "V3 ServiceHost executable not found: $serviceExe"
}
if (-not (Test-Path $pythonExe -PathType Leaf)) {
    throw "Bundled Python executable not found: $pythonExe"
}
if (-not (Test-Path (Join-Path $v3Root 'scripts\run_service.py') -PathType Leaf)) {
    throw "V3 service entrypoint not found under $v3Root"
}

New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
Remove-V3Service

$selectedPort = Find-AvailableLoopbackPort -StartPort $Port -ScanCount $PortScanCount
$binaryPath = "`"$serviceExe`" --root `"$v3Root`" --python `"$pythonExe`" --port $selectedPort --data-dir `"$dataDir`" --service-name `"$ServiceName`""
New-Service -Name $ServiceName -BinaryPathName $binaryPath -StartupType Automatic -DisplayName 'Research OS V3 Local Service' | Out-Null
Start-Service -Name $ServiceName

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$selectedPort/health" -TimeoutSec 2
        if ($health.status -eq 'ok') {
            $ready = $true
            break
        }
    }
    catch { }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    throw "Research OS V3 service did not become ready on selected port $selectedPort"
}

$listeners = @(Get-NetTCPConnection -LocalPort $selectedPort -State Listen -ErrorAction Stop)
if ($listeners.Count -lt 1) {
    throw 'Research OS V3 service has no listening socket after installation'
}
if ($listeners | Where-Object { $_.LocalAddress -ne '127.0.0.1' }) {
    throw 'Research OS V3 service is not loopback-only'
}
$serviceInfo = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'"
if (-not $serviceInfo -or $serviceInfo.ProcessId -eq 0) {
    throw 'Cannot establish ownership of the installed V3 Windows service process'
}
foreach ($listener in $listeners) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if (-not $owner -or -not $owner.ExecutablePath -or
        [System.IO.Path]::GetFullPath($owner.ExecutablePath) -ine [System.IO.Path]::GetFullPath($pythonExe)) {
        throw "Selected port $selectedPort is not owned by the bundled V3 Python runtime"
    }
}

$config = [ordered]@{
    schema_version = 1
    service_name = $ServiceName
    host = '127.0.0.1'
    port = $selectedPort
}
$configJson = $config | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($configPath, $configJson, [System.Text.UTF8Encoding]::new($false))
Write-Host "Research OS V3 service installed and ready on 127.0.0.1:$selectedPort"
Write-Host "Selected port saved to $configPath"
