# Documentation Index

This folder holds the product, architecture, packaging, and release documentation
for **AI Private Workspace**, plus a historical engineering log.

> **Note on structure.** Many task-numbered documents (`TASK###_*.md`) are
> referenced directly by backend code, tests, and packaging scripts, so they are
> intentionally kept in place rather than deleted. Treat them as an append-only
> engineering log. The curated, current documents are listed first below.

## Start here

- [START_HERE.md](START_HERE.md) — first entry point for running and understanding the project.
- [ARCHITECTURE.md](ARCHITECTURE.md) — ports & adapters architecture overview.
- [CONFIGURATION.md](CONFIGURATION.md) — settings and environment variables.
- [ROADMAP.md](ROADMAP.md) — current roadmap and remaining work.
- [V1_PRODUCT_COMPLETION_ROADMAP.md](V1_PRODUCT_COMPLETION_ROADMAP.md) — path from v0.1 source release to v1.0 installer-grade product.

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

## Runbooks & troubleshooting

- [LOCAL_RUNTIME_RUNBOOK.md](LOCAL_RUNTIME_RUNBOOK.md)
- [RUNTIME_TROUBLESHOOTING.md](RUNTIME_TROUBLESHOOTING.md)

## Release & publication

- [V01_DEMO_HANDOFF.md](V01_DEMO_HANDOFF.md)
- [V01_RELEASE_NOTES.md](V01_RELEASE_NOTES.md)
- [RELEASE_CANDIDATE_AUDIT.md](RELEASE_CANDIDATE_AUDIT.md)
- [RELEASE_CANDIDATE_UI_REVIEW.md](RELEASE_CANDIDATE_UI_REVIEW.md)
- [SOURCE_RELEASE_CHECKLIST.md](SOURCE_RELEASE_CHECKLIST.md)
- [GITHUB_PUBLICATION_CHECKLIST.md](GITHUB_PUBLICATION_CHECKLIST.md)
- [GITHUB_REPOSITORY_GUIDE.md](GITHUB_REPOSITORY_GUIDE.md)
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)

## Status snapshots & process notes

These are point-in-time snapshots from development. They may be partially stale;
trust the curated documents above first.

- [PROJECT_STATE.md](PROJECT_STATE.md)
- [PROJECT_CHECKPOINT.md](PROJECT_CHECKPOINT.md)
- [NEXT_STEPS.md](NEXT_STEPS.md)
- [CONTINUE_MESSAGE.md](CONTINUE_MESSAGE.md)
- [FINAL_PRODUCT_QUALITY_PASS.md](FINAL_PRODUCT_QUALITY_PASS.md)
- [UI_POLISH_QA.md](UI_POLISH_QA.md)
- [UI_LOVE_PASS_TASK201.md](UI_LOVE_PASS_TASK201.md)

## Task engineering log (historical)

`TASK###_*.md` files document individual development tasks in order. They are kept
because backend code, tests, and `scripts/` reference several of them by path.
Browse them directly if you need the detailed history of a specific change.
