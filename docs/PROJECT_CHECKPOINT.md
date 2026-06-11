# AI Private Workspace — Project Checkpoint

Last updated: Task 191

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
