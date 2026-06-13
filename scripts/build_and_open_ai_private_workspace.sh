#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_step() {
  local label="$1"
  shift
  printf '\n▶ %s\n' "$label"
  "$@"
  printf '✅ %s\n' "$label"
}

stop_running_app_for_update() {
  if ! osascript -e 'application id "local.ai-private-workspace" is running' 2>/dev/null | grep -q true; then
    return 0
  fi

  printf '\nClosing the running AI Private Workspace before opening the updated build...\n'
  osascript -e 'tell application id "local.ai-private-workspace" to quit' >/dev/null 2>&1 || true
  for _ in {1..20}; do
    if ! osascript -e 'application id "local.ai-private-workspace" is running' 2>/dev/null | grep -q true; then
      return 0
    fi
    sleep 0.5
  done

  printf '❌ AI Private Workspace did not close in time. No process was force-killed.\n' >&2
  return 1
}

run_step "Check backend source" bash -lc 'cd backend && python3 -m compileall -q app tests'
if [ -d "$ROOT_DIR/frontend/node_modules" ]; then
  run_step "Build frontend" bash -lc 'cd frontend && npm run typecheck && npm run build'
else
  run_step "Install and build frontend" bash -lc 'cd frontend && npm ci && npm run typecheck && npm run build'
fi
run_step "Build frozen backend" ./scripts/build_pyinstaller_backend_runtime.sh
run_step "Check frozen backend" ./scripts/check_pyinstaller_backend_runtime.sh
run_step "Smoke frozen backend" env \
  AI_PRIVATE_WORKSPACE_PORT="${AI_PRIVATE_WORKSPACE_BUILD_SMOKE_PORT:-8012}" \
  AI_PRIVATE_WORKSPACE_SMOKE_LOG_DIR="$ROOT_DIR/build/desktop/build-smoke-logs" \
  ./scripts/smoke_frozen_backend_runtime.sh
run_step "Build macOS app" bash -lc 'cd frontend && npm run tauri:build'

APP_PATH="$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"
mkdir -p "$ROOT_DIR/build/desktop"
touch "$ROOT_DIR/build/desktop/last-successful-app-build"
stop_running_app_for_update
printf '\n✅ Ready. Opening app:\n%s\n' "$APP_PATH"
open "$APP_PATH"
sleep 2
osascript -e 'tell application id "local.ai-private-workspace" to activate' >/dev/null 2>&1 || true
if ! osascript -e 'application id "local.ai-private-workspace" is running' 2>/dev/null | grep -q true; then
  printf '\n❌ The app bundle was built, but macOS does not report it as running.\n' >&2
  printf 'Check: %s\n' "$HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log" >&2
  printf 'Check: %s\n' "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log" >&2
  exit 1
fi
