# Task 256 — Tauri dev smoke success

Task 256 records the first confirmed local Tauri development-shell success after the Rust structure, dependency pin, public npm registry, and RGBA icon blockers were fixed.

## What changed

- Added `GET /runtime/tauri-dev-smoke-readiness`.
- Added `scripts/check_tauri_dev_smoke_readiness.sh`.
- Added tests for the readiness endpoint and Tauri source hygiene.
- Updated project checkpoint, roadmap, API inventory, and continue message.

## Confirmed local milestone

The user reported that `npm run tauri dev` now starts successfully on macOS. This is the first practical confirmation that the Tauri shell scaffold is viable locally, not only present in source code.

## Safety boundaries preserved

- React/frontend still does not execute shell commands.
- Tauri startup remains limited to app-owned backend runtime execution.
- Startup success requires frozen manifest and HTTP `GET /health` 200.
- No kill-by-port, `pkill`, `killall`, or `taskkill` behavior is allowed.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.

## Local checks

```bash
scripts/check_tauri_dev_smoke_readiness.sh
cd frontend
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```

## Next step

Move from dev-shell smoke toward packaged macOS app smoke:

```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm run tauri:build
```

After macOS packaged smoke is stable, mirror the same runtime contract on Windows.
