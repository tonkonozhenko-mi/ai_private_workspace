#!/usr/bin/env bash
# Default generated bundle: AI Private Workspace.app
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="${APP_NAME:-AI Private Workspace}"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/Applications}"
APP_DIR="$OUTPUT_DIR/$APP_NAME.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RESOURCES_DIR="$APP_DIR/Contents/Resources"
EXECUTABLE="$MACOS_DIR/$APP_NAME"
PLIST="$APP_DIR/Contents/Info.plist"
LAUNCHER="$ROOT_DIR/scripts/launch_macos.command"

fail_with_next_step() {
  echo "ERROR: $1" >&2
  echo >&2
  echo "Next step:" >&2
  echo "  $2" >&2
  echo >&2
  echo "Nothing was started." >&2
  exit 1
}

[[ -f "$LAUNCHER" ]] || fail_with_next_step "scripts/launch_macos.command was not found." "Run this script from the project scripts/ directory."
[[ -x "$LAUNCHER" ]] || fail_with_next_step "scripts/launch_macos.command is not executable." "chmod +x scripts/launch_macos.command scripts/create_macos_shortcut.sh"

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

cat > "$EXECUTABLE" <<APP
#!/usr/bin/env bash
# Default generated bundle: AI Private Workspace.app
set -euo pipefail
cd "$ROOT_DIR"
exec "$LAUNCHER"
APP
chmod +x "$EXECUTABLE"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>local.ai-private-workspace.launcher</string>
  <key>CFBundleVersion</key>
  <string>0.1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

cat <<INFO
Created macOS launcher app:
  $APP_DIR

What this app does:
  - opens the existing launch_macos.command helper;
  - asks for confirmation before starting backend/frontend;
  - does not start services by itself during shortcut creation;
  - does not install models, scan projects, rebuild indexes, or execute MCP/agent tools.

Optional next steps:
  - Open Finder: open "$OUTPUT_DIR"
  - Drag "$APP_NAME" to the Dock if you want a Dock shortcut.
INFO
