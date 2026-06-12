# Task 264 — Packaged app SQLite data bootstrap and Tauri CORS fix

## Summary

Task 264 fixes the first packaged macOS app flow after the app-owned backend successfully starts.

The backend was healthy at `/health`, but workspace overview and project creation failed because the packaged runtime did not pass the canonical app-owned SQLite settings expected by the backend. The UI also hit CORS preflight failures for packaged-webview origins.

## Changes

- Backend settings now accept both canonical and legacy desktop env names:
  - `APP_DATA_DIR`
  - `WORKSPACE_DB_PATH`
  - `AI_WORKSPACE_APP_DATA_DIR`
  - `AI_WORKBENCH_DB_PATH`
- The SQLite repository now creates the database parent directory before connecting.
- CORS now includes local/Tauri packaged origins and a local/Tauri regex.
- Tauri backend startup now passes canonical app-owned DB paths under:
  - `~/Library/Application Support/AI Private Workspace/data/workspaces.db`
- Tauri still passes legacy env aliases for compatibility with older scripts.
- If port `8000` is already busy but `/health` is healthy, Tauri reuses that local backend without taking ownership instead of showing a startup failure.
- Added a static check script:
  - `scripts/check_packaged_app_sqlite_cors_bootstrap.sh`
- Added regression tests for:
  - SQLite parent directory creation
  - Tauri env wiring
  - Tauri/local CORS preflight
  - legacy desktop env aliases

## Safety

This does not add arbitrary shell execution. The frontend still cannot execute shell commands. Tauri can only start or stop the app-owned frozen backend process through the narrow supervisor command path.

## Local packaged smoke

```bash
scripts/check_packaged_app_sqlite_cors_bootstrap.sh
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
```

```bash
cd frontend
npm ci
npm run build
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

After opening the app:

```bash
curl http://127.0.0.1:8000/health
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"
ls -la "$HOME/Library/Application Support/AI Private Workspace/data"
```
