# Task 238 — Desktop runtime readiness

Task 238 starts the next stage after the v0.1 source release candidate without changing runtime safety behavior.

## Added

- Backend endpoint: `GET /runtime/desktop-runtime-readiness`
- Settings UI section: **v0.2 desktop runtime readiness**
- Test coverage: `backend/tests/test_desktop_runtime_readiness.py`
- API inventory entry for the new endpoint

## Purpose

The endpoint locks the Phase 22 / v0.2 direction:

1. Keep v0.1 frozen except for blockers found during local UI smoke-check.
2. Make backend runtime manifest a required packaging preflight.
3. Add Tauri read-only supervisor status and log-path commands.
4. Start app-owned backend from Tauri only after runtime staging is deterministic.
5. Add desktop startup screen that waits for `/health`.
6. Mirror the lifecycle on Windows after macOS/Tauri startup is stable.

## Safety boundaries

- Frontend React code still never executes shell commands.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.
- Tauri may start only app-owned local backend runtime after explicit packaging implementation.
- Unknown processes on the expected port must not be killed.
- Logs and workspace data stay outside app bundles and source archives.

## Status

- v0.1 source RC: effectively complete after local smoke-check and publication.
- v0.2 desktop runtime: ready to start.
- v1.0 installer-grade product: still roughly 15-25 large tasks away.
