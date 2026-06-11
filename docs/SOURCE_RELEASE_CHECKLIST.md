# Source Release Checklist

Use this checklist before creating or sharing the v0.1 source release archive.

## 1. Confirm repository status

```bash
git status --short
```

Review every file. Do not commit runtime data, local databases, generated builds, or caches.

## 2. Run release audit

```bash
./scripts/audit_release_candidate.sh
```

Acceptable local warnings:

- `backend/.ai-workbench`
- `build`
- `frontend/node_modules`
- `frontend/dist`
- `.pytest_cache`

Failures must be fixed before release.

## 3. Run focused checks

```bash
cd backend
pytest -q tests/test_health.py tests/test_api_inventory.py tests/test_release_candidate_audit.py tests/test_source_release_archive_script.py

cd ../frontend
npm ci
npm run build
```

## 4. Create clean source archive

```bash
cd ~/Documents/ai_workspace
./scripts/prepare_source_release_archive.sh
```

Expected output:

```text
build/release/ai-private-workspace-v0.1-source.zip
```

## 5. Verify archive contents

```bash
unzip -l build/release/ai-private-workspace-v0.1-source.zip | grep -E 'backend/.ai-workbench|node_modules|frontend/dist|build/release|\.sqlite|\.db' || true
```

The command should not show runtime/build/database files from the archive.
