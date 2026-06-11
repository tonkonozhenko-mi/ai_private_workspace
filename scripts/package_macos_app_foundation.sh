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

fail() {
  echo "❌ $1" >&2
  exit 1
}

[ -d "$ROOT_DIR/backend" ] || fail "backend/ directory not found. Run this from the ai_workspace project root."
[ -d "$ROOT_DIR/frontend" ] || fail "frontend/ directory not found. Run this from the ai_workspace project root."
[ -d "$FRONTEND_DIST" ] || fail "frontend/dist not found. Run: cd frontend && npm ci && npm run build"

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

APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$APP_ROOT/Resources"
APP_DIR="$RESOURCES_DIR/app"
LOG_DIR="$RESOURCES_DIR/logs"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="${AI_PRIVATE_WORKSPACE_PORT:-8000}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
BACKEND_LOG="$LOG_DIR/backend.log"

mkdir -p "$LOG_DIR"

if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
  echo "AI Private Workspace package is incomplete." | tee "$LOG_DIR/launch-error.log"
  echo "Expected backend and frontend resources under: $APP_DIR" | tee -a "$LOG_DIR/launch-error.log"
  exit 1
fi

echo "Starting AI Private Workspace foundation package..." | tee "$LOG_DIR/launcher.log"
echo "Logs: $LOG_DIR" | tee -a "$LOG_DIR/launcher.log"
echo "Backend URL: $BACKEND_URL" | tee -a "$LOG_DIR/launcher.log"

if curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
  echo "Backend already healthy at $BACKEND_URL" | tee -a "$LOG_DIR/launcher.log"
else
  echo "Starting packaged backend source with local Python..." | tee -a "$LOG_DIR/launcher.log"
  (
    cd "$BACKEND_DIR"
    export AI_WORKBENCH_DB_PATH="${AI_WORKBENCH_DB_PATH:-$HOME/Library/Application Support/AI Private Workspace/workspace.db}"
    export CORS_ALLOWED_ORIGINS="http://127.0.0.1:${BACKEND_PORT},http://localhost:${BACKEND_PORT},tauri://localhost"
    python3 -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  ) > "$BACKEND_LOG" 2>&1 &
fi

for _ in {1..40}; do
  if curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
    echo "Backend is ready." | tee -a "$LOG_DIR/launcher.log"
    break
  fi
  sleep 0.5
done

if ! curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
  echo "Backend did not become ready. Check: $BACKEND_LOG" | tee -a "$LOG_DIR/launch-error.log"
  exit 1
fi

if command -v open >/dev/null 2>&1; then
  open "$FRONTEND_DIR/index.html"
else
  echo "Open this file manually: $FRONTEND_DIR/index.html" | tee -a "$LOG_DIR/launcher.log"
fi
LAUNCHER
chmod +x "$MACOS_DIR/$APP_NAME"

rsync -a --delete "$FRONTEND_DIST/" "$APP_RESOURCES_DIR/frontend/"
rsync -a --delete \
  --exclude '.ai-workbench/' \
  --exclude '*.db' \
  --exclude '*.sqlite' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.venv/' \
  "$ROOT_DIR/backend/" "$APP_RESOURCES_DIR/backend/"

cat > "$APP_RESOURCES_DIR/README_PACKAGE_FOUNDATION.txt" <<EOF
AI Private Workspace macOS package foundation

This is a foundation bundle for packaging validation, not the final signed app.
It stages:
- static frontend assets from frontend/dist
- backend source without runtime data
- a temporary launcher stub

Runtime data is expected outside the app bundle, for example:
~/Library/Application Support/AI Private Workspace/workspace.db

Next step: replace this temporary launcher with a real Tauri shell/supervisor.
EOF

echo "✅ macOS app foundation created: $APP_DIR"
echo "Open with: open '$APP_DIR'"
echo "Note: this is not a signed installer and not the final Tauri app yet."
