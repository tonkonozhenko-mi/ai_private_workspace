# Task 236 — v0.1 UI smoke-check handoff

Task 236 adds the final manual browser verification checklist for the v0.1 source release candidate.

## Added

- `GET /runtime/v0.1-ui-smoke-check`
- `backend/tests/test_v01_ui_smoke_check.py`
- API inventory and checkpoint documentation updates

## Purpose

The v0.1 source RC is already at the publication gate. This task avoids adding risky new capability and instead makes the last human check explicit:

1. Start backend and frontend manually.
2. Open the UI only after `/health` is ready.
3. Verify Models, onboarding/workspace creation, Ask, and Settings.
4. Confirm startup does not trigger scan, index, rebuild, MCP, Agent, or model downloads.
5. Confirm Settings keeps the wording honest: v0.1 source RC now, v1.0 installer-grade product later.

## Safety

The endpoint is read-only documentation. It does not inspect browser state, start servers, run tests, scan files, index context, download models, run MCP servers, execute Agent workflows, or execute shell commands.

## Roadmap position

- Phase 21 / v0.1 source RC: effectively complete.
- Remaining v0.1 work: local UI smoke-check, clean git status, source archive, first GitHub push.
- v1.0: future Phase 22+ work, still roughly 15-25 large tasks.
