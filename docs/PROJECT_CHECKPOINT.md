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
- First-launch readiness now includes an optional desktop shortcut item and copy-only command.
- No automatic model pull, scan, index, rebuild, MCP execution, or agent execution was introduced.
