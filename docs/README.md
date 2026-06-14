# Documentation Index

Product, architecture, packaging, and release documentation for
**AI Private Workspace**. Kept intentionally small — one document per topic.

## Start here

- [START_HERE.md](START_HERE.md) — first entry point for running and understanding the project.
- [ARCHITECTURE.md](ARCHITECTURE.md) — ports & adapters architecture overview.
- [CONFIGURATION.md](CONFIGURATION.md) — settings and environment variables.
- [ROADMAP.md](ROADMAP.md) — current roadmap and remaining work.
- [V1_PRODUCT_COMPLETION_ROADMAP.md](V1_PRODUCT_COMPLETION_ROADMAP.md) — path from v0.1 source release to a v1.0 installer-grade product.
- [PROJECT_CHECKPOINT.md](PROJECT_CHECKPOINT.md) — current project checkpoint.
- [CONTINUE_MESSAGE.md](CONTINUE_MESSAGE.md) — development continuation notes.

## API & frontend

- [API_INVENTORY.md](API_INVENTORY.md) — backend HTTP API inventory.
- [FRONTEND_API_MAP.md](FRONTEND_API_MAP.md) — how the frontend maps to backend endpoints.

## Safety & data

- [LOCAL_DATA_SAFETY.md](LOCAL_DATA_SAFETY.md) — local-only data handling and the safety model.
- [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md) — backing up and restoring local workspace data.

## Models, downloads & RAG

- [INSTALLED_MODEL_DETECTION.md](INSTALLED_MODEL_DETECTION.md) — detecting locally installed Ollama models.
- [MODEL_INSTALL_APPROVAL_FLOW.md](MODEL_INSTALL_APPROVAL_FLOW.md) — the approval-gated model install flow.
- [MODEL_DOWNLOAD_JOBS.md](MODEL_DOWNLOAD_JOBS.md) — backend-owned model download jobs.

## MCP & Agent

- [MCP_AGENT_INTEGRATION.md](MCP_AGENT_INTEGRATION.md) — MCP and Agent integration model.
- [MCP_SETUP_UX.md](MCP_SETUP_UX.md) — MCP setup UX (referenced by backend safety routes).
- [AGENT_MCP_READINESS.md](AGENT_MCP_READINESS.md) — Agent/MCP readiness (referenced by backend safety routes).

## Desktop packaging (macOS / Windows / Tauri)

- [DESKTOP_STARTUP.md](DESKTOP_STARTUP.md) — how the desktop app starts up.
- [DESKTOP_PACKAGING_DESIGN_LOCK.md](DESKTOP_PACKAGING_DESIGN_LOCK.md) — locked packaging design decisions.
- [MACOS_LAUNCHER.md](MACOS_LAUNCHER.md) — the macOS double-click launcher.
- [WINDOWS_PACKAGING_FOUNDATION.md](WINDOWS_PACKAGING_FOUNDATION.md) — Windows packaging foundation.
- [DESKTOP_STACK_AND_RUNTIME_CONTRACT.md](DESKTOP_STACK_AND_RUNTIME_CONTRACT.md) — desktop stack & runtime contract (referenced by scripts).
- [MACOS_TAURI_SMOKE_RUNBOOK.md](MACOS_TAURI_SMOKE_RUNBOOK.md) — macOS/Tauri smoke runbook (referenced by backend and scripts).
- [MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md](MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md) — packaged app smoke preflight (referenced by backend and scripts).

## Runbooks & troubleshooting

- [LOCAL_RUNTIME_RUNBOOK.md](LOCAL_RUNTIME_RUNBOOK.md) — running the project locally.
- [RUNTIME_TROUBLESHOOTING.md](RUNTIME_TROUBLESHOOTING.md) — common runtime problems and fixes.

## Release & publication

- [RELEASE_AND_UPDATES.md](RELEASE_AND_UPDATES.md) — free distribution + auto-update setup (Tauri updater + GitHub), step by step.
- [V01_DEMO_HANDOFF.md](V01_DEMO_HANDOFF.md) — v0.1 demo scenario and handoff guide.
- [V01_RELEASE_NOTES.md](V01_RELEASE_NOTES.md) — v0.1 release notes.
- [RELEASE_CANDIDATE_AUDIT.md](RELEASE_CANDIDATE_AUDIT.md) — release audit and archive policy.
- [SOURCE_RELEASE_CHECKLIST.md](SOURCE_RELEASE_CHECKLIST.md) — source release checklist.
- [GITHUB_PUBLICATION_CHECKLIST.md](GITHUB_PUBLICATION_CHECKLIST.md) — GitHub publication checklist.
