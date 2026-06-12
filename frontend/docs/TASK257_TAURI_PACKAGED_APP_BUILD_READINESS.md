# Task 257 — Tauri packaged app build readiness

## Goal

Move the desktop runtime work from successful `npm run tauri dev` toward a real packaged macOS app smoke using `npm run tauri:build`.

## What changed

- Added `.idea/` to `.gitignore`.
- Confirmed `.DS_Store` stays ignored.
- Kept `frontend/src-tauri/target/` ignored and excluded from source archives.
- Enabled Tauri app bundling for the packaged smoke path.
- Added Tauri package icon configuration.
- Added frozen backend runtime as a Tauri package resource:
  - `../../build/desktop/frozen-backend-runtime`
- Added packaged resource lookup paths in the Tauri supervisor:
  - `../Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json`
  - `../../Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json`
- Added packaged build preflight script:
  - `scripts/check_tauri_packaged_app_build.sh`
- Added backend endpoint:
  - `GET /runtime/tauri-packaged-app-build-readiness`

## Local packaged smoke path

```bash
./scripts/check_tauri_packaged_app_build.sh
./scripts/build_pyinstaller_backend_runtime.sh
./scripts/check_pyinstaller_backend_runtime.sh
./scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm run tauri:build
```

Then open the generated macOS app bundle and verify:

- app opens;
- app-owned backend starts only from the frozen runtime manifest;
- backend readiness waits for `GET /health` HTTP 200;
- logs/data are written to app-owned user directories;
- no scan/index/rebuild/MCP/Agent/model downloads start automatically;
- app shutdown does not kill unrelated processes.

## Safety rules

- React/frontend still does not execute shell commands.
- Tauri may start only the app-owned frozen backend runtime.
- Missing frozen manifest means blocked startup, not fallback to arbitrary commands.
- No `pkill`, `killall`, `taskkill`, or kill-by-port behavior.
- Runtime data/logs must stay outside the app bundle.
