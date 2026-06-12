#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BLOCKERS=0

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "BLOCKER missing file: $path"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

require_text() {
  local path="$1"
  local text="$2"
  if ! grep -Fq "$text" "$path"; then
    echo "BLOCKER missing text in $path: $text"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

require_absent_text() {
  local path="$1"
  local text="$2"
  if grep -Fq "$text" "$path"; then
    echo "BLOCKER forbidden text in $path: $text"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

require_file "docs/TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md"
require_file "scripts/build_pyinstaller_backend_runtime.sh"
require_file "scripts/check_pyinstaller_backend_runtime.sh"
require_file "scripts/smoke_frozen_backend_runtime.sh"
require_file "scripts/check_tauri_app_owned_backend_startup.sh"
require_file "frontend/src-tauri/src/main.rs"

require_text "docs/TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md" "macOS frozen runtime and Tauri smoke runbook"
require_text "docs/TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md" "frontend does not execute shell commands"
require_text "docs/TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md" "No scan, index, rebuild, MCP, Agent, or model download starts on launch"
require_text "frontend/src-tauri/src/main.rs" "start_app_owned_backend_runtime"
require_text "frontend/src-tauri/src/main.rs" "stop_app_owned_backend_runtime"
require_text "frontend/src-tauri/src/main.rs" "get_app_owned_backend_process_status"
require_absent_text "frontend/src-tauri/src/main.rs" "pkill"
require_absent_text "frontend/src-tauri/src/main.rs" "killall"
require_absent_text "frontend/src-tauri/src/main.rs" "taskkill"
require_absent_text "frontend/src-tauri/src/main.rs" "sh -c"
require_absent_text "frontend/src-tauri/src/main.rs" "cmd /C"

if [[ "$BLOCKERS" -gt 0 ]]; then
  echo "macOS Tauri smoke runbook check failed: $BLOCKERS blocker(s)"
  exit 1
fi

echo "macOS Tauri smoke runbook check passed: 0 blockers"
