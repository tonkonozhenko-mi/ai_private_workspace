# Roadmap

This roadmap describes the likely product sequence for AI Private
Workspace. It is directional rather than a release commitment. Safety,
local-first operation, clean architecture, and replaceable adapters should
remain stable constraints throughout every phase.

## Phase 1: Backend Foundation

**Status:** Mostly done

Delivered foundations include:

- FastAPI and Pydantic API boundary.
- Clean Architecture with domain, use cases, ports, and adapters.
- SQLite and in-memory persistence adapters.
- Workspace lifecycle and read models.
- Project scanner and Skill Registry.
- Deterministic DevOps analyzers and reports.
- Command approval, policy, fake runner, and guarded local runner.
- Timeline and timeline backfill.
- Onboarding, assistant profiles, runtime health, and setup guidance.
- Stabilized API inventory, architecture, and configuration documentation.

Remaining work in this phase should focus on maintenance, consistency, and
carefully scoped shared abstractions rather than new foundational rewrites.

## Phase 2: Local AI And RAG Foundation

**Status:** Partially done, working MVP

Delivered foundations include:

- Deterministic indexing and persistent index-status metadata.
- Context search.
- In-memory vector store and optional Qdrant.
- Fake embeddings and optional Ollama embeddings.
- Fake LLM and optional Ollama LLM.
- Source-grounded workspace question answering.
- RAG diagnostics and deterministic quality warnings.
- Embedding-dimension-aware Qdrant collections.

Likely future improvements:

- Better chunking and retrieval strategies.
- Retrieval diagnostics and index inspection.
- Explicit reindex planning and user confirmation.
- More deterministic answer-validation rules.
- RAG evaluation and experiment history.

## Phase 3: Model Management And Experiments

**Status:** In progress

Delivered foundations include:

- Static local model catalog.
- Deterministic model recommendations.
- User-defined JSON catalog loading and validation.
- Reloadable user model catalog.
- Deterministic model switching plans.
- Deterministic model experiment plans.
- Per-request LLM provider/model override foundation.
- Persistent shared-context model experiment runs.
- Deterministic model experiment comparison summaries.
- Append-only manual experiment candidate ratings and preference signals.
- Workspace-scoped historical model performance summaries.
- Workspace-aware model recommendations using catalog and historical feedback.
- Deterministic model recommendation explanations.
- Persisted workspace LLM and embedding-model selection preferences.
- Workspace model selection readiness/status projection.
- Selected-model usage planning for ask, index, and search.
- Ask using the persisted selected LLM through per-request override.
- Selected-embedding indexing and vector-space transition planning.
- Read-only Workspace Models Dashboard aggregation.
- Compact Workspace Models Dashboard Summary projection.
- Read-only Local AI Activation Guide with explicit setup commands.
- Read-only Workspace UI Action Catalog for frontend buttons and cards.

Next planned tasks:

1. Frontend API mapping or real Ollama experiment happy path.
2. Runtime selection validation against installed/available local models.
3. Ollama-backed real experiment polish.
4. AI-assisted experiment evaluator.
3. Runtime model validation against installed Ollama models.
4. Hugging Face metadata importer.

This phase must keep model downloads, provider changes, reindexing, and runtime
configuration changes explicit and user-controlled.

## Phase 4: Frontend And UI Wizard

**Status:** Not started

Likely scope:

- Application home using Workspaces Overview.
- Workspace dashboard and Continue Workspace experience.
- Onboarding wizard for project, assistant, laptop, privacy, and runtime choices.
- Runtime setup and health views.
- Scan, detected-skill, analysis, report, and timeline views.
- RAG question interface with visible sources and quality warnings.
- Command suggestion, proposal, approval, and execution review.
- Model catalog, recommendation, switching-plan, and experiment views.

The frontend should use existing aggregate endpoints where possible and avoid
reimplementing deterministic backend decisions.

## Phase 5: Desktop Packaging And Installer

**Status:** Not started

Likely scope:

- Desktop launcher and process lifecycle management.
- Cross-platform installer or packaged distribution.
- Local data-directory selection.
- Guided Qdrant and Ollama setup.
- Safe environment configuration.
- Backup, restore, diagnostics, and update flows.

Packaging must preserve command approval, local-only defaults, and transparent
runtime configuration.

## Phase 6: Advanced Integrations

**Status:** Later

Possible future work:

- Additional deterministic analyzers and skill packs.
- User-defined skill and analyzer plugins.
- Git provider integrations with explicit permissions.
- Additional vector stores, embedding providers, and LLM providers.
- Hugging Face metadata and model discovery.
- Benchmark and evaluation suites.
- Shared team summaries or exportable project reports.
- Optional cloud integrations behind explicit configuration and consent.

Advanced integrations should remain optional and isolated behind ports and
adapters.

## Packaging clarity update — Task 198

The current macOS launcher is a bridge for developer-safe testing, not the final distribution model. The final product target remains a true desktop app for macOS and Windows: download, double-click, local services start safely, and the UI opens without cloning the repository or manually running backend/frontend scripts.

Model downloads and MCP server setup should be implemented as explicit, user-approved product flows before the final installer: model manager first, MCP install/config/checks second, sandboxed execution later.


## Packaging update after Task 215

- Task 214 locked the real desktop app architecture.
- Task 215 adds the first macOS `.app` package foundation:
  - app bundle skeleton
  - staged frontend assets
  - staged backend source without runtime data
  - temporary launcher stub
  - packaging validation docs

Next larger packaging tasks:
1. App supervisor contract implementation.
2. Tauri shell foundation.
3. macOS release candidate packaging audit.
4. Windows package foundation.
- Task 216 — Desktop supervisor contract: startup states, localhost-only backend lifecycle, logs, safe shutdown, and no kill-by-port behavior. ✅


### Task 217 — macOS app wiring to supervisor contract ✅

The macOS `.app` foundation is now wired to the supervisor contract: app-owned backend startup, health polling, safe port behavior, logs, and packaged UI open.

### Task 218 — backend runtime bundle readiness ✅

Added a backend runtime manifest and package readiness plan so the macOS `.app` foundation can move toward an app-owned backend runtime instead of relying forever on a developer-managed local Python setup.

Next packaging work:
1. Tauri shell scaffold/foundation.
2. Backend runtime freeze decision: PyInstaller, Nuitka, or packaged Python runtime.
3. macOS release candidate packaging audit.
4. Windows package foundation.

### Task 219 — Tauri shell scaffold/foundation ✅

The project now contains a minimal `frontend/src-tauri` scaffold and a validation helper. Next packaging work should implement the Tauri supervisor bridge, then Windows packaging foundation and final release audit.

### Task 220 — Tauri supervisor bridge ✅

Added the source-controlled bridge between Tauri shell and the desktop supervisor lifecycle. The bridge currently exposes read-only supervisor status/log path commands and documents the future app-owned backend startup flow. It does not start backend processes yet.

Next packaging work:
1. Windows packaging foundation.
2. Release candidate audit for source archives, docs, tests, safety, and generated artifacts.
3. Final v0.1 demo/release handoff.

## Task 221 update

Windows packaging foundation is now present. Phase 20 now has macOS foundation, Tauri scaffold/bridge, backend runtime readiness, and Windows lifecycle/installer direction. Remaining v0.1 work should focus on release candidate audit and final handoff/demo package unless new packaging implementation work is intentionally added.


## Task 222 — release candidate audit

Added a read-only release candidate audit endpoint, source archive policy, validation script, UI audit block, and docs for v0.1 handoff readiness.

## Task 223 — v0.1 demo and GitHub handoff ✅

Added the final source-handoff layer for v0.1:

- GitHub-ready `README.md`.
- `docs/V01_DEMO_HANDOFF.md`.
- `docs/V01_RELEASE_NOTES.md`.
- `docs/GITHUB_REPOSITORY_GUIDE.md`.
- `GET /runtime/v0.1-handoff`.
- Settings UI block for demo flow and handoff validation.

The project is now ready for v0.1 source review and GitHub publication. The remaining work after v0.1 is installer-grade desktop packaging: finalized Tauri backend supervisor, bundled backend runtime, signed macOS package, Windows installer, and later sandboxed Agent/MCP execution.
## Task 224 final product-quality pass

- Repository now includes GitHub-ready README, contribution guide, security policy, issue templates, PR template, and CI workflows.
- Frontend received a final Apple-style normalization layer for spacing, typography, controls, card rhythm, and dark mode.
- Product-facing copy now consistently uses AI Private Workspace.
- `docs/assets/product-flow.svg` explains the local-first flow on the GitHub landing page.



## Task 225 — Model Manager real usage flow and render recovery

- Fixed Models screen render resilience.
- Added a clear Choose → Download → Verify → Use model workflow.
- Kept frontend shell execution disabled.


## Task 226 — Models screen fix and Ollama recommendation guide

- Fixed the Models tab hook-order crash caused by conditional rendering before all hooks were registered.
- Added a human-readable Ollama recommendation guide: answer model vs search model, starter/balanced/power user Mac profiles, safe next steps.
- Added `GET /models/ollama-recommendations` for the UI and future onboarding/packaging flows.
- Kept model downloads explicit, backend-owned, and opt-in.


## Task 227 — Model context indexing clarity

Clarified the difference between selecting an embedding/search model and building workspace context with it. The UI now says `Needs context build` when the selected search model is active but the workspace has not been indexed yet.

- Task 228 — Model context build action ✅

## Current Completion Reality

AI Private Workspace is currently a **v0.1 source release candidate**, not a finished v1.0 installer-grade product. The repository is ready for GitHub publication and local demos, while the remaining v1 work is tracked in [`docs/V1_PRODUCT_COMPLETION_ROADMAP.md`](V1_PRODUCT_COMPLETION_ROADMAP.md).

The next practical milestone is **v0.2 desktop runtime**: frozen backend runtime, stronger supervisor lifecycle, persistent local jobs, and a clearer path to signed macOS/Windows installers.


## Task 230 — Source release stabilization ✅

The GitHub publication surface and source archive flow were stabilized:

- README, CONTRIBUTING, SECURITY, `.editorconfig`, `.gitattributes`, GitHub Actions, PR template, and issue forms are present at source root.
- Release audit now treats local runtime/build directories as warnings and fails only on source-tree database files outside ignored paths.
- Source release archive script now archives the current working tree with explicit runtime/build/cache excludes.

Next practical work:
1. Run one full local UI pass after applying the Task 230 archive.
2. Push the v0.1 source RC to GitHub when audit/build checks pass.
3. Continue into v0.2 desktop runtime only after the source RC is stable.

## Task 231 status note

The v0.1 source release candidate now has GitHub publication basics in place: README, contribution/security docs, CI workflows, PR template, issue templates, release audit, source archive script, and repository hygiene docs.

Remaining v1 work is intentionally separate from the source RC:

- frozen backend runtime;
- signed macOS package;
- Windows installer;
- persistent background job storage;
- real sandboxed Agent + MCP execution;
- installer/update lifecycle.

## Task 232 — final status and v1 runway clarity

Added a final status endpoint and Settings UI section so the app clearly says where the project is: v0.1 source RC is ready after local validation, while a true v1.0 installer-grade product still requires roughly 15-25 large tasks across runtime bundling, installers, persistent jobs, and sandboxed Agent/MCP execution.

## Task 235 — v0.1 release gate and roadmap lock ✅

Task 235 adds the final source-release go/no-go layer before the first GitHub push:

- `GET /runtime/v0.1-release-gate` for local audit/build/test/UI smoke-check status.
- `GET /runtime/v0.1-ui-smoke-check` for the final manual browser verification path before GitHub/source archive publication.
- explicit 0-1 large-task estimate for the remaining v0.1 source RC publication step.
- explicit 15-25 large-task estimate for the future v1.0 installer-grade product.
- updated next-task wording so v0.1 does not drift into new feature work before publication.

Current position: Phase 21 is effectively complete as a source release candidate. The next step is local verification and GitHub/source archive publication. Phase 22/v0.2 should start only after v0.1 is published or intentionally frozen.



## Task 237 — v0.1 publication handoff

- Added final read-only publication handoff endpoint and Settings UI section.
- Current roadmap position: Phase 21 effectively complete; v0.1 has 0-1 large task left for manual smoke-check/publication cleanup.
- v1.0 still needs roughly 15-25 large tasks: frozen runtime, signed installers, persistent jobs, MCP runtime, sandboxed Agent execution, update flow, and final QA.
## Task 238 — Phase 22 desktop runtime readiness

Task 238 starts the post-v0.1 direction with `GET /runtime/desktop-runtime-readiness` and a Settings UI section for v0.2 runtime readiness. It keeps v0.1 frozen and defines the next safe implementation order: runtime manifest preflight, Tauri read-only supervisor status, deterministic app-owned backend startup, `/health` readiness, and Windows parity after macOS/Tauri is stable.


### Task 239 — Desktop runtime preflight

Task 239 adds a read-only Phase 22 gate with `GET /runtime/desktop-runtime-preflight`, `scripts/check_desktop_runtime_preflight.sh`, backend tests, and a Settings UI section. It verifies backend entrypoint, runtime manifest, frontend build output, macOS package foundation script, and Tauri scaffold before any real Tauri backend process supervision is implemented. It preserves the rule that frontend code can display/copy commands but never execute shell commands.


Frontend React code must never execute shell commands. It may display and copy commands only.


## Task 240 — Tauri supervisor static gate

- Added a read-only Tauri supervisor static gate for Phase 22.
- Added `GET /runtime/tauri-supervisor-static-gate`.
- Added `scripts/check_tauri_supervisor_bridge.sh`.
- Tauri bridge now exposes status, log paths, and preflight data while keeping backend startup disabled.
- Next larger step: frozen/staged backend runtime and deterministic app-owned startup design.

## Task 241 — Desktop technology decision

- Added `GET /runtime/desktop-technology-decision` to make the Tauri choice explicit and reviewable.
- Tauri is now documented as the current v0.2 candidate, not an irreversible v1.0 decision.
- Alternatives are recorded: Electron, native SwiftUI/WinUI, and browser UI plus launcher scripts.
- Guardrails remain unchanged: frontend cannot execute shell commands, desktop launch cannot auto-start scan/index/MCP/Agent/model downloads, and native commands must stay allowlisted.

### Task 242 — Desktop stack and runtime contract

Phase 22 now has an accepted v0.2 technology direction: open-source/free Tauri + React desktop shell, FastAPI backend, SQLite/Qdrant/Ollama local runtime, and a PyInstaller-first backend freeze spike. The desktop shell still cannot start the backend until runtime staging is deterministic and safety checks pass.


## Phase 22 Update — Task 243

**Task 243 — Staged backend runtime:** done.

The project now has a practical v0.2 runtime staging layer:

- `scripts/stage_backend_runtime.sh`
- `scripts/check_staged_backend_runtime.sh`
- `GET /runtime/staged-backend-runtime-contract`
- Settings UI visibility for the staged runtime contract

This is still not the final v1.0 frozen runtime. It is the bridge from v0.1
source RC toward a real double-click desktop app.

## Phase 22 Update — Task 244

**Task 244 — PyInstaller backend runtime proof-of-concept:** done.

The project now has the first frozen-backend runtime path:

- `backend/packaging/pyinstaller_backend_entrypoint.py`
- `backend/packaging/ai_private_workspace_backend.spec`
- `scripts/build_pyinstaller_backend_runtime.sh`
- `scripts/check_pyinstaller_backend_runtime.sh`
- `GET /runtime/pyinstaller-backend-runtime-contract`
- Settings UI visibility for the PyInstaller backend runtime PoC

This does not claim final installer-grade packaging. It creates a reproducible PoC path toward a frozen backend executable that Tauri can later supervise only after explicit checks pass.

## Phase 22 Update — Task 245

**Task 245 — Frozen backend runtime selection:** done. The desktop runtime path now distinguishes frozen PyInstaller runtime, staged source runtime, and manual developer backend without enabling process startup. The release-candidate audit Settings error was fixed, and frontend build chunking was improved.

## Phase 22 Update — Task 246

**Task 246 — Frozen backend smoke contract:** done. The project now has an explicit developer-only smoke path for the PyInstaller frozen backend runtime:

- `scripts/smoke_frozen_backend_runtime.sh`
- `scripts/check_frozen_backend_smoke_contract.sh`
- `GET /runtime/frozen-backend-smoke-contract`
- Settings UI visibility for the smoke contract

The smoke script starts only the app-owned generated backend executable, waits for `/health`, and stops only the PID it created. Tauri backend startup remains disabled until the next app-owned startup gate.

### Task 247 — app-owned backend startup gate

Phase 22 now has a metadata-only Tauri startup gate. The project can describe the exact conditions for future app-owned backend startup, but automatic backend startup remains disabled until a frozen runtime passes local smoke and PID-owned shutdown is implemented.


## Task 248 — app-owned backend startup implementation

- `GET /runtime/app-owned-backend-startup-implementation` records the first real Tauri backend lifecycle implementation.
- Tauri now has narrow commands to report, start, and stop only the app-owned frozen backend runtime.
- Startup is gated by the frozen backend manifest; missing manifest means blocked startup, not arbitrary fallback.
- Shutdown is PID-owned and no kill-by-port/generic shell execution is allowed.
- Settings crash coverage for `GET /runtime/v0.1-handoff` was added.

### Task 249 — macOS frozen runtime and Tauri smoke runbook ✅

Added the local macOS smoke runbook and check gate for the frozen backend runtime plus Tauri app-owned startup path. This keeps Phase 22 practical: build frozen backend, smoke it, compile-check Tauri, then run the desktop smoke locally before Windows parity or installer work.


## Task 250 — Tauri backend health readiness gate ✅

Task 250 hardens the real Tauri app-owned backend startup implementation. Desktop readiness now requires application-level `/health` HTTP 200 rather than only an open TCP port. This reduces false-positive startup success before packaged macOS/Windows smoke work.

## Task 251 update

- Phase 22 continues with macOS packaged app smoke preflight.
- Frontend now includes Tauri CLI npm scripts and lockfile support so `npm run tauri dev` is reproducible after `npm ci`.
- Next major step: run local macOS frozen backend + Tauri dev/package smoke, then mirror the flow on Windows.


### Task 252 — Packaging toolchain fixes ✅

- Fixed PyInstaller spec path resolution so the backend entrypoint no longer resolves to duplicated `backend/packaging/backend/packaging`.
- Declared `pyinstaller>=6.0,<7.0` in backend requirements.
- Added packaging toolchain prerequisite check and endpoint.
- Documented Rust/Cargo installation for local Tauri smoke.

### Task 253 — Tauri Rust structure and public npm registry guard ✅

The desktop runtime path now has the correct Cargo library layout for Tauri: `main.rs` delegates to `ai_private_workspace_lib::run()` and `lib.rs` owns the app-owned backend lifecycle commands. The release checks also guard against internal package registry URLs in `frontend/package-lock.json`.


* Task 254 — Tauri Rust dependency pin fix + src-tauri target hygiene ✅

## Task 255 — Tauri icon assets ✅

Fixed the local Tauri `cargo check` blocker caused by missing/non-RGBA icon assets. Added required RGBA PNG placeholder icons, removed an unused Rust import, added `scripts/check_tauri_icon_assets.sh`, and exposed `GET /runtime/tauri-icon-assets` for Settings/API readiness. Next local check: `scripts/check_tauri_icon_assets.sh && cd frontend && cargo check --manifest-path src-tauri/Cargo.toml`.

## Task 256 — Tauri dev smoke success ✅

`npm run tauri dev` now works locally on macOS after fixing the Rust library structure, npm lockfile registry hygiene, Rust dependency pinning, and Tauri RGBA icon assets. Phase 22 is no longer only scaffold/preflight work: the desktop shell can start in development mode. Next step is packaged macOS smoke with a locally built PyInstaller backend runtime, then Windows parity.
