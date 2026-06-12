# Task 262 — Packaged app backend startup diagnostics and full test stabilization

## Problem

The macOS packaged app opened the React UI, but the app-owned backend did not start:

- `curl http://127.0.0.1:8000/health` failed.
- The app-owned logs directory existed but had no `backend.log`.
- The standalone frozen backend smoke passed, so the failure was in packaged app runtime discovery/startup, not in the PyInstaller backend itself.

A full backend test run also failed when the developer shell was configured for the real Ollama/Qdrant runtime instead of the deterministic fake test runtime.

## Changes

- Added deterministic backend test defaults in `backend/tests/conftest.py` so full `pytest` is isolated from local shell runtime settings.
- Hardened Tauri packaged runtime discovery:
  - direct Resources manifest candidates are still checked;
  - the app now recursively searches bundled `Contents/Resources` for `AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json`;
  - duplicate candidates are de-duplicated.
- Added `desktop-supervisor.log` diagnostics before the backend process starts, so missing manifest/resource errors are visible even when `backend.log` does not exist yet.
- Added supervisor logging for:
  - startup command invocation;
  - candidate manifest paths;
  - resolved backend executable;
  - occupied port refusal;
  - child PID creation;
  - `/health` timeout cleanup;
  - healthy startup.
- Updated packaged app checks to require recursive Resources search and supervisor diagnostics.
- Updated stale tests that still expected the old pre-startup Tauri scaffold.
- Preserved safety rules:
  - no generic shell execution;
  - no `pkill`/`killall`/`taskkill`/kill-by-port;
  - shutdown only targets the child process started by the app;
  - desktop launch still does not start scan/index/rebuild/MCP/Agent/model downloads.

## Local verification

```bash
cd backend
python3 -m pytest -q
```

Expected:

```text
538 passed, 3 skipped
```

```bash
scripts/check_packaged_app_frontend_bootstrap.sh
scripts/check_tauri_packaged_app_build.sh
scripts/check_tauri_app_owned_backend_startup.sh
scripts/check_npm_supply_chain_policy.sh
```

Expected: `0 blockers`.

```bash
cd frontend
npm ci
npm run build
```

Expected: build passes.

```bash
./scripts/audit_release_candidate.sh
```

Expected: audit passes with only local build/cache warnings.

## Next packaged smoke

```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh

cd frontend
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

Then check:

```bash
curl http://127.0.0.1:8000/health
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log"
```
