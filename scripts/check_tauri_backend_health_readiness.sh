#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/lib.rs"
BLOCKERS=0
REVIEWS=0

fail() { echo "❌ $1" >&2; BLOCKERS=$((BLOCKERS + 1)); }
review() { echo "⚠️  $1" >&2; REVIEWS=$((REVIEWS + 1)); }
ok() { echo "✅ $1"; }

[ -f "$TAURI_MAIN" ] || fail "Tauri main.rs missing: frontend/src-tauri/src/lib.rs"

if [ -f "$TAURI_MAIN" ]; then
  grep -q "backend_health_is_ready" "$TAURI_MAIN" && ok "HTTP health readiness function exists" || fail "Missing backend_health_is_ready"
  grep -q "GET /health HTTP/1.1" "$TAURI_MAIN" && ok "Readiness sends HTTP GET /health" || fail "Readiness must send HTTP GET /health"
  grep -q "wait_for_backend_health" "$TAURI_MAIN" && ok "Startup waits for /health readiness" || fail "Missing wait_for_backend_health"
  grep -q "HTTP/1.1 200" "$TAURI_MAIN" && ok "Readiness requires HTTP 200" || fail "Readiness should require HTTP 200"
  grep -q "/health did not return HTTP 200" "$TAURI_MAIN" && ok "Failed readiness has clear /health error" || fail "Missing clear /health failure message"
  grep -q "get_backend_health_readiness_contract" "$TAURI_MAIN" && ok "Read-only health contract command exists" || fail "Missing get_backend_health_readiness_contract"
  grep -q "child.kill()" "$TAURI_MAIN" && ok "Failed startup cleanup targets spawned child" || fail "Missing spawned-child cleanup on failed readiness"

  if grep -q "wait_for_backend_tcp" "$TAURI_MAIN"; then
    fail "TCP-only readiness function still exists; use HTTP /health readiness"
  else
    ok "No TCP-only readiness function remains"
  fi

  if grep -Eq "pkill|killall|taskkill|sh -c|cmd /C|powershell -Command" "$TAURI_MAIN"; then
    fail "Forbidden generic process/shell control found in Tauri supervisor"
  else
    ok "No forbidden generic process/shell control found"
  fi
fi

if ! command -v cargo >/dev/null 2>&1; then
  review "cargo is not available in this environment; run cargo check locally on the developer machine"
fi

printf '\nTauri backend health readiness check: %s blockers, %s review items\n' "$BLOCKERS" "$REVIEWS"
[ "$BLOCKERS" -eq 0 ]
