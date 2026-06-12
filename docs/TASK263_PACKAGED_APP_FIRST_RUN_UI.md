# Task 263 — packaged app first-run UI clarity

Task 263 records the first successful packaged macOS backend startup milestone and tightens the UI around the first-run state.

## Local evidence

The packaged `.app` now starts the app-owned frozen backend runtime and writes app-owned logs:

- `curl http://127.0.0.1:8000/health` returns `{"status":"ok"}` after opening the packaged app.
- `~/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log` records manifest resolution, backend PID, and health readiness.
- `~/Library/Application Support/AI Private Workspace/logs/backend.log` records Uvicorn startup and `/workspaces/overview` calls.

## Fixes

- Made workspace overview loading race-safe so an old failed request cannot leave a stale **Backend unavailable** card after a later successful backend startup.
- Added a packaged desktop startup banner so users can see whether the app-owned backend is starting, ready, or failed.
- Added a frontend `/health` wait before loading workspaces in packaged Tauri mode.
- Changed the no-workspace first-run empty state to make clear that an empty app is normal until the user clicks **Add project**.

## Expected first-run behavior

When there are no workspaces yet, the app should show an empty state. That is correct. The important checks are:

- no persistent **Backend unavailable** card after `/health` is ready;
- no automatic scan/index/rebuild/MCP/Agent/model download;
- app-owned logs exist under `~/Library/Application Support/AI Private Workspace/logs`;
- the user can click **Add project** to create the first workspace.
