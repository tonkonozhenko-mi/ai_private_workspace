#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
BLOCKERS=0
check_contains() {
  local file="$1" pattern="$2" label="$3"
  if grep -Fq "$pattern" "$file"; then
    echo "ok: $label"
  else
    echo "blocker: missing $label"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}
check_contains "$TAURI_MAIN" "get_app_owned_startup_gate" "app-owned startup gate command"
check_contains "$TAURI_MAIN" "backend_start_enabled: false" "backend startup still disabled"
check_contains "$TAURI_MAIN" "frozen-pyinstaller-runtime" "frozen runtime preference"
check_contains "$TAURI_MAIN" "manifest_gated_future_startup_no_process_start_yet" "metadata-only startup mode"
check_contains "$TAURI_MAIN" "do not kill it" "no kill-by-port contract"
check_contains "$TAURI_MAIN" "Open UI only after /health" "health gate contract"
if grep -Eq "Command::new|std::process|kill\(|pkill|killall|taskkill" "$TAURI_MAIN"; then
  echo "blocker: startup gate must not execute or kill processes yet"
  BLOCKERS=$((BLOCKERS + 1))
else
  echo "ok: startup gate remains free of process execution APIs"
fi
echo "summary: $BLOCKERS blockers"
if [ "$BLOCKERS" -ne 0 ]; then exit 1; fi
