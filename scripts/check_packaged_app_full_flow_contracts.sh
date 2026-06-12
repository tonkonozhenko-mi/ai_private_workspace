#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP="frontend/src/App.tsx"
API_CLIENT="frontend/src/api/client.ts"
WORKSPACE_DASHBOARD="frontend/src/components/WorkspaceDashboard.tsx"
ASK_UI="frontend/src/components/AskWorkspace.tsx"
TAURI="frontend/src-tauri/src/lib.rs"
SETTINGS="backend/app/config/settings.py"
MAIN="backend/app/main.py"
JOB_RUNNER="backend/app/api/workspace_job_runner.py"
WORKSPACE_ROUTES="backend/app/api/routes/workspaces.py"
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
  local target="$1"
  local pattern="$2"
  local label="$3"
  if grep -REq "$pattern" "$target"; then fail "$label"; else pass "$label"; fi
}

echo "AI Private Workspace packaged full product flow source-contract smoke"

require_text "$API_CLIENT" '/jobs/scan' "Frontend scan action calls backend job API"
require_text "$API_CLIENT" '/jobs/index' "Frontend index action calls backend job API"
require_text "$API_CLIENT" '/ask-selected' "Frontend Ask action calls selected-LLM backend API"
require_text "$WORKSPACE_DASHBOARD" "Confirm and start" "Scan/index require explicit UI confirmation"
require_text "$WORKSPACE_DASHBOARD" "Nothing starts automatically." "Scan/index UI states explicit-action safety"
require_text "$ASK_UI" "submitQuestion" "Ask starts from explicit form submit"
require_text "$ASK_UI" "Could not ask the chosen workspace AI model." "Ask has endpoint-specific error state"
require_text "$ASK_UI" "index_metadata_exists_but_no_chunks_found" "Ask handles persisted-index/missing-vector diagnostic"
require_text "$WORKSPACE_DASHBOARD" "Backend job failed." "Scan/index jobs surface endpoint-specific failures"

require_text "$JOB_RUNNER" "workspace job started" "Backend logs scan/index job start"
require_text "$JOB_RUNNER" "workspace job completed" "Backend logs scan/index job completion"
require_text "$JOB_RUNNER" "workspace job failed" "Backend logs scan/index job failure"
require_text "$WORKSPACE_ROUTES" "workspace ask requested" "Backend logs explicit Ask request"
require_text "$WORKSPACE_ROUTES" "retrieved_chunks=%s" "Backend logs Ask retrieval/provider result"

require_text "$SETTINGS" "http://tauri.localhost" "Packaged Tauri origin is in CORS defaults"
require_text "$MAIN" "allow_origin_regex=" "Local packaged origins have explicit CORS coverage"
require_text "$TAURI" '.env("APP_DATA_DIR", app_data_dir())' "Tauri passes app-owned data directory"
require_text "$TAURI" '.env("WORKSPACE_DB_PATH", workspace_db_path())' "Tauri passes app-owned SQLite path"
require_text "$TAURI" "backend.log" "Tauri writes backend output to app-owned logs"
require_text "$APP" "ensureAppOwnedBackendRuntime" "Desktop startup is limited to app-owned backend bootstrap"

forbid_pattern "frontend/src" 'child_process|execSync|spawnSync|Deno\.Command|Bun\.spawn' "Frontend has no generic process/shell execution"
forbid_pattern "$TAURI" 'pkill|killall|taskkill|kill-by-port|lsof -ti' "Tauri has no kill-by-port or unknown-process termination"
forbid_pattern "$TAURI" 'Command::new\("(sh|bash|zsh|cmd|powershell)"\)|sh -c|cmd /C|powershell -Command' "Tauri has no generic shell execution"
forbid_pattern "$TAURI" '/jobs/scan|/jobs/index|/ask-selected|ollama pull' "Desktop startup cannot auto-run scan/index/ask/model pull"

if [[ "$BLOCKERS" -ne 0 ]]; then
  printf 'Summary: %s blocker(s)\n' "$BLOCKERS"
  exit 1
fi

echo "Summary: 0 blockers"
