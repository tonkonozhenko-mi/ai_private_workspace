# Task 235 — v0.1 release gate and roadmap lock

This task adds a final go/no-go layer before publishing **AI Private Workspace v0.1** as a source release candidate.

## What changed

- Added `GET /runtime/v0.1-release-gate`.
- Added backend tests for the new release-gate endpoint.
- Updated API inventory and roadmap docs.
- Updated next-task wording so the project does not accidentally keep adding features to v0.1 before publication.

## Current roadmap position

- Phase 21 / v0.1 source RC: effectively complete.
- Remaining v0.1 work: 0-1 large task for local UI smoke-check, clean git status, audit/build/test pass, source archive, and first GitHub push.
- Phase 22 / v1.0 runway: future work, roughly 15-25 large tasks.

## Release gate commands

```bash
./scripts/audit_release_candidate.sh
```

```bash
cd backend
pytest -q tests/test_release_candidate_audit_script.py tests/test_source_release_archive_script.py tests/test_release_candidate_audit.py tests/test_api_inventory.py tests/test_final_product_status.py tests/test_product_completion_roadmap.py tests/test_v01_release_gate.py
```

```bash
cd frontend
npm ci
npm run build
```

```bash
git status --short
./scripts/prepare_source_release_archive.sh
```

## Go/no-go rule

Publish v0.1 only when audit, backend targeted tests, frontend build, git status, and source archive creation are clean. Use the local UI smoke-check as the final human confidence check.

## Safety boundaries

- Frontend still must not execute shell commands.
- Startup still must not trigger scan/index/rebuild/MCP/Agent/model downloads.
- MCP/Agent execution stays disabled until sandbox, approvals, allowlists, and audit logs exist.
- Runtime/build/cache/database artifacts must not be included in GitHub or source archives.
