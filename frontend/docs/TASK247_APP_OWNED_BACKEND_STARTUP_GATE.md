# Task 247 — App-owned backend startup gate

Task 247 fixes the Settings crash on `GET /runtime/v0.1-handoff` and adds the next Phase 22 gate for desktop startup.

## Fix

`/runtime/v0.1-handoff` now returns validation commands using the same response schema declared by the endpoint. This prevents the Settings panel from receiving a `500 Internal Server Error` when it loads the v0.1 handoff block.

## New runtime gate

Added:

- `GET /runtime/app-owned-backend-startup-gate`
- `scripts/check_tauri_app_owned_startup_gate.sh`
- Tauri command `get_app_owned_startup_gate`
- Settings section `App-owned backend startup gate`

The gate is metadata-only. It does not start backend processes.

## Startup contract

Future Tauri startup may proceed only after:

1. frozen backend runtime exists;
2. frozen runtime manifest is valid;
3. developer smoke has passed;
4. the app can record a spawned PID;
5. shutdown stops only the spawned PID;
6. unknown localhost processes are never killed by port;
7. UI opens only after `/health` is ready.

## Safety rules

- Frontend still cannot execute shell commands.
- Tauri does not expose arbitrary shell execution.
- This task does not enable automatic backend startup yet.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.
