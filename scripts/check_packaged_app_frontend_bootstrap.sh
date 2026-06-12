#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_TSX="$ROOT_DIR/frontend/src/App.tsx"
DESKTOP_RUNTIME="$ROOT_DIR/frontend/src/desktopRuntime.ts"
LIB_RS="$ROOT_DIR/frontend/src-tauri/src/lib.rs"

blockers=0
reviews=0

check_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -Fq "$pattern" "$file"; then
    echo "✅ $label"
  else
    echo "❌ $label"
    blockers=$((blockers + 1))
  fi
}

echo "AI Private Workspace packaged app frontend bootstrap check"
echo "Project root: $ROOT_DIR"
echo

[[ -f "$DESKTOP_RUNTIME" ]] || { echo "❌ frontend/src/desktopRuntime.ts is missing"; blockers=$((blockers + 1)); }
[[ -f "$APP_TSX" ]] || { echo "❌ frontend/src/App.tsx is missing"; blockers=$((blockers + 1)); }
[[ -f "$LIB_RS" ]] || { echo "❌ frontend/src-tauri/src/lib.rs is missing"; blockers=$((blockers + 1)); }

if [[ -f "$DESKTOP_RUNTIME" ]]; then
  check_contains "$DESKTOP_RUNTIME" "window as typeof window & { __TAURI__?" "desktopRuntime detects Tauri without browser dependency"
  check_contains "$DESKTOP_RUNTIME" "start_app_owned_backend_runtime" "desktopRuntime invokes app-owned backend startup"
  check_contains "$DESKTOP_RUNTIME" "get_app_owned_backend_process_status" "desktopRuntime checks process status before startup"
fi

if [[ -f "$APP_TSX" ]]; then
  check_contains "$APP_TSX" "ensureAppOwnedBackendRuntime" "App calls desktop backend bootstrap before workspace load"
  check_contains "$APP_TSX" "Starting local desktop backend" "App exposes desktop startup status"
fi

if [[ -f "$LIB_RS" ]]; then
  check_contains "$LIB_RS" "start_app_owned_backend_runtime" "Tauri command for app-owned backend startup exists"
  check_contains "$LIB_RS" "GET /health HTTP/1.1" "Tauri startup waits for HTTP /health"
fi

if grep -R "@tauri-apps/api" "$ROOT_DIR/frontend/src" >/dev/null 2>&1; then
  echo "ℹ️ frontend imports @tauri-apps/api; make sure package-lock stays public-registry only"
  reviews=$((reviews + 1))
else
  echo "✅ frontend uses injected Tauri global without adding a new npm dependency"
fi

echo
echo "Summary: ${blockers} blocker(s), ${reviews} review item(s)"
[[ "$blockers" -eq 0 ]]
