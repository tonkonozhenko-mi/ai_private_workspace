#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"
BUILD_STAMP="$ROOT_DIR/build/desktop/last-successful-app-build"

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
open "$APP_PATH"
