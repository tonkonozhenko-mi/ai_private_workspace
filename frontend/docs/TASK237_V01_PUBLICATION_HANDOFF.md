# Task 237 — v0.1 publication handoff

Task 237 adds the final publication handoff for the v0.1 source release candidate.

## Added

- Backend endpoint: `GET /runtime/v0.1-publication-handoff`
- Frontend Settings section: **v0.1 publication handoff**
- Backend tests for the new read-only handoff endpoint

## Purpose

This is the final copyable route from local verification to GitHub/source release:

1. Run the release audit.
2. Run targeted backend release tests.
3. Build the frontend.
4. Perform manual UI smoke-check.
5. Create the clean source archive.
6. Review `git status --short`.
7. Stage, review, commit, and push only intended source files.

## Safety

The new endpoint and UI are read-only. They do not execute commands and do not change runtime state.

The handoff repeats the release safety rules:

- Frontend must never execute shell commands.
- Desktop startup must not auto-run scan/index/rebuild/MCP/Agent/model downloads.
- Model downloads remain backend-owned, opt-in, allowlisted, and disabled by default.
- MCP/Agent execution remains planning/manual tracking until sandboxing and audit logs exist.
- v0.1 must not be described as a finished installer-grade v1.0 product.
