#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_SCRIPT="$ROOT_DIR/scripts/start_backend.sh"
FRONTEND_SCRIPT="$ROOT_DIR/scripts/start_frontend.sh"
APP_URL="${APP_URL:-http://127.0.0.1:5173}"

print_header() {
  echo "AI Private Workspace macOS launcher"
  echo "Root: $ROOT_DIR"
  echo
}

fail_with_next_step() {
  echo "ERROR: $1" >&2
  echo >&2
  echo "Next step:" >&2
  echo "  $2" >&2
  echo >&2
  echo "Nothing was started." >&2
  exit 1
}

print_header

[[ -d "$BACKEND_DIR" ]] || fail_with_next_step "backend/ was not found." "Run this file from the project scripts/ directory."
[[ -d "$FRONTEND_DIR" ]] || fail_with_next_step "frontend/ was not found." "Run this file from the project scripts/ directory."
[[ -x "$BACKEND_SCRIPT" ]] || fail_with_next_step "scripts/start_backend.sh is not executable." "chmod +x scripts/start_backend.sh scripts/start_frontend.sh scripts/launch_macos.command"
[[ -x "$FRONTEND_SCRIPT" ]] || fail_with_next_step "scripts/start_frontend.sh is not executable." "chmod +x scripts/start_backend.sh scripts/start_frontend.sh scripts/launch_macos.command"
[[ -d "$BACKEND_DIR/.venv" ]] || fail_with_next_step "backend/.venv is missing." "cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
[[ -d "$FRONTEND_DIR/node_modules" ]] || fail_with_next_step "frontend/node_modules is missing." "cd frontend && npm ci"

cat <<INFO
This launcher starts only local backend and frontend dev servers.
It does not pull models, does not scan projects, does not rebuild indexes, does not run MCP tools, or change runtime data.
Close the Terminal windows to stop the local app.
INFO

echo
read -r -p "Start AI Private Workspace now? [y/N] " answer
case "$answer" in
  y|Y|yes|YES) ;;
  *)
    echo "Cancelled. Nothing was started."
    exit 0
    ;;
esac

osascript <<OSA
Tell application "Terminal"
  activate
  do script "cd '$ROOT_DIR' && ./scripts/start_backend.sh"
  do script "cd '$ROOT_DIR' && ./scripts/start_frontend.sh"
end tell
OSA

(
  sleep 5
  open "$APP_URL" >/dev/null 2>&1 || true
) &

echo "Started backend and frontend in Terminal. Opening $APP_URL shortly."
