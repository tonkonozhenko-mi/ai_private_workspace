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
  if [[ ! -f "$path" ]]; then
    echo "❌ Cannot check $message; file missing: $path"
    BLOCKERS=$((BLOCKERS + 1))
    return
  fi
  if grep -Fq "$needle" "$path"; then
    echo "✅ $message"
  else
    echo "❌ $message"
    echo "   Expected to find: $needle"
    BLOCKERS=$((BLOCKERS + 1))
  fi
}

check_not_contains() {
  local path="$1"
  local needle="$2"
  local message="$3"
  if [[ ! -f "$path" ]]; then
    echo "❌ Cannot check $message; file missing: $path"
    BLOCKERS=$((BLOCKERS + 1))
    return
  fi
  if grep -Fq "$needle" "$path"; then
    echo "❌ $message"
    echo "   Forbidden text found: $needle"
    BLOCKERS=$((BLOCKERS + 1))
  else
    echo "✅ $message"
  fi
}

check_file ".gitignore" "repository ignore file"
check_file "frontend/src-tauri/tauri.conf.json" "Tauri config"
check_file "frontend/src-tauri/Cargo.toml" "Tauri Cargo manifest"
check_file "frontend/src-tauri/Cargo.lock" "Tauri Cargo lockfile"
check_file "frontend/src-tauri/src/lib.rs" "Tauri library"
check_file "frontend/src-tauri/icons/icon.png" "Tauri RGBA app icon"
check_file "frontend/package.json" "frontend package manifest"
check_file "frontend/package-lock.json" "frontend npm lockfile"
check_file "scripts/build_pyinstaller_backend_runtime.sh" "PyInstaller backend build script"
check_file "scripts/check_pyinstaller_backend_runtime.sh" "frozen backend runtime check script"
check_file "scripts/smoke_frozen_backend_runtime.sh" "frozen backend smoke script"
check_file "scripts/check_tauri_backend_health_readiness.sh" "Tauri health readiness check script"
check_file "scripts/check_tauri_icon_assets.sh" "Tauri icon asset check script"

check_contains ".gitignore" "frontend/src-tauri/target/" "Tauri target directory is ignored"
check_contains ".gitignore" ".idea/" "JetBrains IDE metadata is ignored"
check_contains ".gitignore" ".DS_Store" "macOS Finder metadata is ignored"
check_contains "frontend/package.json" '"tauri:build": "tauri build"' "npm run tauri:build is available"
check_contains "frontend/src-tauri/tauri.conf.json" '"active": true' "Tauri bundling is enabled for packaged app smoke"
check_contains "frontend/src-tauri/tauri.conf.json" '"targets": [' "Tauri bundle targets are explicit"
check_contains "frontend/src-tauri/tauri.conf.json" '"app"' "macOS app bundle target is enabled"
check_contains "frontend/src-tauri/tauri.conf.json" '"resources": [' "Tauri bundle resources are configured"
check_contains "frontend/src-tauri/tauri.conf.json" '../../build/desktop/frozen-backend-runtime' "frozen backend runtime is declared as a packaged resource"
check_contains "frontend/src-tauri/tauri.conf.json" '"icon": [' "Tauri package icons are configured"
check_contains "frontend/src-tauri/src/lib.rs" "../Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" "Tauri packaged app can find frozen runtime manifest in app Resources"
check_contains "frontend/src-tauri/src/lib.rs" "GET /health HTTP/1.1" "Tauri packaged startup waits for HTTP /health readiness"
check_contains "frontend/src-tauri/src/lib.rs" "kill" "Tauri can stop only its stored child PID"
check_not_contains "frontend/package-lock.json" "packages.applied-caas-gateway" "npm lockfile does not use internal OpenAI package registry"
check_not_contains "frontend/package-lock.json" "internal.api.openai" "npm lockfile does not use internal OpenAI hosts"
check_not_contains "frontend/package-lock.json" "artifactory" "npm lockfile does not use internal Artifactory URLs"

if [[ -f "build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" ]]; then
  echo "✅ Frozen backend manifest exists locally for packaged app smoke"
else
  echo "⚠️ Frozen backend manifest is local-only; build it before npm run tauri:build."
  echo "   Run: scripts/build_pyinstaller_backend_runtime.sh && scripts/check_pyinstaller_backend_runtime.sh && scripts/smoke_frozen_backend_runtime.sh"
  REVIEWS=$((REVIEWS + 1))
fi

if command -v cargo >/dev/null 2>&1; then
  echo "✅ cargo is available: $(cargo --version)"
else
  echo "⚠️ cargo is not available here; install Rust locally before packaged app smoke."
  REVIEWS=$((REVIEWS + 1))
fi

if [[ "$BLOCKERS" -gt 0 ]]; then
  echo "❌ Tauri packaged app build preflight failed with $BLOCKERS blocker(s) and $REVIEWS review item(s)."
  exit 1
fi

echo "✅ Tauri packaged app build preflight passed with 0 blockers and $REVIEWS review item(s)."
