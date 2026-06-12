#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_TSX="$ROOT_DIR/frontend/src/App.tsx"
LIB_RS="$ROOT_DIR/frontend/src-tauri/src/lib.rs"

blockers=0
review_items=0

echo "AI Private Workspace packaged app first-run UI check"
echo "Project root: $ROOT_DIR"
echo

require_contains() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if grep -Fq "$needle" "$file"; then
    echo "✅ $label"
  else
    echo "❌ $label"
    blockers=$((blockers + 1))
  fi
}

require_contains "$APP_TSX" "loadWorkspacesRequestIdRef" "workspace overview requests are race-safe"
require_contains "$APP_TSX" "waitForBackendApi" "packaged UI waits for backend /health before loading workspaces"
require_contains "$APP_TSX" "Desktop backend did not become reachable" "packaged UI has a clear backend readiness failure message"
require_contains "$APP_TSX" "desktop-startup-banner" "packaged UI renders desktop startup status"
require_contains "$APP_TSX" "No projects yet" "first-run empty state is explicit and not mistaken for a crash"
require_contains "$APP_TSX" "The desktop backend is running" "first-run empty state explains backend is ready"
require_contains "$APP_TSX" "setWorkspacesError(null);" "successful backend readiness clears stale backend errors"
require_contains "$LIB_RS" "desktop-supervisor.log" "Tauri supervisor writes startup diagnostics before backend launch"
require_contains "$LIB_RS" "App-owned frozen backend runtime is healthy" "Tauri records successful /health readiness"

if [ -d "$HOME/Library/Application Support/AI Private Workspace/logs" ]; then
  echo "ℹ️  Local app logs directory exists: $HOME/Library/Application Support/AI Private Workspace/logs"
  review_items=$((review_items + 1))
fi

echo
echo "Summary: ${blockers} blocker(s), ${review_items} review item(s)"
if [ "$blockers" -ne 0 ]; then
  exit 1
fi
