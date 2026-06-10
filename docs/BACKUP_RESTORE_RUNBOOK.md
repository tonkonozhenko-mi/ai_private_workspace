# Backup and Restore Runbook

AI Private Workspace keeps local runtime data in `backend/.ai-workbench/workspaces.db` by default. This file is intentionally excluded from generated update archives.

## Create a backup

From the project root:

```bash
scripts/backup_workspace_db.sh ~/Documents/ai_workspace
```

The backend UI also exposes an explicit **Create DB backup** action under Settings → Local data safety. It copies the current database next to the active DB file.

## Restore a backup manually

Restore is manual by design. The frontend never overwrites runtime data.

1. Stop the backend process.
2. Create a before-restore copy of the current DB.
3. Copy the selected backup to `backend/.ai-workbench/workspaces.db`.
4. Restart the backend.
5. Check Settings → Migration safety or call `/runtime/local-data`.

Example:

```bash
cd ~/Documents/ai_workspace/backend
cp .ai-workbench/workspaces.db .ai-workbench/workspaces.db.before-restore
cp .ai-workbench/workspaces-YYYYMMDD-HHMMSS.backup.db .ai-workbench/workspaces.db
python -m uvicorn app.main:app --reload
```

## Migration safety

Use the read-only endpoint:

```bash
curl http://127.0.0.1:8000/runtime/database-migration-safety
```

It checks the active DB path and known SQLite feature tables. Missing tables may be normal for features that were not used yet, but a backup is still recommended before applying generated updates.
