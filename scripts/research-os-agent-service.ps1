[CmdletBinding()]
param(
    [ValidateSet('install','uninstall','start','stop','status')]
    [string]$Action = 'install',
    [string]$ServiceExe = (Join-Path $PSScriptRoot '..\agent_service\ResearchOS.LocalAgent.exe'),
    [string]$DataDir = (Join-Path $env:ProgramData 'ResearchOSAgent')
)
$ErrorActionPreference = 'Stop'
$serviceName = 'ResearchOSLocalAgent'
switch ($Action) {
    'install' {
        $exe = (Resolve-Path $ServiceExe).Path
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
        & icacls.exe $DataDir /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F' | Out-Null
        if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
            & sc.exe stop $serviceName | Out-Null
            & sc.exe delete $serviceName | Out-Null
            Start-Sleep -Seconds 2
        }
        $binPath = '"' + $exe + '"'
        & sc.exe create $serviceName "binPath= $binPath" 'start= demand' 'obj= LocalSystem' 'DisplayName= Research OS Local Agent'
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create Research OS Local Agent service.' }
        & sc.exe description $serviceName 'Outbound-only Research OS Local Agent. No inbound listener is created.'
        Write-Host 'Service installed with Manual start. Configure it with ResearchOS.LocalAgent.exe --configure.'
    }
    'uninstall' {
        if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
            & sc.exe stop $serviceName | Out-Null
            & sc.exe delete $serviceName | Out-Null
        }
        Write-Host 'Local Agent service removed. DPAPI configuration and local data were preserved.'
    }
    'start' { Start-Service -Name $serviceName }
    'stop' { Stop-Service -Name $serviceName -Force }
    'status' { Get-Service -Name $serviceName -ErrorAction Stop }
}
