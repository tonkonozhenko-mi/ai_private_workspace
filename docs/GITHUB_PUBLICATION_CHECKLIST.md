# GitHub Publication Checklist

Use this checklist before pushing AI Private Workspace to GitHub.

## 1. Repository presentation

Required files:

- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.editorconfig`
- `.gitattributes`
- `.github/workflows/ci.yml`
- `.github/workflows/desktop-packaging-checks.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `docs/assets/product-flow.svg`

## 2. Confirm local source state

```bash
git status --short
```

Review every changed file. Do not commit runtime data, generated build output, or local caches.

## 3. Run the release audit

```bash
./scripts/audit_release_candidate.sh
```

Warnings for local folders such as `frontend/node_modules`, `frontend/dist`, `build`, `.pytest_cache`, or `backend/.ai-workbench` are acceptable locally. They must not be committed or included in release archives.

A database failure is not acceptable when the database is outside ignored runtime/build paths. Find source-tree database files with:

```bash
find . \( \
  -path "./frontend/node_modules" -o \
  -path "./frontend/dist" -o \
  -path "./build" -o \
  -path "./backend/.ai-workbench" -o \
  -path "./.pytest_cache" \
\) -prune -o \( \
  -name "*.db" -o \
  -name "*.sqlite" -o \
  -name "*.sqlite3" \
\) -print
```

## 4. Run focused validation

```bash
cd backend
pytest -q tests/test_health.py tests/test_api_inventory.py tests/test_release_candidate_audit.py tests/test_source_release_archive_script.py

cd ../frontend
npm ci
npm run build
```

## 5. Check ignored files

```bash
git check-ignore -v backend/.ai-workbench frontend/node_modules frontend/dist build .pytest_cache || true
```

## 6. Create a clean source archive

```bash
./scripts/prepare_source_release_archive.sh
```

The archive is written to `build/release/` and should not be committed.

## 7. Commit and push

```bash
git add README.md CONTRIBUTING.md SECURITY.md .editorconfig .gitattributes .github backend frontend docs scripts pytest.ini .gitignore
git status --short
git commit -m "Prepare AI Private Workspace v0.1 source release"
git push origin main
```

Adjust the branch name if your default branch is different.
