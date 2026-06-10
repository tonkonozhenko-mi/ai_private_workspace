#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
BACKEND_DIR="$PROJECT_DIR/backend"
DB_PATH="${WORKSPACE_DB_PATH:-$BACKEND_DIR/.ai-workbench/workspaces.db}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "Workspace database not found: $DB_PATH"
  exit 1
fi

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_PATH="${DB_PATH%.db}-$TIMESTAMP.backup.db"
cp "$DB_PATH" "$BACKUP_PATH"

echo "Created workspace DB backup: $BACKUP_PATH"
ls -lh "$BACKUP_PATH"
