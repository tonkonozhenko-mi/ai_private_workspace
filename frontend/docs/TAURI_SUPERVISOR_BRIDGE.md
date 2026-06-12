# Tauri supervisor bridge

Task 220 adds the bridge contract between the Tauri desktop shell and the backend supervisor lifecycle.

The goal is still the product-level desktop experience:

1. User double-clicks the packaged app.
2. Tauri shell starts.
3. App-owned backend starts on `127.0.0.1`.
4. Tauri waits for `/health`.
5. The UI opens only after the backend is ready.

## What changed

- Added `GET /runtime/tauri-supervisor-bridge`.
- Added read-only Tauri commands in `frontend/src-tauri/src/main.rs`:
  - `get_supervisor_status`
  - `get_supervisor_log_paths`
- Updated `scripts/prepare_tauri_shell_scaffold.sh` to validate the bridge commands.
- Added Settings UI visibility for the bridge states and safety rules.

## Safety boundaries

- React never executes shell commands.
- The Tauri bridge is read-only in this task.
- Tauri does not yet start backend processes.
- No scan, index, rebuild, MCP, agent workflow, or model download starts on launch.
- Future backend startup must only start the app-owned backend runtime.
- Unknown processes using a port must not be killed.

## Current limitation

This is not the final signed macOS package. The bridge is a source-controlled foundation for the next packaging step, where the native shell can own backend startup after runtime bundling is stable.
