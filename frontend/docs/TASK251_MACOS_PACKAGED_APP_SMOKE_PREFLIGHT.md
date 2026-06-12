# Task 251 — macOS packaged app smoke preflight

## Goal

Move Phase 22 from runbook-only Tauri smoke toward a reproducible local macOS packaged-app smoke path.

This task does **not** make a final signed installer. It prepares the local developer flow that must pass before signing/DMG work:

1. install frontend dependencies with Tauri CLI;
2. build the frontend;
3. build the frozen backend runtime;
4. smoke the frozen backend directly;
5. run Tauri dev smoke;
6. later run Tauri build/package smoke.

## Why this task was needed

Earlier tasks documented `npm run tauri dev`, but `frontend/package.json` did not yet expose a Tauri CLI script or include `@tauri-apps/cli` in the frontend lockfile. That means a developer following the runbook could hit a missing command even though the Rust scaffold existed.

Task 251 fixes that by adding explicit npm scripts and lockfile support.

## Added scripts

Frontend:

```bash
cd frontend
npm run tauri dev
npm run tauri:dev
npm run tauri:build
```

Repository check:

```bash
scripts/check_macos_packaged_app_smoke_preflight.sh
```

## Local macOS smoke path

From the repository root:

```bash
./scripts/audit_release_candidate.sh
./scripts/check_macos_packaged_app_smoke_preflight.sh
./scripts/check_tauri_backend_health_readiness.sh
./scripts/check_tauri_app_owned_backend_startup.sh
```

Build and smoke the frozen backend:

```bash
./scripts/build_pyinstaller_backend_runtime.sh
./scripts/check_pyinstaller_backend_runtime.sh
./scripts/smoke_frozen_backend_runtime.sh
```

Check and run Tauri:

```bash
cd frontend
npm ci
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```

Optional package smoke, after dev smoke is stable:

```bash
npm run tauri:build
```

## Pass criteria

- `npm ci` installs the Tauri CLI from `package-lock.json`.
- `npm run build` passes without the old large chunk warning.
- frozen backend manifest is generated locally.
- frozen backend `/health` smoke passes.
- Tauri starts only the app-owned frozen backend runtime.
- Tauri reports readiness only after HTTP `GET /health` returns `200`.
- closing/stopping the app stops only the PID it started.

## Safety rules

- React/frontend still does not execute shell commands.
- Tauri exposes only narrow app-owned backend lifecycle commands.
- No generic shell execution is exposed to the UI.
- No `pkill`, `killall`, `taskkill`, or kill-by-port behavior.
- If port `8000` is occupied, startup fails and does not kill anything.
- Desktop launch must not run scan, index, rebuild, MCP, Agent, or model downloads.

## Next step

After this preflight passes locally, the next large step should be packaged macOS app smoke hardening: verify `tauri build` output, app resources, frozen runtime placement, logs path, and close/shutdown behavior.
