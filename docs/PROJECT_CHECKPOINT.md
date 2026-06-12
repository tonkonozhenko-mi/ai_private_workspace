# AI Private Workspace — Project Checkpoint

Last updated: Task 236

## Working style

- Work continues through numbered tasks.
- User uploads a root-preserving zip with `backend/`, `frontend/`, `docs/`, `scripts/`, `pytest.ini`, `.gitignore`.
- Assistant returns a root-preserving updated zip and patch.
- Runtime data must never be included in generated archives.
- Apply generated archives with safe excludes for `backend/.ai-workbench`, `*.db`, `*.sqlite`, `.venv`, `node_modules`, `dist`, and `*.tsbuildinfo`.
- Frontend must never execute shell commands. It may only display/copy commands.
- Scan, index, rebuild, runtime changes, backups, restore, update apply, MCP server start, and tool execution remain explicit user actions.

## Roadmap status

1. Backend foundation — done
2. RAG / Qdrant / Ollama — done
3. Model management — done
4. Frontend MVP — done
5. UI polish — done
6. Real local AI happy path — done
7. Model experiments UI — done
8. Apple/native visual redesign — done
9. Beginner-friendly UX layer — done
10. Settings and personalization — done
11. Real Workspace Onboarding Flow — done
12. File selection / indexing control — done
13. Advanced skill profiles — done
14. Persistent conversations and answer history — done
15. Project reports and documentation generation — done
16. Production hardening / packaging / desktop-like experience — mostly done
17. Optional company branding / sharing / final polish — in progress
18. Safe agent and MCP workflow — started as an extension to the original roadmap

## Recent tasks

- Task 175: local data safety diagnostics
- Task 176: startup checklist and safer local scripts
- Task 177: backup/restore and migration safety workflow
- Task 178: runtime troubleshooting assistant
- Task 179: generated update workflow hardening
- Task 180: desktop startup and last workspace restore
- Task 181: production readiness checklist
- Task 182: branding presets and report share kit
- Task 183: Apple-style light/dark UI polish
- Task 184: dark/light visual QA and consistency pass
- Task 185: final UX QA, typography alignment, demo mode, and visual consistency
- Task 186: strict dark/light visual QA and alignment
- Task 187: safe agent capability awareness
- Task 188: manual agent workflow tracking
- Task 189: MCP server registry foundation
- Task 190: workspace MCP configs, tool inventory, and approval gates foundation
- Task 191: agent approval-gated execution plan UI and step approval tracking
- Task 192: workflow evidence, MCP tool mapping, and execution readiness panel

## Current focus

Safe Agent and MCP workflow, while preserving local-first safety:

- model capability awareness for agent-style tasks;
- planning-only agent workflows before execution;
- manual workflow tracking with step statuses;
- MCP server catalog and config preview;
- workspace-saved MCP configs;
- reviewed/approved MCP tool inventory;
- approval gates before any future tool execution;
- step approval preview with proposed tool, risk, evidence, and blocked actions;
- workflow execution readiness maps steps to approved MCP tools and shows blockers;
- workflow steps can store manual evidence status, summary, and sources;
- workflow steps cannot be marked in progress/done until approved when confirmation is required;
- no automatic shell/MCP/tool execution from the frontend.

## Packaging direction

The product is close to the original goal, but true two-click installation still needs a dedicated packaging phase:

- script-based local start is available now;
- next step is a friendly launcher/shortcut for macOS;
- later step is Windows launcher support;
- model selection should become a guided setup flow with recommended LLM/embedding choices, explanations, and custom model entry;
- packaging must protect `backend/.ai-workbench/workspaces.db` and never overwrite runtime data during updates.

## Safety posture

- Local-first only.
- No external upload/share automation.
- No shell execution from frontend.
- No MCP server start from frontend.
- No MCP tool execution. Approval gates record intent only until backend sandbox execution exists.
- Skills guide answer style, but project facts must come from retrieved sources.
- Reports and exports must remain source-backed and user-controlled.

## Task 194 checkpoint

Added the macOS launcher foundation for the packaging path:

- `scripts/launch_macos.command` starts only local backend/frontend servers after explicit confirmation.
- The launcher performs prerequisite checks and exits with setup instructions if dependencies are missing.
- No project scan, indexing, model pull, MCP execution, or agent execution is triggered by the launcher.
- `docs/MACOS_LAUNCHER.md` documents setup and optional Finder alias usage.

## Task 197 checkpoint — macOS shortcut foundation

Added a macOS `.app` shortcut generator for desktop-like startup:

- `scripts/create_macos_shortcut.sh` creates `~/Applications/AI Private Workspace.app` by default.
- The generated app delegates to `scripts/launch_macos.command`.
- Post-launch readiness now includes an optional desktop shortcut item and copy-only command.
- No automatic model pull, scan, index, rebuild, MCP execution, or agent execution was introduced.

## Packaging clarity update — Task 198

The current macOS launcher is a bridge for developer-safe testing, not the final distribution model. The final product target remains a true desktop app for macOS and Windows: download, double-click, local services start safely, and the UI opens without cloning the repository or manually running backend/frontend scripts.

Model downloads and MCP server setup should be implemented as explicit, user-approved product flows before the final installer: model manager first, MCP install/config/checks second, sandboxed execution later.


## Task 200 — Release candidate UI review

Completed a full UI/UX consistency pass focused on calm Apple-like layout, reduced cognitive load, clearer first-run logic, and one-primary-action sections. Advanced file rules and packaging roadmap details are now progressively disclosed instead of competing with the main setup flow.

## Task 206 checkpoint

Added approved local model download execution foundation. The backend can run an exact allowlisted `ollama pull <catalog-model-name>` draft only when explicitly enabled for a trusted local runtime. Frontend shell execution remains forbidden.

## Task 207 update

Added model download job foundation endpoints: `POST /models/local-install-drafts/{command_id}/jobs` and `GET /models/local-download-jobs/{job_id}`. Jobs are backend-owned status records for approved Ollama downloads. The frontend can start and refresh a job, but still never runs shell commands. Execution remains opt-in and allowlisted.

## Task 213 — Agent + MCP readiness cleanup

- Added a calm Agent + MCP overview panel.
- Simplified Agent screen hierarchy around the main action: preview a safe plan.
- Collapsed secondary capability/guardrail/workflow details to reduce visual noise.
- Kept MCP as safe tool visibility only; no automatic server start or tool execution.


## Task 214 — Desktop packaging design lock

Locked the target architecture for the real desktop app: Tauri-first shell, supervised FastAPI backend, static frontend assets, localhost-only API, protected local data, logs, lifecycle rules, and explicit safety boundaries. Current scripts remain a temporary developer-safe bridge.

## Task 215 — macOS app package foundation

Task 215 moves packaging from concept to a concrete macOS `.app` foundation.

Added:
- `GET /runtime/macos-app-package-foundation`
- `scripts/package_macos_app_foundation.sh`
- Settings UI section for macOS package foundation
- `docs/MACOS_APP_PACKAGE_FOUNDATION.md`
- `docs/MACOS_APP_PACKAGE_NEXT_STEPS.md`

Important safety boundaries:
- The generated bundle is created under `build/` and is not part of normal source archives.
- Runtime data is excluded from packaged backend files.
- The script does not download models, start MCP servers, run agent tools, scan, index, rebuild, or restart user workflows.
- This is not the final signed Tauri app yet; it is a packaging skeleton and lifecycle contract.
- Task 216: desktop supervisor contract implemented as a read-only backend endpoint, UI section, and safe development supervisor script.


## Task 217 — macOS app wiring to supervisor contract

- Added `/runtime/macos-app-supervisor-wiring`.
- Wired `scripts/package_macos_app_foundation.sh` launcher to the desktop supervisor lifecycle.
- Generated `.app` now performs preflight, safe port check, app-owned backend startup, `/health` polling, and packaged UI open.
- Logs are written outside the `.app` bundle under app data.
- Frontend still never executes shell, and no scan/index/rebuild/MCP/agent/model download starts on launch.

## Task 218 — backend runtime bundle readiness

- Added `/runtime/backend-runtime-bundle-plan`.
- Added `scripts/prepare_macos_backend_runtime.sh`.
- Runtime manifest is generated under `build/macos/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt`.
- macOS package script now generates/copies the runtime manifest into app resources.
- This is still a foundation: the app is not signed and backend is not frozen into a standalone binary yet.
- Safety preserved: runtime preparation does not start scan/index/rebuild/MCP/agent/model downloads and does not package runtime databases or local state.

## Task 219 — Tauri shell scaffold/foundation

Added `frontend/src-tauri` as the first source-controlled desktop shell scaffold and `scripts/prepare_tauri_shell_scaffold.sh` as a safe validation helper. This is still a scaffold, not a final signed installer. Frontend still does not execute shell commands; backend supervision must remain app-owned and explicit.

## Task 220 checkpoint — Tauri supervisor bridge

The project now has a Tauri supervisor bridge foundation:

- `GET /runtime/tauri-supervisor-bridge`
- read-only Tauri commands for supervisor status/log paths
- scaffold validation for the bridge commands
- Settings UI panel for bridge states and safety

The bridge remains safe: no frontend shell execution, no backend process startup from Tauri yet, and no automatic scan/index/rebuild/MCP/agent/model-download actions on launch.

## Task 221 — Windows packaging foundation

Added the Windows equivalent of the desktop packaging path:

- `GET /runtime/windows-packaging-foundation`
- `scripts/windows_supervisor_contract.ps1`
- `scripts/package_windows_app_foundation.ps1`
- `scripts/prepare_windows_packaging_foundation.sh`
- `docs/WINDOWS_PACKAGING_FOUNDATION.md`

The target UX remains downloaded package -> double click -> app-owned localhost backend -> UI opens. Windows runtime data is planned under `%LOCALAPPDATA%\AI Private Workspace`. Frontend still never executes shell commands.


## Task 222 — release candidate audit

Added a read-only release candidate audit endpoint, source archive policy, validation script, UI audit block, and docs for v0.1 handoff readiness.

## Task 223 — v0.1 demo and GitHub handoff

The project now has a GitHub-ready README, v0.1 demo handoff, release notes, repository guide, and a read-only `/runtime/v0.1-handoff` endpoint. Settings includes a final v0.1 handoff block with demo steps, important repository files, validation commands, release notes, limitations, and next steps.

Current status: v0.1 release candidate source handoff is ready. Final signed desktop installers are still future packaging work.
## Task 224 final product-quality pass

- Repository now includes GitHub-ready README, contribution guide, security policy, issue templates, PR template, and CI workflows.
- Frontend received a final Apple-style normalization layer for spacing, typography, controls, card rhythm, and dark mode.
- Product-facing copy now consistently uses AI Private Workspace.
- `docs/assets/product-flow.svg` explains the local-first flow on the GitHub landing page.



## Task 225 — Model Manager real usage flow and render recovery

- Fixed Models screen render resilience.
- Added a clear Choose → Download → Verify → Use model workflow.
- Kept frontend shell execution disabled.


## Task 226 checkpoint

Models tab crash was fixed by moving hooks before conditional loading/error returns in the local model install panel. The UI now includes an Ollama recommendation guide that explains which model answers questions, which model powers search context, and which Mac profile to start with.


## Task 227 — Model context indexing clarity

Clarified the difference between selecting an embedding/search model and building workspace context with it. The UI now says `Needs context build` when the selected search model is active but the workspace has not been indexed yet.

- Task 228 — Model context build action ✅

## Task 229 — Source release packaging and completion roadmap

- Restored/added GitHub-facing repository files: README, CONTRIBUTING, SECURITY, GitHub Actions, PR template, and issue templates.
- Added `scripts/prepare_source_release_archive.sh` for a clean root-preserving source archive.
- Added `docs/GITHUB_PUBLICATION_CHECKLIST.md`, `docs/SOURCE_RELEASE_CHECKLIST.md`, and `docs/V1_PRODUCT_COMPLETION_ROADMAP.md`.
- Added `GET /runtime/product-completion-roadmap` to clearly distinguish v0.1 source RC from a future v1.0 product.
- Updated release audit checks to include README/.github and `*.sqlite3`.

## Task 230 — Source release stabilization

- Restored missing GitHub-facing root files and `.github` templates/workflows in the source tree.
- Hardened `scripts/audit_release_candidate.sh` so local runtime/build folders are warnings, while source-tree database files outside ignored paths still fail audit.
- Hardened `scripts/prepare_source_release_archive.sh` to build from the current working tree with explicit excludes, making it useful before the final release commit exists.
- Added `docs/TASK230_SOURCE_RELEASE_STABILIZATION.md` and refreshed publication/source release checklists.

Current status: v0.1 source RC is ready for GitHub publication checks after local validation.

## Task 231 update — final repository publication pass

Task 231 restored and stabilized GitHub-facing repository files so the project is ready to be published as a polished v0.1 source release candidate.

Added or confirmed:

- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.editorconfig`
- `.gitattributes`
- `.github/workflows/ci.yml`
- `.github/workflows/desktop-packaging-checks.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `docs/TASK231_FINAL_REPOSITORY_PUBLICATION_PASS.md`

The release target remains source-RC quality, not a signed installer. Runtime/build data must remain excluded from GitHub and release archives.

## Task 232 update — final status and v1 runway

Task 232 adds `GET /runtime/final-product-status` and a Settings UI section named **Where we are now**. It makes the status explicit: the project is a GitHub-ready v0.1 source release candidate after local validation, not a finished v1.0 desktop installer. The remaining estimate is 0-2 large tasks for source-RC cleanup and roughly 15-25 large tasks for a polished v1.0 product.

## Task 235 — v0.1 release gate and roadmap lock

Task 235 adds a final release-gate endpoint: `GET /runtime/v0.1-release-gate`. It gives a concrete go/no-go checklist for audit, backend targeted tests, frontend build, UI smoke-check, git status cleanup, and clean source archive creation.

Current status after this task:

- v0.1 source RC: effectively complete, with 0-1 large task left for local verification and publication.
- v1.0 installer-grade product: still future work, roughly 15-25 large tasks.
- Recommended next step: run the release gate locally, create/push the clean source release, then start Phase 22/v0.2.



## Task 236 — v0.1 UI smoke-check handoff

Task 236 adds a final manual UI smoke-check endpoint: `GET /runtime/v0.1-ui-smoke-check`. It gives a 10-15 minute browser checklist for startup, Models, onboarding/workspace creation, Ask, and Settings before GitHub/source archive publication. The checklist is documentation only: it does not start servers, inspect browser state, run tests, scan/index context, download models, or execute shell commands.

Current roadmap position after Task 236:

- Phase 21 / v0.1 source RC is effectively complete.
- Remaining v0.1 work is local human verification, clean git status, source archive, and first GitHub push.
- v1.0 remains future work with roughly 15-25 large tasks: frozen backend runtime, signed installers, persistent jobs, MCP runtime, sandboxed Agent execution, update flow, and final QA.


## Task 237 — v0.1 publication handoff

- Added final read-only publication handoff endpoint and Settings UI section.
- Current roadmap position: Phase 21 effectively complete; v0.1 has 0-1 large task left for manual smoke-check/publication cleanup.
- v1.0 still needs roughly 15-25 large tasks: frozen runtime, signed installers, persistent jobs, MCP runtime, sandboxed Agent execution, update flow, and final QA.
## Task 238 — desktop runtime readiness

Task 238 adds the Phase 22 / v0.2 desktop runtime readiness endpoint and Settings UI handoff. The project should now stop adding v0.1 features unless local smoke-check finds blockers. The next product stage is desktop runtime reliability: backend runtime manifest, Tauri supervisor status, app-owned backend startup, app-owned logs/data, and no automatic scan/index/MCP/Agent/model downloads on launch.


### Task 239 — Desktop runtime preflight

Task 239 adds a read-only Phase 22 gate with `GET /runtime/desktop-runtime-preflight`, `scripts/check_desktop_runtime_preflight.sh`, backend tests, and a Settings UI section. It verifies backend entrypoint, runtime manifest, frontend build output, macOS package foundation script, and Tauri scaffold before any real Tauri backend process supervision is implemented. It preserves the rule that frontend code can display/copy commands but never execute shell commands.


## Task 240 — Tauri supervisor static gate

- Added a read-only Tauri supervisor static gate for Phase 22.
- Added `GET /runtime/tauri-supervisor-static-gate`.
- Added `scripts/check_tauri_supervisor_bridge.sh`.
- Tauri bridge now exposes status, log paths, and preflight data while keeping backend startup disabled.
- Next larger step: frozen/staged backend runtime and deterministic app-owned startup design.
