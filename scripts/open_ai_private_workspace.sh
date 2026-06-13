#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"
BUILD_STAMP="$ROOT_DIR/build/desktop/last-successful-app-build"
LAUNCH_LOG="$ROOT_DIR/build/desktop/open-ai-private-workspace.log"

mkdir -p "$ROOT_DIR/build/desktop"
exec > >(tee -a "$LAUNCH_LOG") 2>&1
printf '\n=== AI Private Workspace open request: %s ===\n' "$(date)"

launch_app() {
  if [ ! -d "$APP_PATH" ]; then
    echo "App bundle is missing: $APP_PATH" >&2
    return 1
  fi
  echo "Opening AI Private Workspace..."
  open "$APP_PATH"
  sleep 2
  osascript -e 'tell application id "local.ai-private-workspace" to activate' >/dev/null 2>&1 || true
  if ! osascript -e 'application id "local.ai-private-workspace" is running' 2>/dev/null | grep -q true; then
    echo "The app launch request completed, but the app is not running." >&2
    echo "Check: $HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log" >&2
    echo "Check: $HOME/Library/Application Support/AI Private Workspace/logs/backend.log" >&2
    return 1
  fi
  echo "Launch request completed. App log: $HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log"
}

needs_build=false
if [ ! -d "$APP_PATH" ] || [ ! -f "$BUILD_STAMP" ]; then
  needs_build=true
elif find \
  "$ROOT_DIR/backend/app" \
  "$ROOT_DIR/frontend/src" \
  "$ROOT_DIR/frontend/src-tauri" \
  "$ROOT_DIR/scripts" \
  "$ROOT_DIR/backend/requirements.txt" \
  "$ROOT_DIR/frontend/package.json" \
  "$ROOT_DIR/frontend/package-lock.json" \
  -type f -newer "$BUILD_STAMP" -print -quit | grep -q .; then
  needs_build=true
fi

if [ "$needs_build" = true ]; then
  echo "Updates detected. Building AI Private Workspace before launch..."
  exec "$ROOT_DIR/scripts/build_and_open_ai_private_workspace.sh"
fi

echo "No updates detected. Opening AI Private Workspace..."
launch_app
