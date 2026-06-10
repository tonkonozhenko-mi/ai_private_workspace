#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/apply_generated_update.sh /path/to/unzipped/update /path/to/ai_workspace"
  echo "Example: scripts/apply_generated_update.sh ~/Documents/ai_workspace_task176_work ~/Documents/ai_workspace"
  exit 1
fi

SOURCE_DIR="$1"
TARGET_DIR="$2"

if [[ ! -d "$SOURCE_DIR/backend" || ! -d "$SOURCE_DIR/frontend" ]]; then
  echo "Source must contain backend/ and frontend/ at its root."
  exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target directory does not exist: $TARGET_DIR"
  exit 1
fi

echo "Applying generated update safely"
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"
echo "Runtime data is protected: backend/.ai-workbench, *.db, *.sqlite"

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
  "$SOURCE_DIR/" \
  "$TARGET_DIR/"

echo "Update applied. Run scripts/check_runtime.sh after starting the backend."
