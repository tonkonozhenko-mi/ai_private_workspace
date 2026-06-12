#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_LIB="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
BLOCKERS=0
check_contains() { local file="$1" pattern="$2" label="$3"; if grep -Fq "$pattern" "$file"; then echo "ok: $label"; else echo "blocker: missing $label"; BLOCKERS=$((BLOCKERS + 1)); fi; }
check_contains "$TAURI_LIB" "get_app_owned_startup_gate" "app-owned startup gate command"
check_contains "$TAURI_LIB" "backend_start_enabled: true" "backend startup enabled after frozen manifest gate"
check_contains "$TAURI_LIB" "frozen-pyinstaller-runtime" "frozen runtime preference"
check_contains "$TAURI_LIB" "manifest_gated_app_owned_backend_process" "manifest-gated startup mode"
check_contains "$TAURI_LIB" "do not kill it" "no kill-by-port contract"
check_contains "$TAURI_LIB" "Open UI only after /health" "health gate contract"
check_contains "$TAURI_LIB" "resolve_frozen_backend_executable" "frozen manifest resolver"
if grep -Eq "pkill|killall|taskkill|sh -c|cmd /C|powershell -Command" "$TAURI_LIB"; then echo "blocker: forbidden generic process/shell control"; BLOCKERS=$((BLOCKERS + 1)); else echo "ok: no forbidden generic process/shell control"; fi
echo "summary: $BLOCKERS blockers"
[ "$BLOCKERS" -eq 0 ]
