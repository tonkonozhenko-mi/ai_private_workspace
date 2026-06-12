#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TAURI_SOURCE="frontend/src-tauri/src/lib.rs"
TAURI_CONFIG="frontend/src-tauri/tauri.conf.json"
SETTINGS="backend/app/config/settings.py"
REPOSITORY="backend/app/adapters/memory/sqlite_workspace_repository.py"
ENTRYPOINT="backend/packaging/pyinstaller_backend_entrypoint.py"
MAIN="backend/app/main.py"
BLOCKERS=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; BLOCKERS=$((BLOCKERS + 1)); }

require_text() {
  local file="$1"
  local text="$2"
  local label="$3"
  grep -Fq "$text" "$file" && pass "$label" || fail "$label"
}

forbid_pattern() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -Eq "$pattern" "$file"; then fail "$label"; else pass "$label"; fi
}

echo "AI Private Workspace packaged workspace API source-contract smoke"

require_text "$TAURI_CONFIG" '"identifier": "local.ai-private-workspace"' "Tauri bundle identifier does not end in .app"
require_text "$TAURI_SOURCE" 'fs::create_dir_all(data_dir())' "Tauri creates app-owned data directory"
require_text "$TAURI_SOURCE" '.env("APP_DATA_DIR", app_data_dir())' "Tauri passes canonical APP_DATA_DIR"
require_text "$TAURI_SOURCE" '.env("WORKSPACE_DB_PATH", workspace_db_path())' "Tauri passes canonical WORKSPACE_DB_PATH"
require_text "$TAURI_SOURCE" 'Resolved workspace database path' "Supervisor logs resolved database path"
require_text "$TAURI_SOURCE" '/workspaces/overview returned HTTP 200' "Supervisor verifies workspace overview after health"
require_text "$TAURI_SOURCE" 'AI Private Workspace app-owned backend start' "Backend log separates fresh app-owned launches"
require_text "$TAURI_SOURCE" 'tauri::RunEvent::Exit' "Desktop exit cleanup targets stored app-owned child"
require_text "$TAURI_SOURCE" 'libc::kill(pid as i32, libc::SIGTERM)' "Unix shutdown gracefully terminates exact app-owned PyInstaller parent PID"
require_text "$REPOSITORY" 'self.db_path.parent.mkdir(parents=True, exist_ok=True)' "Workspace repository creates database parent"
require_text "$SETTINGS" '"AI_WORKSPACE_APP_DATA_DIR"' "Backend supports legacy app-data alias"
require_text "$SETTINGS" '"AI_WORKBENCH_DB_PATH"' "Backend supports legacy database alias"
require_text "$ENTRYPOINT" 'default=app_data_dir / "data" / "workspaces.db"' "Frozen fallback uses app-owned data directory"
require_text "$SETTINGS" 'http://tauri.localhost' "Packaged Tauri origin is covered by CORS"
require_text "$MAIN" 'allow_origin_regex=' "Local packaged origins have explicit CORS regex"

forbid_pattern "$TAURI_SOURCE" 'pkill|killall|taskkill|kill-by-port|lsof -ti' "No kill-by-port or unknown-process termination"
forbid_pattern "$TAURI_SOURCE" 'Command::new\\("(sh|bash|zsh|cmd|powershell)"\\)|sh -c|cmd /C|powershell -Command' "No generic shell execution"

if [[ "$BLOCKERS" -ne 0 ]]; then
  printf 'Summary: %s blocker(s)\n' "$BLOCKERS"
  exit 1
fi

echo "Summary: 0 blockers"
