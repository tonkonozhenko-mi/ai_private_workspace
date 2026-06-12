#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
BLOCKERS=0
REVIEWS=0

fail() {
  echo "❌ $1" >&2
  BLOCKERS=$((BLOCKERS + 1))
}

review() {
  echo "⚠️  $1" >&2
  REVIEWS=$((REVIEWS + 1))
}

ok() {
  echo "✅ $1"
}

[ -f "$TAURI_MAIN" ] || fail "Tauri main.rs missing: frontend/src-tauri/src/main.rs"

if [ -f "$TAURI_MAIN" ]; then
  grep -q "fn start_app_owned_backend_runtime" "$TAURI_MAIN" && ok "start_app_owned_backend_runtime exists" || fail "Missing start_app_owned_backend_runtime command"
  grep -q "fn stop_app_owned_backend_runtime" "$TAURI_MAIN" && ok "stop_app_owned_backend_runtime exists" || fail "Missing stop_app_owned_backend_runtime command"
  grep -q "fn get_app_owned_backend_process_status" "$TAURI_MAIN" && ok "get_app_owned_backend_process_status exists" || fail "Missing process status command"
  grep -q "Command::new(&executable)" "$TAURI_MAIN" && ok "Startup uses Rust process API against selected executable" || fail "Startup should use Command::new(&executable)"
  grep -q "resolve_frozen_backend_executable" "$TAURI_MAIN" && ok "Startup is gated by frozen runtime manifest resolver" || fail "Missing frozen runtime manifest resolver"
  grep -q "backend_process_state" "$TAURI_MAIN" && ok "Backend child process state is stored for PID-owned shutdown" || fail "Missing stored backend process state"
  grep -q "port_8000_is_busy" "$TAURI_MAIN" && ok "Port occupation is detected before startup" || fail "Missing safe port occupation check"
  grep -q "wait_for_backend_health" "$TAURI_MAIN" && ok "Startup waits for HTTP /health readiness" || fail "Missing HTTP /health readiness wait"
  grep -q "child.kill" "$TAURI_MAIN" && ok "Shutdown/failed startup cleanup targets only stored child process" || fail "Missing PID-owned child shutdown"

  if grep -Eq "pkill|killall|taskkill|sh -c|cmd /C|powershell -Command" "$TAURI_MAIN"; then
    fail "Forbidden generic process/shell control found in Tauri supervisor"
  else
    ok "No forbidden generic process/shell control found"
  fi
fi

if [ ! -f "$ROOT_DIR/build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" ]; then
  review "Frozen runtime manifest is not present yet. Build locally with scripts/build_pyinstaller_backend_runtime.sh before testing real Tauri startup."
fi

printf '\nTauri app-owned backend startup check: %s blockers, %s review items\n' "$BLOCKERS" "$REVIEWS"
[ "$BLOCKERS" -eq 0 ]
