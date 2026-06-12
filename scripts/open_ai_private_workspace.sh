#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PATH="$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"

if [ ! -d "$APP_PATH" ]; then
  echo "AI Private Workspace.app is not built yet."
  echo "Run one time: ./scripts/build_and_open_ai_private_workspace.sh"
  exit 1
fi

open "$APP_PATH"
