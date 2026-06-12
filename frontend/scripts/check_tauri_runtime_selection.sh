#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
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
check_absent() {
  local file="$1" pattern="$2" label="$3"
  if grep -Fq "$pattern" "$file"; then
    echo "blocker: forbidden $label"
    BLOCKERS=$((BLOCKERS + 1))
  else
    echo "ok: no $label"
  fi
}
check_contains "$TAURI_MAIN" "get_runtime_selection_status" "runtime selection command"
check_contains "$TAURI_MAIN" "start_app_owned_backend_runtime" "app-owned backend startup command"
check_contains "$TAURI_MAIN" "stop_app_owned_backend_runtime" "PID-owned backend shutdown command"
check_contains "$TAURI_MAIN" "frozen-pyinstaller-runtime" "frozen runtime candidate"
check_contains "$TAURI_MAIN" "staged-source-runtime" "staged runtime fallback documentation"
check_contains "$TAURI_MAIN" "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" "frozen manifest path"
check_contains "$TAURI_MAIN" "resolve_frozen_backend_executable" "frozen manifest executable resolver"
check_contains "$TAURI_MAIN" "port_8000_is_busy" "safe occupied-port check"
check_absent "$TAURI_MAIN" "pkill" "pkill"
check_absent "$TAURI_MAIN" "killall" "killall"
check_absent "$TAURI_MAIN" "taskkill" "taskkill"
check_absent "$TAURI_MAIN" "sh -c" "shell string execution"
check_absent "$TAURI_MAIN" "cmd /C" "cmd shell execution"
echo "summary: $BLOCKERS blockers, $REVIEW review items"
if [ "$BLOCKERS" -ne 0 ]; then exit 1; fi
