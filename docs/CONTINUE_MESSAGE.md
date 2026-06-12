# Continue message — AI Private Workspace

I continue the `ai_workspace` project — a local-first AI Private Workspace product.

Working style:

- Continue step-by-step through Tasks.
- User uploads a root-preserving zip of the whole project.
- ChatGPT modifies files and returns an updated root-preserving zip + patch.
- Keep the root structure: `backend/`, `frontend/`, `docs/`, `scripts/`, `.github/`, root docs/config files.
- Do not include runtime/build data in archives: `backend/.ai-workbench`, `.venv`, `node_modules`, `dist`, `build/`, caches, `*.db`, `*.sqlite`, `*.sqlite3`, `*.tsbuildinfo`.
- Answer in Russian, concise, with exact commands.
- Prefer larger useful tasks instead of many tiny tasks.
- Preserve safety rules.

Hard safety rules:

- Frontend/React never executes shell commands.
- Frontend does not auto-start scan/index/rebuild/restart/model downloads/MCP/Agent.
- Backend clean architecture: core without FastAPI/sqlite3; adapters in infrastructure.
- Model downloads are backend-side, opt-in, allowlisted, explicit approval only.
- MCP servers/tools do not start automatically.
- Agent workflows remain approval-gated; no automatic tool execution.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.
- Tauri may start only an app-owned backend executable from the frozen runtime manifest.
- Shutdown must be PID-owned; never kill unknown processes by port.

Current roadmap status:

- Phase 21 / v0.1 source RC: effectively complete.
- Phase 22 / v0.2 desktop runtime foundation: strongly in progress.
- Current latest task: Task 249 — macOS frozen runtime and Tauri smoke runbook.
- v0.1 publication remaining: 0–1 large task, mostly local manual UI smoke-check + source archive + GitHub push.
- v1.0 remaining: about 7–12 large tasks, depending on PyInstaller/Tauri/macOS/Windows issues found locally.

Recent important tasks:

- Task 243: staged backend runtime layout.
- Task 244: PyInstaller backend runtime PoC.
- Task 245: fixed Settings release audit crash, added frozen runtime selection, fixed frontend chunk warning.
- Task 246: frozen backend smoke contract.
- Task 247: fixed Settings `/runtime/v0.1-handoff` crash, added app-owned backend startup gate.
- Task 248: real gated Tauri app-owned backend startup implementation.
- Task 249: macOS frozen runtime + Tauri smoke runbook/checks + updated continue message.

Current desktop stack decision:

- Tauri + React + TypeScript + Vite for cross-platform desktop shell.
- FastAPI backend.
- PyInstaller first for frozen backend runtime.
- SQLite/Qdrant/Ollama local runtime pieces.
- Open-source/free, macOS + Windows, lightweight, maintainable, production-grade direction.
- Fallbacks remain possible if Tauri/PyInstaller becomes too painful: Nuitka, packaged Python runtime, Electron.

Next recommended task:

Task 250 — local smoke feedback/fixes. If the user ran local commands and shows errors, fix them first. Otherwise add Windows frozen runtime parity checks and keep moving toward installer-grade v1.0.

Task 250 — Tauri backend health readiness gate ✅

- Added `/runtime/app-owned-backend-health-readiness`.
- Added `scripts/check_tauri_backend_health_readiness.sh`.
- Tauri no longer treats open TCP port as readiness; startup success requires HTTP `GET /health` 200.
- Failed readiness cleanup stops only the child process started by this app session.
- No kill-by-port, no generic shell execution, no scan/index/rebuild/MCP/Agent/model downloads on launch.
- Next recommended large task: local macOS cargo/PyInstaller/Tauri smoke fixes, then Windows parity.

Task 251 — macOS packaged app smoke preflight ✅

- Added Tauri CLI npm wiring:
  - `npm run tauri dev`
  - `npm run tauri:dev`
  - `npm run tauri:build`
- Added `@tauri-apps/cli` to frontend devDependencies and package-lock.
- Added backend endpoint `GET /runtime/macos-packaged-app-smoke-preflight`.
- Added Settings section “macOS packaged app smoke preflight”.
- Added script `scripts/check_macos_packaged_app_smoke_preflight.sh`.
- Added doc `docs/TASK251_MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md`.
- Next: local macOS smoke should run `scripts/build_pyinstaller_backend_runtime.sh`, `scripts/smoke_frozen_backend_runtime.sh`, `cargo check`, and `npm run tauri dev`.


- Task 252 fixed local packaging blockers: added `pyinstaller>=6.0,<7.0`, fixed PyInstaller spec path resolution, added `scripts/check_packaging_toolchain_prerequisites.sh`, and documented Cargo install (`brew install rust` or rustup).

## Latest update — Task 253

Task 253 fixed the Tauri Rust manifest structure and npm registry hygiene:

- `frontend/src-tauri/src/main.rs` is now a thin entrypoint that calls `ai_private_workspace_lib::run();`.
- `frontend/src-tauri/src/lib.rs` contains the real Tauri app-owned backend lifecycle commands.
- Added `scripts/check_tauri_rust_structure_and_registry.sh`.
- Updated Tauri check scripts to inspect `src/lib.rs` instead of expecting all logic in `src/main.rs`.
- Added a guard against internal npm registry URLs in `frontend/package-lock.json`.
- Existing safety rules remain: no frontend shell execution, no kill-by-port, startup only via frozen manifest, and no scan/index/rebuild/MCP/Agent/model downloads on launch.

Current next local checks:

```bash
scripts/check_tauri_rust_structure_and_registry.sh
scripts/check_macos_packaged_app_smoke_preflight.sh
cd frontend
npm ci
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```


* Task 254 — Tauri Rust dependency pin fix + src-tauri target hygiene ✅

## Task 255 — Tauri icon assets ✅

Fixed the local Tauri `cargo check` blocker caused by missing/non-RGBA icon assets. Added required RGBA PNG placeholder icons, removed an unused Rust import, added `scripts/check_tauri_icon_assets.sh`, and exposed `GET /runtime/tauri-icon-assets` for Settings/API readiness. Next local check: `scripts/check_tauri_icon_assets.sh && cd frontend && cargo check --manifest-path src-tauri/Cargo.toml`.

## Latest update — Task 256

Task 256 records the first successful local Tauri dev smoke:

- User reported `npm run tauri dev` now works on macOS.
- Added `GET /runtime/tauri-dev-smoke-readiness`.
- Added `scripts/check_tauri_dev_smoke_readiness.sh`.
- Added tests for the readiness endpoint and Tauri source hygiene.
- Safety remains unchanged: no frontend shell execution, no kill-by-port, frozen manifest gate, `/health` readiness, and no scan/index/rebuild/MCP/Agent/model downloads on launch.

Current roadmap:

- Phase 21 / v0.1 source RC: effectively complete.
- Phase 22 / v0.2 desktop runtime: strongly in progress and now locally smoke-proven in Tauri dev mode.
- Remaining to 100% v1.0: roughly 5–8 large tasks.

Next recommended task:

Task 257 — packaged macOS app smoke preparation/build hardening. Focus on `npm run tauri:build`, frozen backend runtime placement, bundled resource paths, and app-owned logs/data validation.

Task 257 — Tauri packaged app build readiness ✅

- Added `.idea/` and `.DS_Store` repository hygiene.
- Kept `frontend/src-tauri/target/` ignored and excluded from release archives.
- Enabled Tauri bundle config for packaged app smoke.
- Declared frozen backend runtime as a packaged Tauri resource.
- Added packaged Resources manifest lookup in Tauri supervisor.
- Added `scripts/check_tauri_packaged_app_build.sh`.
- Added endpoint `GET /runtime/tauri-packaged-app-build-readiness` and Settings UI section.

Next local smoke path:

```bash
./scripts/check_tauri_packaged_app_build.sh
./scripts/build_pyinstaller_backend_runtime.sh
./scripts/check_pyinstaller_backend_runtime.sh
./scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm run tauri:build
```

Then open the generated macOS app and verify app-owned backend startup, `/health`, logs/data paths, and no auto scan/index/rebuild/MCP/Agent/model downloads.

### Task 258 — frozen backend startup diagnostics ✅

After local packaged-app work, `npm run tauri:build` succeeded, but `scripts/smoke_frozen_backend_runtime.sh` showed the frozen backend process did not make `/health` ready. Task 258 hardened the PyInstaller entrypoint/spec and smoke script: explicit import self-check, broader hidden imports, app-owned smoke data directory, early-process-exit detection, and log-tail printing on failure. Next local step is to rebuild the frozen backend and rerun the smoke script to see either a clean `/health` pass or a concrete backend traceback.
* Task 259 — macOS packaged app smoke result ✅


- Task 260 — packaged app frontend bootstrap: React now invokes the narrow Tauri app-owned backend startup command before workspace HTTP API calls, fixing the packaged `.app` case where UI opened but backend/logs were missing. ✅


## Task 261 — packaged app Tauri bridge fix and npm install-script policy ✅

- Enabled `app.withGlobalTauri = true` so packaged React can invoke the Tauri bridge.
- Added fallback detection for `__TAURI_INTERNALS__.invoke`.
- Added `tauriBridgeDiagnostic()` to surface packaged bridge state in the UI.
- Added explicit npm `allowScripts` policy for `esbuild` and `fsevents`.
- Added `scripts/check_npm_supply_chain_policy.sh`.
- Next local check: rebuild frozen backend, rebuild `.app`, open packaged app, verify `/health` and app-owned logs.

## Task 262 update

Task 262 fixed the packaged macOS app backend startup diagnostics and full backend pytest stability.

Important updates:
- Full backend pytest is now isolated from the developer shell runtime by setting deterministic fake runtime defaults in `backend/tests/conftest.py`.
- Tauri packaged runtime discovery now recursively searches bundled `Contents/Resources` for `AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json`.
- Tauri writes `desktop-supervisor.log` before backend startup, so missing bundled runtime/manifests are diagnosable even when `backend.log` does not exist.
- Full backend test result in sandbox: `538 passed, 3 skipped`.

Next local check:
```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

Then inspect:
```bash
curl http://127.0.0.1:8000/health
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log"
```

## Latest checkpoint after Task 263

Task 263 fixed packaged first-run UI clarity after the first successful `.app` backend startup milestone. The packaged macOS app now starts the app-owned frozen backend runtime on the user's Mac: `/health` returns ok and logs appear under `~/Library/Application Support/AI Private Workspace/logs`.

Important: if the app has zero workspaces, the main screen being mostly empty is expected. It should show a clear no-projects state and the user should click **Add project**. This is not a backend failure as long as `/health` is ok and logs exist.

Task 263 frontend fixes:
- race-safe workspace overview loading with `loadWorkspacesRequestIdRef`;
- frontend waits for backend `/health` before workspace loading in Tauri mode;
- stale backend errors are cleared after successful readiness;
- visible desktop startup banner;
- first-run empty state says "No projects yet" and explains the desktop backend is running.

New check:
- `scripts/check_packaged_app_first_run_ui.sh`

Current status:
- Phase 21 / v0.1 source RC: effectively complete.
- Phase 22 / v0.2 desktop runtime: macOS packaged runtime is very close to closed.
- Estimated remaining to 100% v1.0: around 4–6 large tasks.

## Latest state after Task 264

Task 264 fixed packaged app SQLite/CORS bootstrap:
- backend accepts `APP_DATA_DIR` / `WORKSPACE_DB_PATH` and legacy `AI_WORKSPACE_APP_DATA_DIR` / `AI_WORKBENCH_DB_PATH`;
- SQLite repository creates DB parent directories before connecting;
- Tauri passes canonical app-owned DB path under `~/Library/Application Support/AI Private Workspace/data/workspaces.db`;
- packaged-webview CORS preflight is allowed for local/Tauri origins;
- if port 8000 is already healthy, Tauri reuses it without taking ownership instead of showing a startup failure.

Latest checks:
- `scripts/check_packaged_app_sqlite_cors_bootstrap.sh` passed.
- `cd backend && python3 -m pytest -q` → `545 passed, 3 skipped`.
- `cd frontend && npm ci && npm run build` passed.
- `./scripts/audit_release_candidate.sh` passed with expected local warnings.

Next gate: rebuild frozen backend + Tauri app, open packaged `.app`, create first project, then test onboarding/scan/index/ask inside the packaged desktop app.

## Latest state after Task 265

Task 265 hardens the packaged macOS SQLite workspace API path after the
remaining `sqlite3.OperationalError: unable to open database file` report:

- Tauri bundle identifier is `local.ai-private-workspace` without the
  discouraged `.app` suffix.
- Tauri creates `~/Library/Application Support/AI Private Workspace/data` and
  passes/logs the exact `workspaces.db` path.
- Frozen PyInstaller fallback paths use app-owned Application Support data, not
  `.app/Contents/Resources`.
- Backend settings support canonical and legacy path variables and ignore
  blank canonical values.
- SQLite workspace initialization/connect errors include the resolved path.
- Packaged readiness requires both `/health` and `/workspaces/overview`.
- New gate: `scripts/check_packaged_app_workspace_api_smoke.sh`.

Exact next local gate:

```bash
./scripts/audit_release_candidate.sh
./scripts/check_packaged_app_workspace_api_smoke.sh
cd backend && python3 -m pytest -q
cd ../frontend && npm ci && npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

Then verify the app-owned data/log directories, `/health`,
`/workspaces/overview`, first-run `No projects yet`, and explicit **Add
project**. Desktop launch still never starts scan, index, rebuild, MCP, Agent,
or model downloads.

Latest local smoke detail:

- fresh frozen backend workspace API smoke passed on owned alternate port 8011;
- it created `build/desktop/task265-smoke-logs/app-data/data/workspaces.db`;
- rebuilt `.app` logged the correct Application Support DB path;
- the rebuilt supervisor correctly refused to reuse or kill an older orphaned
  packaged backend that returned `/health` 200 and `/workspaces/overview` 500;
- after stopping only the exact old app-owned PID recorded by the supervisor,
  the rebuilt `.app` passed `/health`, `/workspaces/overview`, packaged CORS
  preflight, and real `POST /workspaces` creation;
- `~/Library/Application Support/AI Private Workspace/data/workspaces.db`
  exists and the created workspace appears in overview.
- graceful packaged-app quit now stops the PyInstaller bootloader and internal
  server child; port 8000 is free afterward and no orphan product process
  remains.

## Latest state after Task 266

Task 266 proves and guards the first complete packaged macOS product flow:

- open `.app`;
- create/select workspace;
- explicitly scan;
- explicitly build search context;
- explicitly Ask with a selected provider;
- quit/reopen and verify SQLite persistence.

New gate and runbook:

```bash
./scripts/check_packaged_app_full_flow_contracts.sh
cat docs/TASK266_PACKAGED_FULL_PRODUCT_FLOW_SMOKE.md
```

The packaged deterministic smoke uses `VECTOR_STORE=memory`,
`EMBEDDING_PROVIDER=fake`, and selected `fake/fake-llm`. Scan/index metadata
persists in SQLite. Memory-vector chunks do not persist after backend restart,
so Ask must show the clear `index_metadata_exists_but_no_chunks_found`
diagnostic until the user explicitly rebuilds context. Qdrant remains the
persistent vector-store path.

Next recommended task: Windows packaged-runtime full-flow parity, then macOS
signing/notarization and installer-grade distribution.


Task 267 status: packaged persistent RAG was added. The `.app` should pass VECTOR_STORE=sqlite and VECTOR_STORE_PATH under `~/Library/Application Support/AI Private Workspace/data/vector_store.db`; memory remains only for dev/tests. Next check: run packaged smoke and confirm Ask works after quit/reopen without reindex.

## Task 269 — Daily-use MVP polish

The packaged MVP now includes a clearer daily-use path:

- Overview shows a `Use it now` readiness panel.
- The primary action changes between scan, build context, fix model setup, and ask.
- Ask reloads the latest conversation for the selected workspace, so restart feels continuous.
- A new `scripts/check_daily_use_mvp_contracts.sh` guard verifies this UX and safety contract.

Safety remains unchanged: the frontend does not execute shell commands and scan/index/ask do not start automatically on mount.
