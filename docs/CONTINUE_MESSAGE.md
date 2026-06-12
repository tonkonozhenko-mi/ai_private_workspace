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
