# Local Data Safety

AI Private Workspace stores user-created workspace state locally. Code updates must not replace or delete runtime data.

## Protected local data

Default backend runtime data lives under:

```text
backend/.ai-workbench/
backend/.ai-workbench/workspaces.db
```

This database can contain workspaces, scans, indexing rules, skill profiles, saved conversations, reusable notes, and saved reports.

## Safe update rule

When applying a generated archive with `rsync --delete`, always exclude runtime data:

```bash
rsync -av --delete \
  --exclude ".git" \
  --exclude "node_modules" \
  --exclude "dist" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".venv" \
  --exclude "backend/.ai-workbench" \
  --exclude "*.db" \
  --exclude "*.sqlite" \
  SOURCE/ \
  ~/Documents/ai_workspace/
```

Generated zip archives should keep the root project shape:

```text
backend/
frontend/
docs/
pytest.ini
```

They should not include `backend/.ai-workbench/`, virtual environments, frontend dependencies, build output, or SQLite databases.

## Backup before large updates

```bash
cd ~/Documents/ai_workspace/backend
mkdir -p .ai-workbench
cp .ai-workbench/workspaces.db .ai-workbench/workspaces.db.backup
```

Find possible old workspace databases:

```bash
find ~/Documents -path '*ai_workspace*workspaces.db' -print -exec ls -lh {} \;
```

## Runtime diagnostics

Use:

```bash
curl http://127.0.0.1:8000/runtime/local-data
```

The response shows the active database path, whether the database exists, key object counts, safe update excludes, and backup command hints.

## Safer generated update workflow

Use the helper script when applying generated archives:

```bash
scripts/apply_generated_update.sh /path/to/unzipped/update ~/Documents/ai_workspace
```

The script keeps generated source files in sync while preserving runtime data such as `backend/.ai-workbench/workspaces.db`.

## Task 177 backup/restore workflow

Additional read-only and explicit backup endpoints are available:

```bash
curl http://127.0.0.1:8000/runtime/database-backups
curl http://127.0.0.1:8000/runtime/database-migration-safety
```

Creating a backup is an explicit backend action:

```bash
curl -X POST http://127.0.0.1:8000/runtime/database-backups
```

Restore remains manual. The restore-plan endpoint returns copy commands only and does not modify the active database.
