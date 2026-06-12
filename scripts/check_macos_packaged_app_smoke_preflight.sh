#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BLOCKERS=0
REVIEWS=0

check_file() {
  local path="$1"
  local message="$2"
  if [[ -f "$path" ]]; then
    echo "✅ $message: $path"
  else
    echo "❌ Missing $message: $path"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

check_contains() {
  local path="$1"
  local needle="$2"
  local message="$3"
  if grep -Fq "$needle" "$path"; then
    echo "✅ $message"
  else
    echo "❌ $message"
    echo "   Expected to find: $needle"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

check_file "frontend/package.json" "frontend package manifest"
check_file "frontend/package-lock.json" "frontend lockfile"
check_file "frontend/src-tauri/Cargo.toml" "Tauri Cargo manifest"
check_file "frontend/src-tauri/tauri.conf.json" "Tauri config"
check_file "frontend/src-tauri/src/lib.rs" "Tauri supervisor bridge"
check_file "scripts/build_pyinstaller_backend_runtime.sh" "PyInstaller build script"
check_file "scripts/smoke_frozen_backend_runtime.sh" "frozen backend smoke script"
check_file "scripts/check_tauri_backend_health_readiness.sh" "Tauri health readiness check"
check_file "docs/TASK251_MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md" "Task 251 runbook"

check_contains "frontend/package.json" '"@tauri-apps/cli"' "Tauri CLI is pinned as an npm devDependency"
check_contains "frontend/package.json" '"tauri": "tauri"' "npm run tauri dev command is available"
check_contains "frontend/package.json" '"tauri:dev": "tauri dev"' "npm run tauri:dev alias is available"
check_contains "frontend/package.json" '"tauri:build": "tauri build"' "npm run tauri:build alias is available"
check_contains "frontend/package-lock.json" 'node_modules/@tauri-apps/cli' "package-lock includes Tauri CLI packages for npm ci"
check_contains "frontend/src-tauri/src/lib.rs" 'GET /health HTTP/1.1' "Tauri startup waits for HTTP /health"
check_contains "frontend/src-tauri/src/lib.rs" 'start_app_owned_backend_runtime' "Tauri app-owned backend startup command exists"
check_contains "frontend/src-tauri/src/lib.rs" 'stop_app_owned_backend_runtime' "Tauri PID-owned shutdown command exists"
check_contains "frontend/src-tauri/src/lib.rs" 'AI_WORKBENCH_DB_PATH' "Tauri passes app-owned DB path to backend"
check_contains "docs/CONTINUE_MESSAGE.md" 'Task 253' "continuation checkpoint includes Task 251"

if [[ -f "build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" ]]; then
  echo "✅ Frozen backend manifest exists locally"
else
  echo "⚠️ Frozen backend manifest is not present in source archive; create it locally with scripts/build_pyinstaller_backend_runtime.sh"
  REVIEWS=$((REVIEWS + 1))
fi

if command -v cargo >/dev/null 2>&1; then
  echo "✅ cargo is available locally"
else
  echo "⚠️ cargo is not available in this environment; run cargo check on the developer Mac"
  REVIEWS=$((REVIEWS + 1))
fi

if [[ "$BLOCKERS" -gt 0 ]]; then
  echo "❌ macOS packaged app smoke preflight failed with $BLOCKERS blocker(s) and $REVIEWS review item(s)."
  exit 1
fi

echo "✅ macOS packaged app smoke preflight passed with 0 blockers and $REVIEWS review item(s)."
