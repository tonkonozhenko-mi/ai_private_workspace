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

run_step "Check backend source" bash -lc 'cd backend && python3 -m compileall -q app tests'
run_step "Build frontend" bash -lc 'cd frontend && npm ci && npm run typecheck && npm run build'
run_step "Build frozen backend" ./scripts/build_pyinstaller_backend_runtime.sh
run_step "Check frozen backend" ./scripts/check_pyinstaller_backend_runtime.sh
run_step "Smoke frozen backend" ./scripts/smoke_frozen_backend_runtime.sh
run_step "Build macOS app" bash -lc 'cd frontend && npm run tauri:build'

APP_PATH="$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"
mkdir -p "$ROOT_DIR/build/desktop"
touch "$ROOT_DIR/build/desktop/last-successful-app-build"
printf '\n✅ Ready. Opening app:\n%s\n' "$APP_PATH"
open "$APP_PATH"
