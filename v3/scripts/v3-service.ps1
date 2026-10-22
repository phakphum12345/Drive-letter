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
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($service) {
            $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
        }
    }

    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
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
            throw "Windows service $ServiceName remains registered after deletion"
        }
    }
    # Never terminate a process merely because it owns the configured port.
    # A listener may belong to an unrelated application.
}

if ($Action -eq 'uninstall') {
    Remove-V3Service
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
$config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8
Write-Host "Research OS V3 service installed and ready on 127.0.0.1:$selectedPort"
Write-Host "Selected port saved to $configPath"
