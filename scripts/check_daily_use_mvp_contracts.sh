#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DASHBOARD="frontend/src/components/WorkspaceDashboard.tsx"
ASK="frontend/src/components/AskWorkspace.tsx"
STYLES="frontend/src/styles.css"
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

echo "AI Private Workspace daily-use MVP source-contract smoke"

require_text "$DASHBOARD" "DailyUseStatusPanel" "Overview has a daily-use readiness panel"
require_text "$DASHBOARD" "Use it now" "Overview exposes an obvious use-now section"
require_text "$DASHBOARD" "Workspace is ready for questions" "Ready state tells user they can ask"
require_text "$DASHBOARD" "Scan project" "Daily-use panel can start scan"
require_text "$DASHBOARD" "Build search context" "Daily-use panel can start indexing"
require_text "$DASHBOARD" "Ask this workspace" "Daily-use panel can open Ask"
require_text "$DASHBOARD" "No hidden automation." "Daily-use panel repeats explicit-action safety"
require_text "$DASHBOARD" "Ask history" "Overview documents persisted Ask history"
require_text "$ASK" "initializeAskState" "Ask restores initial conversation state"
require_text "$ASK" "openConversation(latestConversation.id)" "Ask opens latest conversation automatically"
require_text "$STYLES" ".daily-use-panel" "Daily-use panel has dedicated styling"

forbid_pattern "frontend/src" 'child_process|execSync|spawnSync|Deno\.Command|Bun\.spawn|ollama pull' "Frontend still has no shell/model-pull execution"
forbid_pattern "frontend/src" 'useEffect\([^)]*startScanWorkspaceJob|useEffect\([^)]*startIndexWorkspaceJob|useEffect\([^)]*askSelectedWorkspace' "No scan/index/ask auto-run on mount"

if [[ "$BLOCKERS" -ne 0 ]]; then
  printf 'Summary: %s blocker(s)\n' "$BLOCKERS"
  exit 1
fi

echo "Summary: 0 blockers"
