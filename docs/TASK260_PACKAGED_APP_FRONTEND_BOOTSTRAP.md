# Task 260 — Packaged app frontend bootstrap

The packaged macOS app opened the bundled React UI, but the backend was not started. Evidence:

- `curl http://127.0.0.1:8000/health` failed after opening the `.app`.
- `~/Library/Application Support/AI Private Workspace` did not exist.
- The standalone frozen backend smoke passed, so the issue was not the PyInstaller runtime itself.

## Root cause

The packaged frontend immediately tried HTTP API calls against `http://127.0.0.1:8000`, but it did not invoke the Tauri app-owned backend startup command first.

## Fix

Added `frontend/src/desktopRuntime.ts` and wired `App.tsx` to start the app-owned backend through the narrow Tauri command bridge before loading workspaces.

Safety remains unchanged:

- React does not execute shell commands.
- React only invokes the narrow `start_app_owned_backend_runtime` Tauri command.
- Tauri starts only the frozen backend runtime selected by manifest.
- Startup success still requires HTTP `/health` 200.
- Launch does not start scan, index, rebuild, MCP, Agent, or model downloads.

## Local validation

```bash
scripts/check_packaged_app_frontend_bootstrap.sh
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm ci
npm run build
npm run tauri:build
open src-tauri/target/release/bundle/macos/AI\ Private\ Workspace.app
```

Then verify:

```bash
curl http://127.0.0.1:8000/health
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"
```
