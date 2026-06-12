#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODELS_DETAIL="frontend/src/components/ModelsDetail.tsx"
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

echo "AI Private Workspace runtime readiness UX source-contract smoke"

require_text "$MODELS_DETAIL" "RuntimeNextActionPanel" "Models screen has an inline runtime action panel"
require_text "$MODELS_DETAIL" "Search context runtime does not match this workspace." "Runtime mismatch explains exact problem"
require_text "$MODELS_DETAIL" "Use active search model" "Runtime mismatch has a primary action button"
require_text "$MODELS_DETAIL" "Re-check runtime" "Runtime state can be refreshed in place"
require_text "$MODELS_DETAIL" "Build context now" "Context-build state has direct action"
require_text "$MODELS_DETAIL" "updateWorkspaceModelSelection(workspaceId" "Primary action uses backend API, not shell"
require_text "$MODELS_DETAIL" "Fastest way to continue now" "UI gives immediate path to continue using the app"
require_text "$STYLES" ".runtime-next-action-panel" "Runtime action panel has dedicated styling"

forbid_pattern "frontend/src" 'child_process|execSync|spawnSync|Deno\.Command|Bun\.spawn|ollama pull' "Frontend still has no shell/model-pull execution"

if [[ "$BLOCKERS" -ne 0 ]]; then
  printf 'Summary: %s blocker(s)\n' "$BLOCKERS"
  exit 1
fi

echo "Summary: 0 blockers"
