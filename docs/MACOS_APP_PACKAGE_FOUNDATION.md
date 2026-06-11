# Task 215 — macOS app package foundation

This task starts the move from developer scripts to a real desktop package.
It is still a foundation step, not the final signed macOS app.

## Goal

Final product target:

```text
download package -> double click AI Private Workspace.app -> local backend starts -> UI opens
```

The user should not need to clone the repository, run backend scripts, run frontend scripts, or understand development commands.

## What was added

- `GET /runtime/macos-app-package-foundation`
- `scripts/package_macos_app_foundation.sh`
- Settings UI section under **Desktop packaging / Two-click app architecture**

The endpoint and UI explain the app bundle contract, expected artifacts, build steps, validation steps, and safety boundaries.

## Build the foundation bundle

From the project root:

```bash
cd frontend
npm ci
npm run build

cd ..
./scripts/package_macos_app_foundation.sh
```

Expected output:

```text
build/macos/AI Private Workspace.app
```

Open it for local validation:

```bash
open "build/macos/AI Private Workspace.app"
```

## What the script does

The script creates a macOS `.app` bundle skeleton:

```text
build/macos/AI Private Workspace.app/
  Contents/
    Info.plist
    MacOS/
      AI Private Workspace
    Resources/
      app/
        frontend/
        backend/
      logs/
```

It stages:

- frontend static assets from `frontend/dist`
- backend source files
- a temporary launcher stub
- local package notes

## What it does not do

The script does not:

- download LLM models
- start MCP servers
- run agent tools
- run scan/index/rebuild/restart flows
- sign or notarize the app
- create `.dmg`, `.pkg`, `.exe`, or `.msi`
- copy runtime DBs or workspace runtime state

## Runtime data protection

The packaging script excludes backend runtime data:

- `backend/.ai-workbench/`
- `*.db`
- `*.sqlite`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`

The foundation launcher points runtime DB usage toward an app data path such as:

```text
~/Library/Application Support/AI Private Workspace/workspace.db
```

## Why this is still not the final app

This task proves the bundle shape and lifecycle contract.
The final app should replace the temporary shell launcher with a real Tauri shell/supervisor that can:

- start the backend process safely
- wait for `/health`
- open the UI only after backend readiness
- show user-friendly errors
- write logs to a known local path
- stop only app-owned processes on exit

## Safety rules

- Frontend never executes shell commands.
- Desktop shell may start only app-owned local processes.
- Backend API binds to localhost only by default.
- Runtime data must not be overwritten by generated updates.
- Model downloads stay backend-side, allowlisted, explicit jobs.
- MCP/tool execution stays disabled until sandbox/allowlist execution exists.
