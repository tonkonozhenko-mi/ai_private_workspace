#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
TAURI_LIB="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
TAURI_CONFIG="$ROOT_DIR/frontend/src-tauri/tauri.conf.json"
CARGO_TOML="$ROOT_DIR/frontend/src-tauri/Cargo.toml"
failures=0
reviews=0
ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace Tauri supervisor bridge check\nProject root: %s\n\n' "$ROOT_DIR"
[ -f "$TAURI_MAIN" ] && ok "Tauri main.rs found" || fail "frontend/src-tauri/src/main.rs missing"
[ -f "$TAURI_LIB" ] && ok "Tauri lib.rs found" || fail "frontend/src-tauri/src/lib.rs missing"
[ -f "$TAURI_CONFIG" ] && ok "tauri.conf.json found" || fail "frontend/src-tauri/tauri.conf.json missing"
[ -f "$CARGO_TOML" ] && ok "Cargo.toml found" || fail "frontend/src-tauri/Cargo.toml missing"

if [ -f "$TAURI_MAIN" ]; then
  grep -q 'ai_private_workspace_lib::run();' "$TAURI_MAIN" && ok "main.rs delegates to library run()" || fail "main.rs must delegate to ai_private_workspace_lib::run()"
fi
if [ -f "$TAURI_LIB" ]; then
  grep -q 'fn get_supervisor_status' "$TAURI_LIB" && ok "get_supervisor_status command exists" || fail "get_supervisor_status command missing"
  grep -q 'fn get_supervisor_log_paths' "$TAURI_LIB" && ok "get_supervisor_log_paths command exists" || fail "get_supervisor_log_paths command missing"
  grep -q 'fn get_supervisor_preflight' "$TAURI_LIB" && ok "get_supervisor_preflight command exists" || fail "get_supervisor_preflight command missing"
  grep -q 'start_app_owned_backend_runtime' "$TAURI_LIB" && ok "app-owned backend startup command exists" || fail "app-owned backend startup command missing"
  grep -q 'AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json' "$TAURI_LIB" && ok "startup is manifest-gated" || fail "frozen manifest gate missing"
  grep -q 'Do not start scan, index, rebuild, MCP, Agent, or model downloads' "$TAURI_LIB" && ok "launch safety contract is embedded" || fail "launch safety contract missing"
  grep -q '127.0.0.1:8000/health' "$TAURI_LIB" && ok "localhost health URL is fixed" || fail "localhost health URL missing"
  if grep -Eq 'pkill|killall|taskkill|sh -c|cmd /C|powershell -Command' "$TAURI_LIB"; then
    fail "forbidden generic process/shell control found"
  else
    ok "no forbidden generic process/shell control found"
  fi
fi
if [ -f "$TAURI_CONFIG" ]; then
  grep -q 'frontendDist' "$TAURI_CONFIG" && ok "Tauri config points to frontend build output" || fail "Tauri frontendDist missing"
  grep -q '"active": false' "$TAURI_CONFIG" && review "Tauri bundle remains inactive; expected until signed installer stage"
fi
printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
[ "$failures" -eq 0 ]
