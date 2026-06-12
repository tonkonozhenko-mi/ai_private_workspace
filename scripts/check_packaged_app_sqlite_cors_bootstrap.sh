#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BLOCKERS=0
check_contains() {
  local file="$1"
  local expected="$2"
  local label="$3"
  if grep -Fq "$expected" "$file"; then
    echo "✅ $label"
  else
    echo "❌ $label"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

echo "AI Private Workspace packaged app SQLite/CORS bootstrap check"
check_contains backend/app/config/settings.py 'os.getenv("AI_WORKSPACE_APP_DATA_DIR"' "settings accepts legacy app data env alias"
check_contains backend/app/config/settings.py 'os.getenv("AI_WORKBENCH_DB_PATH"' "settings accepts legacy DB path env alias"
check_contains backend/app/config/settings.py 'http://tauri.localhost' "settings allows Tauri local origin"
check_contains backend/app/config/settings.py '"null"' "settings allows packaged webview null origin"
check_contains backend/app/main.py 'allow_origin_regex=' "CORS has local/Tauri regex"
check_contains backend/app/adapters/memory/sqlite_workspace_repository.py 'self.db_path.parent.mkdir(parents=True, exist_ok=True)' "SQLite repository creates DB parent directory"
check_contains frontend/src-tauri/src/lib.rs '.env("APP_DATA_DIR", app_data_dir())' "Tauri sets canonical APP_DATA_DIR"
check_contains frontend/src-tauri/src/lib.rs '.env("WORKSPACE_DB_PATH", app_data_dir().join("data").join("workspaces.db"))' "Tauri sets canonical WORKSPACE_DB_PATH"
check_contains frontend/src-tauri/src/lib.rs 'external_healthy' "Tauri reuses healthy existing backend instead of reporting startup failure"

if [[ "$BLOCKERS" -ne 0 ]]; then
  echo "Summary: $BLOCKERS blocker(s)"
  exit 1
fi

echo "Summary: 0 blockers"
