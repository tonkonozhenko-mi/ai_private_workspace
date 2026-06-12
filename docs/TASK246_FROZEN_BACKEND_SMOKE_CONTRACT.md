# Task 246 — Frozen backend smoke contract

Task 246 adds the explicit developer-only smoke path for the frozen backend runtime.

## What changed

- Added `scripts/smoke_frozen_backend_runtime.sh`.
- Added `scripts/check_frozen_backend_smoke_contract.sh`.
- Added `GET /runtime/frozen-backend-smoke-contract`.
- Added Settings UI visibility for the smoke contract.
- Added backend test coverage.

## Contract

The smoke script is a manual developer command. It may start only the generated
app-owned frozen backend executable from `build/desktop/frozen-backend-runtime`.
It refuses to run without the frozen runtime manifest, checks that the configured
localhost port is free, waits for `/health`, and stops only the PID it created.

It must never kill unknown localhost processes by port or name.

## Safety rules

- Frontend/React cannot execute the smoke script.
- Desktop launch still cannot trigger scan, index, rebuild, MCP, Agent, or model downloads.
- Tauri backend startup remains disabled until a later task enables it behind manifest and smoke gates.
- Generated frozen runtime outputs remain under `build/desktop` and must not be committed.

## Commands

```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
scripts/check_frozen_backend_smoke_contract.sh
```

## Roadmap position

Phase 22 is now past static runtime selection and has a practical local smoke gate.
The next step is Tauri app-owned backend startup behind this manifest/smoke contract.
