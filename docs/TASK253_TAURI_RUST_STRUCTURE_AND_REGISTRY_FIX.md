# Task 253 — Tauri Rust structure and public npm registry guard

## Goal

Fix the local Tauri `cargo check` blocker and prevent internal package registry URLs from leaking into `frontend/package-lock.json`.

## Fixed blockers

- `cargo check --manifest-path src-tauri/Cargo.toml` failed because Cargo expected the declared library `ai_private_workspace_lib`, but the real Tauri implementation lived in `src/main.rs`.
- `frontend/package-lock.json` could contain internal registry URLs if generated in a sandbox/internal environment.

## Implementation

- `frontend/src-tauri/src/main.rs` is now a thin entrypoint:
  - `ai_private_workspace_lib::run();`
- `frontend/src-tauri/src/lib.rs` now owns the Tauri application logic and commands.
- Added `scripts/check_tauri_rust_structure_and_registry.sh`.
- Updated existing Tauri check scripts to inspect `src/lib.rs` for supervisor logic.
- Updated older checks that still expected backend startup to be disabled; startup is now allowed only through the frozen manifest gate.

## Safety

- React/frontend still cannot execute shell commands.
- Tauri startup remains restricted to the app-owned frozen backend runtime.
- Missing frozen manifest blocks startup.
- No `pkill`, `killall`, `taskkill`, `sh -c`, `cmd /C`, or kill-by-port behavior.
- `npm ci` should use public npm registry URLs only.

## Local validation

```bash
scripts/check_tauri_rust_structure_and_registry.sh
scripts/check_tauri_app_owned_backend_startup.sh
scripts/check_tauri_backend_health_readiness.sh
scripts/check_macos_packaged_app_smoke_preflight.sh
```

Then on the developer Mac:

```bash
cd frontend
npm ci
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```
