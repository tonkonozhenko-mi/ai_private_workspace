# Task 230 — Source release stabilization

Task 230 hardens the repository for the first GitHub push and clean source release archive.

## What changed

- Restored GitHub-facing repository files at the repository root:
  - `README.md`
  - `CONTRIBUTING.md`
  - `SECURITY.md`
  - `.editorconfig`
  - `.gitattributes`
- Restored GitHub community files:
  - `.github/workflows/ci.yml`
  - `.github/workflows/desktop-packaging-checks.yml`
  - `.github/pull_request_template.md`
  - `.github/ISSUE_TEMPLATE/bug_report.yml`
  - `.github/ISSUE_TEMPLATE/feature_request.yml`
- Restored the product visual:
  - `docs/assets/product-flow.svg`
- Hardened release audit behavior:
  - local runtime/build folders are warnings, not blockers;
  - database files fail audit only when they appear outside ignored runtime/build paths;
  - GitHub files are now part of the required release surface.
- Hardened source archive creation:
  - archive is built from the current working tree;
  - runtime/build/cache files are excluded explicitly;
  - generated archive remains under `build/release/` and must not be committed.

## Why this matters

The project is intended to be published to GitHub. The repository should therefore look complete on first open, with clear onboarding, contribution rules, security boundaries, CI, release checks, and no local runtime data.

## Validation

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q tests/test_source_release_archive_script.py tests/test_release_candidate_audit_script.py tests/test_release_candidate_audit.py tests/test_api_inventory.py

cd ../frontend
npm ci
npm run build
```

## Release archive

```bash
./scripts/prepare_source_release_archive.sh
```

The archive is created in `build/release/` and should not be committed.
