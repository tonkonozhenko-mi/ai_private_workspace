#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
BLOCKERS=0
REVIEW=0
check_contains() {
  local file="$1" pattern="$2" label="$3"
  if grep -Fq "$pattern" "$file"; then
    echo "ok: $label"
  else
    echo "blocker: missing $label"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}
check_contains "$TAURI_MAIN" "get_runtime_selection_status" "runtime selection command"
check_contains "$TAURI_MAIN" "backend_start_enabled: false" "backend startup disabled"
check_contains "$TAURI_MAIN" "frozen-pyinstaller-runtime" "frozen runtime candidate"
check_contains "$TAURI_MAIN" "staged-source-runtime" "staged runtime fallback"
check_contains "$TAURI_MAIN" "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" "frozen manifest path"
if grep -Eq "Command::new|std::process|kill\(|pkill|taskkill" "$TAURI_MAIN"; then
  echo "blocker: Tauri runtime selection must not execute or kill processes yet"
  BLOCKERS=$((BLOCKERS + 1))
else
  echo "ok: no process execution API in Tauri runtime selection"
fi
echo "summary: $BLOCKERS blockers, $REVIEW review items"
if [ "$BLOCKERS" -ne 0 ]; then exit 1; fi
