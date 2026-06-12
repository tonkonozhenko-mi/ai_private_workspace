#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="AI Private Workspace"
BUILD_DIR="$ROOT_DIR/build/macos"
APP_DIR="$BUILD_DIR/${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_RESOURCES_DIR="$RESOURCES_DIR/app"
FRONTEND_DIST="$ROOT_DIR/frontend/dist"
STAGED_RUNTIME_DIR="$ROOT_DIR/build/desktop/backend-runtime"
RUNTIME_MANIFEST="$STAGED_RUNTIME_DIR/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"

fail() {
  echo "❌ $1" >&2
  exit 1
}

[ -d "$ROOT_DIR/backend" ] || fail "backend/ directory not found. Run this from the ai_workspace project root."
[ -d "$ROOT_DIR/frontend" ] || fail "frontend/ directory not found. Run this from the ai_workspace project root."
[ -d "$FRONTEND_DIST" ] || fail "frontend/dist not found. Run: cd frontend && npm ci && npm run build"
if [ ! -f "$RUNTIME_MANIFEST" ] || [ ! -x "$STAGED_RUNTIME_DIR/run_backend.sh" ]; then
  echo "ℹ️ Staged backend runtime not found. Generating source runtime stage first."
  "$ROOT_DIR/scripts/stage_backend_runtime.sh"
fi
[ -f "$RUNTIME_MANIFEST" ] || fail "staged backend runtime manifest was not generated."
[ -x "$STAGED_RUNTIME_DIR/run_backend.sh" ] || fail "staged backend runtime launcher was not generated."

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$APP_RESOURCES_DIR/frontend" "$APP_RESOURCES_DIR/backend" "$RESOURCES_DIR/logs"

cat > "$CONTENTS_DIR/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>AI Private Workspace</string>
  <key>CFBundleDisplayName</key>
  <string>AI Private Workspace</string>
  <key>CFBundleIdentifier</key>
  <string>local.ai-private-workspace.app</string>
  <key>CFBundleVersion</key>
  <string>0.1.0-foundation</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleExecutable</key>
  <string>AI Private Workspace</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
</dict>
</plist>
PLIST

cat > "$MACOS_DIR/$APP_NAME" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail

# Foundation macOS launcher wired to the desktop supervisor contract.
# It starts only the app-owned backend, waits for /health, writes readable logs,
# and refuses to kill unknown processes when the target port is busy.

APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$APP_ROOT/Resources"
APP_DIR="$RESOURCES_DIR/app"
BACKEND_DIR="$APP_DIR/backend-runtime/app"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="${AI_PRIVATE_WORKSPACE_PORT:-8000}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
APP_DATA_DIR="${AI_WORKSPACE_APP_DATA_DIR:-$HOME/Library/Application Support/AI Private Workspace}"
LOG_DIR="$APP_DATA_DIR/logs"
LAUNCHER_LOG="$LOG_DIR/macos-app-launcher.log"
BACKEND_LOG="$LOG_DIR/backend.log"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
BACKEND_PID=""

mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "$LAUNCHER_LOG"; }

port_busy() {
  python3 - "$BACKEND_HOST" "$BACKEND_PORT" <<'PYPORT'
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.3)
try:
    sys.exit(0 if s.connect_ex((host, port)) == 0 else 1)
finally:
    s.close()
PYPORT
}

health_ready() {
  curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1
}

open_ui() {
  if command -v open >/dev/null 2>&1; then
    open "$FRONTEND_DIR/index.html"
  else
    log "Open this file manually: $FRONTEND_DIR/index.html"
  fi
}

cleanup_note() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "App-owned backend is running with PID $BACKEND_PID. It will keep serving the UI after launch."
  fi
}
trap cleanup_note EXIT

log "Preparing AI Private Workspace macOS app foundation"
log "App resources: $APP_DIR"
log "App data: $APP_DATA_DIR"
log "Logs: $LOG_DIR"
log "Backend health: $BACKEND_URL/health"

if [[ ! -d "$BACKEND_DIR" ]]; then
  log "ERROR: packaged backend is missing: $BACKEND_DIR"
  exit 1
fi

if [[ ! -f "$FRONTEND_DIR/index.html" ]]; then
  log "ERROR: packaged frontend is missing: $FRONTEND_DIR/index.html"
  exit 1
fi

if health_ready; then
  log "Backend is already healthy at $BACKEND_URL. Opening UI."
  open_ui
  exit 0
fi

if port_busy; then
  log "ERROR: $BACKEND_HOST:$BACKEND_PORT is busy, but it is not responding like AI Private Workspace."
  log "Refusing to kill an unknown process. Close the other app or use AI_PRIVATE_WORKSPACE_PORT to choose a different port."
  exit 2
fi

log "Starting app-owned backend on $BACKEND_HOST:$BACKEND_PORT"
(
  cd "$BACKEND_DIR"
  export APP_ENV="desktop"
  export HOST="$BACKEND_HOST"
  export PORT="$BACKEND_PORT"
  export AI_WORKSPACE_APP_DATA_DIR="$APP_DATA_DIR"
  export AI_WORKBENCH_DB_PATH="${AI_WORKBENCH_DB_PATH:-$APP_DATA_DIR/workspace.db}"
  export CORS_ALLOWED_ORIGINS="http://127.0.0.1:${BACKEND_PORT},http://localhost:${BACKEND_PORT},tauri://localhost,file://"
  python3 -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
printf '%s\n' "$BACKEND_PID" > "$BACKEND_PID_FILE"
log "Backend PID: $BACKEND_PID"

log "Waiting for backend health"
for _ in $(seq 1 80); do
  if health_ready; then
    log "Backend is ready. Opening packaged UI."
    open_ui
    exit 0
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "ERROR: backend exited before becoming healthy. Check $BACKEND_LOG"
    exit 3
  fi
  sleep 0.5
done

log "ERROR: backend did not become healthy in time. Check $BACKEND_LOG"
exit 4
LAUNCHER
chmod +x "$MACOS_DIR/$APP_NAME"

rsync -a --delete "$FRONTEND_DIST/" "$APP_RESOURCES_DIR/frontend/"
rsync -a --delete "$STAGED_RUNTIME_DIR/" "$APP_RESOURCES_DIR/backend-runtime/"

cp "$RUNTIME_MANIFEST" "$APP_RESOURCES_DIR/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"

cat > "$APP_RESOURCES_DIR/README_PACKAGE_FOUNDATION.txt" <<EOF
AI Private Workspace macOS package foundation

This is a foundation bundle for packaging validation, not the final signed app.
It stages:
- static frontend assets from frontend/dist
- staged backend runtime from build/desktop/backend-runtime
- backend runtime manifest from build/desktop/backend-runtime
- a temporary launcher stub wired to the staged source runtime

Runtime data is expected outside the app bundle, for example:
~/Library/Application Support/AI Private Workspace/workspace.db

Next step: replace this temporary launcher with a real Tauri shell/supervisor.
EOF

echo "✅ macOS app foundation created: $APP_DIR"
echo "Open with: open '$APP_DIR'"
echo "Note: this is not a signed installer and not the final Tauri app yet."
