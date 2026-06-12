# Task 261 — Packaged app Tauri bridge fix and npm install-script policy

## Why this task exists

The frozen backend runtime smoke passed and `npm run tauri:build` produced a macOS `.app`, but opening the packaged app showed the React UI without starting the app-owned backend. `curl http://127.0.0.1:8000/health` failed and the app-owned log directory did not exist.

The packaged frontend used the injected Tauri invoke bridge, but the Tauri config did not explicitly enable the global bridge for the packaged webview. As a result, the UI behaved like a static browser build and never invoked `start_app_owned_backend_runtime`.

A second local warning appeared during `npm ci`: npm reported install scripts for `esbuild` and `fsevents` that were not covered by an explicit allowScripts policy.

## What changed

- Enabled the packaged Tauri invoke bridge with `app.withGlobalTauri = true` in `frontend/src-tauri/tauri.conf.json`.
- Hardened `frontend/src/desktopRuntime.ts` to detect:
  - `window.__TAURI__.core.invoke`
  - `window.__TAURI__.tauri.invoke`
  - `window.__TAURI_INTERNALS__.invoke`
- Added `tauriBridgeDiagnostic()` so the UI can surface whether the packaged bridge is available.
- Added explicit npm `allowScripts` policy for the known install scripts:
  - `esbuild`
  - `fsevents`
- Added `scripts/check_npm_supply_chain_policy.sh`.
- Extended packaged app bootstrap checks to verify the Tauri bridge config, frontend diagnostics, and npm policy.

## Safety rules preserved

- React still does not execute shell commands.
- React only invokes narrow Tauri commands exposed by the app-owned backend lifecycle bridge.
- Tauri starts only the frozen backend runtime selected by the manifest.
- Startup success still requires HTTP `/health` readiness.
- Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.
- Unknown processes on port 8000 are not killed.

## Local validation

```bash
scripts/check_packaged_app_frontend_bootstrap.sh
scripts/check_npm_supply_chain_policy.sh
scripts/check_tauri_packaged_app_build.sh
```

Then rebuild the runtime and app:

```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm ci
npm run build
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

After opening the app:

```bash
curl http://127.0.0.1:8000/health
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log"
```
