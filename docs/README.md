# Documentation Index

Product, architecture, packaging, and release documentation for
**AI Private Workspace**.

> The per-task development journal (`TASK###_*.md` files) and point-in-time
> status snapshots were removed to keep this folder focused on current,
> evergreen documentation. A few task-numbered files remain only because code,
> tests, or packaging scripts reference them directly.

## Start here

- [START_HERE.md](START_HERE.md) — first entry point for running and understanding the project.
- [ARCHITECTURE.md](ARCHITECTURE.md) — ports & adapters architecture overview.
- [CONFIGURATION.md](CONFIGURATION.md) — settings and environment variables.
- [ROADMAP.md](ROADMAP.md) — current roadmap and remaining work.
- [V1_PRODUCT_COMPLETION_ROADMAP.md](V1_PRODUCT_COMPLETION_ROADMAP.md) — path from v0.1 source release to v1.0 installer-grade product.
- [PROJECT_CHECKPOINT.md](PROJECT_CHECKPOINT.md) — current project checkpoint.
- [CONTINUE_MESSAGE.md](CONTINUE_MESSAGE.md) — development continuation notes.

## API & frontend

- [API_INVENTORY.md](API_INVENTORY.md) — backend HTTP API inventory.
- [FRONTEND_API_MAP.md](FRONTEND_API_MAP.md) — how the frontend maps to backend endpoints.

## Safety & data

- [LOCAL_DATA_SAFETY.md](LOCAL_DATA_SAFETY.md) — local-only data handling and the safety model.
- [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md) — backing up and restoring local workspace data.

## Models, downloads & RAG

- [INSTALLED_MODEL_DETECTION.md](INSTALLED_MODEL_DETECTION.md)
- [MODEL_INSTALL_APPROVAL_FLOW.md](MODEL_INSTALL_APPROVAL_FLOW.md)
- [MODEL_DOWNLOAD_JOBS.md](MODEL_DOWNLOAD_JOBS.md)
- [MODEL_DOWNLOAD_MANAGER_PLAN.md](MODEL_DOWNLOAD_MANAGER_PLAN.md)
- [MODEL_DOWNLOAD_WORKER_DESIGN.md](MODEL_DOWNLOAD_WORKER_DESIGN.md)
- [MODEL_DOWNLOAD_EXECUTION_FOUNDATION.md](MODEL_DOWNLOAD_EXECUTION_FOUNDATION.md)
- [MODEL_DOWNLOAD_CANCEL_AND_HISTORY.md](MODEL_DOWNLOAD_CANCEL_AND_HISTORY.md)
- [MODEL_DOWNLOAD_JOB_UX.md](MODEL_DOWNLOAD_JOB_UX.md)
- [BACKGROUND_MODEL_DOWNLOAD_WORKER.md](BACKGROUND_MODEL_DOWNLOAD_WORKER.md)
- [MODEL_MANAGER_FINAL_HARDENING.md](MODEL_MANAGER_FINAL_HARDENING.md)

## MCP & Agent

- [MCP_AGENT_INTEGRATION.md](MCP_AGENT_INTEGRATION.md) — MCP and Agent integration model.
- [MCP_SETUP_UX_TASK212.md](MCP_SETUP_UX_TASK212.md) — MCP setup UX (referenced by backend safety routes).
- [AGENT_MCP_READINESS_TASK213.md](AGENT_MCP_READINESS_TASK213.md) — Agent/MCP readiness (referenced by backend safety routes).

## Desktop packaging (macOS / Windows / Tauri)

- [DESKTOP_APP_TARGET.md](DESKTOP_APP_TARGET.md)
- [DESKTOP_STARTUP.md](DESKTOP_STARTUP.md)
- [DESKTOP_PACKAGING_DESIGN_LOCK.md](DESKTOP_PACKAGING_DESIGN_LOCK.md)
- [DESKTOP_SUPERVISOR_CONTRACT.md](DESKTOP_SUPERVISOR_CONTRACT.md)
- [MACOS_LAUNCHER.md](MACOS_LAUNCHER.md)
- [MACOS_APP_PACKAGE_FOUNDATION.md](MACOS_APP_PACKAGE_FOUNDATION.md)
- [MACOS_APP_PACKAGE_NEXT_STEPS.md](MACOS_APP_PACKAGE_NEXT_STEPS.md)
- [MACOS_APP_SUPERVISOR_WIRING.md](MACOS_APP_SUPERVISOR_WIRING.md)
- [MACOS_BACKEND_RUNTIME_BUNDLE_PLAN.md](MACOS_BACKEND_RUNTIME_BUNDLE_PLAN.md)
- [WINDOWS_PACKAGING_FOUNDATION.md](WINDOWS_PACKAGING_FOUNDATION.md)
- [TAURI_SHELL_SCAFFOLD.md](TAURI_SHELL_SCAFFOLD.md)
- [TAURI_SUPERVISOR_BRIDGE.md](TAURI_SUPERVISOR_BRIDGE.md)
- [PRODUCT_PACKAGING_ROADMAP.md](PRODUCT_PACKAGING_ROADMAP.md)
- [TASK242_DESKTOP_STACK_AND_RUNTIME_CONTRACT.md](TASK242_DESKTOP_STACK_AND_RUNTIME_CONTRACT.md) — referenced by packaging scripts.
- [TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md](TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md) — referenced by backend and scripts.
- [TASK251_MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md](TASK251_MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md) — referenced by backend and scripts.

## Runbooks & troubleshooting

- [LOCAL_RUNTIME_RUNBOOK.md](LOCAL_RUNTIME_RUNBOOK.md)
- [RUNTIME_TROUBLESHOOTING.md](RUNTIME_TROUBLESHOOTING.md)

## Release & publication

- [V01_DEMO_HANDOFF.md](V01_DEMO_HANDOFF.md)
- [V01_RELEASE_NOTES.md](V01_RELEASE_NOTES.md)
- [RELEASE_CANDIDATE_AUDIT.md](RELEASE_CANDIDATE_AUDIT.md)
- [SOURCE_RELEASE_CHECKLIST.md](SOURCE_RELEASE_CHECKLIST.md)
- [GITHUB_PUBLICATION_CHECKLIST.md](GITHUB_PUBLICATION_CHECKLIST.md)
- [GITHUB_REPOSITORY_GUIDE.md](GITHUB_REPOSITORY_GUIDE.md)
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)
