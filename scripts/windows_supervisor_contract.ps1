<#
AI Private Workspace — Windows supervisor contract

This script is a packaging foundation contract, not the final installer launcher.
It documents the Windows lifecycle that the desktop shell must implement.

Safety boundaries:
- Start only app-owned backend runtime.
- Bind backend to 127.0.0.1.
- Wait for /health before opening UI.
- Never kill unknown processes using the same port.
- Never start scan/index/rebuild/MCP/agent/model downloads on app launch.
#>

param(
    [int]$BackendPort = 8000,
    [string]$AppName = "AI Private Workspace"
)

$ErrorActionPreference = "Stop"

$AppDataRoot = Join-Path $env:LOCALAPPDATA $AppName
$LogsDir = Join-Path $AppDataRoot "logs"
$PidFile = Join-Path $AppDataRoot "backend.pid"
$SupervisorLog = Join-Path $LogsDir "windows-supervisor.log"
$BackendLog = Join-Path $LogsDir "backend.log"
$HealthUrl = "http://127.0.0.1:$BackendPort/health"

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

function Write-SupervisorLog {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
    "$Timestamp $Message" | Tee-Object -FilePath $SupervisorLog -Append | Out-Null
}

function Test-PortInUse {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $connections
}

Write-SupervisorLog "Supervisor contract check started. HealthUrl=$HealthUrl"
Write-SupervisorLog "AppDataRoot=$AppDataRoot"
Write-SupervisorLog "LogsDir=$LogsDir"
Write-SupervisorLog "PidFile=$PidFile"
Write-SupervisorLog "BackendLog=$BackendLog"

if (Test-PortInUse -Port $BackendPort) {
    Write-SupervisorLog "Port $BackendPort is already in use. Do not kill unknown processes. Show a friendly startup error."
    Write-Host "Port $BackendPort is already in use. The packaged app must not kill unknown processes."
    exit 2
}

Write-SupervisorLog "Port $BackendPort appears free. Final desktop shell may start only the app-owned packaged backend here."
Write-Host "Windows supervisor contract is valid. Final packaging still needs app-owned backend runtime wiring."
