# Task 248 — App-owned backend startup implementation

Task 248 moves Phase 22 from metadata-only startup gates toward the first real desktop backend lifecycle implementation.

## What changed

- Fixed the Settings crash path around `GET /runtime/v0.1-handoff` with a regression test.
- Added `GET /runtime/app-owned-backend-startup-implementation`.
- Added `scripts/check_tauri_app_owned_backend_startup.sh`.
- Extended the Tauri bridge with narrow app-owned backend lifecycle commands:
  - `get_app_owned_backend_process_status`
  - `start_app_owned_backend_runtime`
  - `stop_app_owned_backend_runtime`

## Startup model

The Tauri supervisor can start only the frozen backend runtime described by:

```text
build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json
```

If the manifest or executable is missing, startup is blocked with a clear error. It does not fall back to arbitrary shell commands or unknown Python environments.

## Safety boundaries

- React/frontend still does not execute shell commands.
- Tauri does not expose generic shell execution.
- The supervisor starts only the executable referenced by the frozen runtime manifest.
- If port `127.0.0.1:8000` is already occupied, startup fails and does not kill anything.
- Shutdown stops only the child process spawned by this app session.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.

## Validation

```bash
scripts/check_tauri_app_owned_backend_startup.sh
```

```bash
cd backend
python -m pytest -q tests/test_app_owned_backend_startup_implementation.py
```

## Remaining work

- Build and smoke the frozen backend locally on macOS.
- Run the Tauri shell against the generated frozen runtime.
- Repeat the same startup lifecycle on Windows.
- Then move to signed app/installer work.
