#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
TAURI_CONFIG="$ROOT_DIR/frontend/src-tauri/tauri.conf.json"
CARGO_TOML="$ROOT_DIR/frontend/src-tauri/Cargo.toml"

failures=0
reviews=0

ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace Tauri supervisor bridge check\n'
printf 'Project root: %s\n\n' "$ROOT_DIR"

[ -f "$TAURI_MAIN" ] && ok "Tauri main.rs found" || fail "frontend/src-tauri/src/main.rs missing"
[ -f "$TAURI_CONFIG" ] && ok "tauri.conf.json found" || fail "frontend/src-tauri/tauri.conf.json missing"
[ -f "$CARGO_TOML" ] && ok "Cargo.toml found" || fail "frontend/src-tauri/Cargo.toml missing"

if [ -f "$TAURI_MAIN" ]; then
  grep -q 'fn get_supervisor_status' "$TAURI_MAIN" && ok "get_supervisor_status command exists" || fail "get_supervisor_status command missing"
  grep -q 'fn get_supervisor_log_paths' "$TAURI_MAIN" && ok "get_supervisor_log_paths command exists" || fail "get_supervisor_log_paths command missing"
  grep -q 'fn get_supervisor_preflight' "$TAURI_MAIN" && ok "get_supervisor_preflight command exists" || fail "get_supervisor_preflight command missing"
  grep -q 'backend_start_enabled: false' "$TAURI_MAIN" && ok "backend startup is explicitly disabled in read-only bridge" || fail "backend startup is not explicitly disabled"
  grep -q 'Do not start scan, index, rebuild, MCP, Agent, or model downloads' "$TAURI_MAIN" && ok "launch safety contract is embedded" || fail "launch safety contract missing"
  grep -q '127.0.0.1:8000/health' "$TAURI_MAIN" && ok "localhost health URL is fixed" || fail "localhost health URL missing"

  if grep -Eq 'std::process::Command|Command::new|std::process|spawn\(' "$TAURI_MAIN"; then
    fail "Tauri bridge contains process/shell execution keywords; keep Task 240 read-only"
  else
    ok "Tauri bridge has no process/shell execution calls"
  fi
fi

if [ -f "$TAURI_CONFIG" ]; then
  grep -q 'frontendDist' "$TAURI_CONFIG" && ok "Tauri config points to frontend build output" || fail "Tauri frontendDist missing"
  grep -q '"active": false' "$TAURI_CONFIG" && review "Tauri bundle remains inactive; expected until signed installer stage"
fi

printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
if [ "$failures" -gt 0 ]; then
  exit 1
fi
exit 0
