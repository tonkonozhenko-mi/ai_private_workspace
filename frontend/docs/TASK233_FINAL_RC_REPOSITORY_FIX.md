# Task 233 — final RC repository blocker cleanup

## Goal

Bring the uploaded v0.1 source release candidate back to a GitHub-publishable state after the archive was missing required repository-level files.

## Fixed

- Restored GitHub-facing root files:
  - `README.md`
  - `CONTRIBUTING.md`
  - `SECURITY.md`
  - `.editorconfig`
  - `.gitattributes`
- Restored GitHub contribution metadata:
  - `.github/workflows/ci.yml`
  - `.github/workflows/desktop-packaging-checks.yml`
  - `.github/pull_request_template.md`
  - `.github/ISSUE_TEMPLATE/bug_report.yml`
  - `.github/ISSUE_TEMPLATE/feature_request.yml`
- Kept the source archive policy intact: no runtime data, databases, local build outputs, or dependency folders in the handoff archive.

## Verification

Run from the repository root:

```bash
./scripts/audit_release_candidate.sh
cd backend
pytest -q tests/test_source_release_archive_script.py tests/test_release_candidate_audit.py tests/test_release_candidate_audit_script.py tests/test_api_inventory.py
cd ../frontend
npm ci
npm run build
```

## Status

This task is still part of the v0.1 source release candidate track. It does not make v1.0 installer-grade packaging complete.
