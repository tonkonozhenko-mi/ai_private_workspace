<#
AI Private Workspace — Windows package foundation

Creates a developer-readable Windows packaging manifest.
It does not build a signed installer and does not include runtime data.
#>

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildDir = Join-Path $ProjectRoot "build\windows"
$ManifestPath = Join-Path $BuildDir "AI_PRIVATE_WORKSPACE_WINDOWS_PACKAGE_MANIFEST.txt"

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

$RequiredPaths = @(
    "frontend\src-tauri\tauri.conf.json",
    "frontend\src-tauri\Cargo.toml",
    "frontend\src-tauri\src\main.rs",
    "backend\app",
    "backend\requirements.txt",
    "scripts\windows_supervisor_contract.ps1"
)

foreach ($RelativePath in $RequiredPaths) {
    $FullPath = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path $FullPath)) {
        throw "Missing required packaging resource: $RelativePath"
    }
}

$Now = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
@"
AI Private Workspace Windows package foundation
GeneratedAt=$Now
ProjectRoot=$ProjectRoot
TargetShell=Tauri Windows
AppData=%LOCALAPPDATA%\AI Private Workspace
Logs=%LOCALAPPDATA%\AI Private Workspace\logs
Health=http://127.0.0.1:8000/health

Included source-controlled resources:
- frontend/src-tauri
- frontend build output after npm run build
- backend app source or future frozen backend runtime
- scripts/windows_supervisor_contract.ps1

Excluded runtime/build data:
- backend/.ai-workbench
- *.db
- *.sqlite
- node_modules
- dist
- build runtime outputs outside this manifest
- __pycache__
- .pytest_cache

Safety rules:
- Frontend never runs shell commands.
- Windows shell starts only app-owned backend process.
- Never kill unknown process by port.
- No scan/index/rebuild/MCP/agent/model download on launch.
"@ | Set-Content -Path $ManifestPath -Encoding UTF8

Write-Host "Windows package foundation manifest created: $ManifestPath"
