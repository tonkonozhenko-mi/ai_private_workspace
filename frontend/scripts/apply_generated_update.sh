#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
CREATE_BACKUP=1

usage() {
  cat <<'USAGE'
Usage: scripts/apply_generated_update.sh [--dry-run] [--no-backup] /path/to/unzipped/update /path/to/ai_workspace

Safe generated-update apply helper.
- Preserves backend/.ai-workbench, *.db, *.sqlite, .venv, node_modules, dist.
- Creates a timestamped SQLite backup before applying unless --no-backup is used.
- Supports --dry-run to preview rsync changes without writing files.

Example:
  scripts/apply_generated_update.sh --dry-run ~/Documents/ai_workspace_task179_work ~/Documents/ai_workspace
  scripts/apply_generated_update.sh ~/Documents/ai_workspace_task179_work ~/Documents/ai_workspace
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-backup)
      CREATE_BACKUP=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

SOURCE_DIR="$1"
TARGET_DIR="$2"

if [[ ! -d "$SOURCE_DIR/backend" || ! -d "$SOURCE_DIR/frontend" ]]; then
  echo "ERROR: Source must contain backend/ and frontend/ at its root." >&2
  echo "Do not pass a nested directory unless it contains the root project folders directly." >&2
  exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "ERROR: Target directory does not exist: $TARGET_DIR" >&2
  exit 1
fi

if [[ ! -d "$TARGET_DIR/backend" || ! -d "$TARGET_DIR/frontend" ]]; then
  echo "ERROR: Target does not look like ai_workspace root: $TARGET_DIR" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
TARGET_DB="$TARGET_DIR/backend/.ai-workbench/workspaces.db"
BACKUP_PATH=""

if [[ "$SOURCE_DIR" == "$TARGET_DIR" ]]; then
  echo "ERROR: Source and target are the same directory. Refusing to apply update." >&2
  exit 1
fi

if find "$SOURCE_DIR" \( -path "*/backend/.ai-workbench/*" -o -name "*.db" -o -name "*.sqlite" \) -print -quit | grep -q .; then
  echo "WARNING: Source contains runtime database files. They will be excluded and not copied." >&2
fi

cat <<INFO
Applying generated update safely
Source: $SOURCE_DIR
Target: $TARGET_DIR
Mode: $([[ "$DRY_RUN" == "1" ]] && echo "dry-run" || echo "apply")
Runtime data is protected: backend/.ai-workbench, *.db, *.sqlite
INFO

if [[ "$DRY_RUN" != "1" && "$CREATE_BACKUP" == "1" && -f "$TARGET_DB" ]]; then
  timestamp="$(date -u +%Y%m%d-%H%M%S)"
  BACKUP_PATH="$TARGET_DIR/backend/.ai-workbench/workspaces-${timestamp}.pre-update.backup.db"
  mkdir -p "$(dirname "$BACKUP_PATH")"
  cp -p "$TARGET_DB" "$BACKUP_PATH"
  echo "Created pre-update backup: $BACKUP_PATH"
fi

RSYNC_ARGS=(
  -av
  --delete
  --exclude .git
  --exclude node_modules
  --exclude dist
  --exclude __pycache__
  --exclude .pytest_cache
  --exclude .venv
  --exclude backend/.ai-workbench
  --exclude '*.db'
  --exclude '*.sqlite'
  --exclude '*.tsbuildinfo'
)

if [[ "$DRY_RUN" == "1" ]]; then
  RSYNC_ARGS+=(--dry-run --itemize-changes)
fi

rsync "${RSYNC_ARGS[@]}" "$SOURCE_DIR/" "$TARGET_DIR/"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry-run complete. No files were changed. Run again without --dry-run to apply."
else
  echo "Update applied. Runtime DB preserved. Run scripts/check_runtime.sh after starting the backend."
  if [[ -n "$BACKUP_PATH" ]]; then
    echo "Pre-update DB backup: $BACKUP_PATH"
  fi
fi
