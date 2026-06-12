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

check_file "frontend/src-tauri/Cargo.toml" "Tauri Cargo manifest"
check_file "frontend/src-tauri/Cargo.lock" "Tauri Cargo lockfile"
check_file "frontend/src-tauri/src/main.rs" "Tauri binary entrypoint"
check_file "frontend/src-tauri/src/lib.rs" "Tauri app library"
check_file "frontend/src-tauri/tauri.conf.json" "Tauri config"
check_file "frontend/src-tauri/icons/icon.png" "Tauri main icon"
check_file "frontend/package.json" "frontend package manifest"
check_file "frontend/package-lock.json" "frontend npm lockfile"
check_file "scripts/check_tauri_icon_assets.sh" "Tauri icon check script"
check_file "scripts/check_tauri_backend_health_readiness.sh" "Tauri health readiness check script"
check_file "scripts/check_tauri_rust_structure_and_registry.sh" "Tauri Rust structure check script"

check_contains ".gitignore" "frontend/src-tauri/target/" "Tauri Rust target directory is ignored"
check_contains "frontend/src-tauri/src/main.rs" "ai_private_workspace_lib::run();" "main.rs delegates to library run()"
check_contains "frontend/src-tauri/src/lib.rs" "start_app_owned_backend_runtime" "Tauri app-owned backend startup command is present"
check_contains "frontend/src-tauri/src/lib.rs" "stop_app_owned_backend_runtime" "Tauri PID-owned backend shutdown command is present"
check_contains "frontend/src-tauri/src/lib.rs" "GET /health HTTP/1.1" "Tauri waits for application-level /health readiness"
check_contains "frontend/src-tauri/src/lib.rs" "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" "Tauri startup is gated by frozen runtime manifest"
check_contains "frontend/src-tauri/Cargo.toml" 'time = "=0.3.36"' "Rust time crate is pinned for current local toolchain compatibility"
check_contains "frontend/package.json" '"tauri": "tauri"' "npm run tauri dev is available"
check_contains "frontend/package.json" '"tauri:build": "tauri build"' "npm run tauri:build is available"
check_not_contains "frontend/package-lock.json" "packages.applied-caas-gateway" "npm lockfile does not use internal OpenAI package registry"
check_not_contains "frontend/package-lock.json" "internal.api.openai" "npm lockfile does not use internal OpenAI hosts"
check_not_contains "frontend/package-lock.json" "artifactory" "npm lockfile does not use internal Artifactory URLs"

if command -v cargo >/dev/null 2>&1; then
  echo "✅ cargo is available: $(cargo --version)"
else
  echo "⚠️ cargo is not available here; install with brew install rust or rustup on macOS."
  REVIEWS=$((REVIEWS + 1))
fi

if [[ -f "build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" ]]; then
  echo "✅ Frozen backend manifest exists locally"
else
  echo "⚠️ Frozen backend manifest is not included in source archives; create it locally with scripts/build_pyinstaller_backend_runtime.sh"
  REVIEWS=$((REVIEWS + 1))
fi

if [[ "$BLOCKERS" -gt 0 ]]; then
  echo "❌ Tauri dev smoke readiness failed with $BLOCKERS blocker(s) and $REVIEWS review item(s)."
  exit 1
fi

echo "✅ Tauri dev smoke readiness passed with 0 blockers and $REVIEWS review item(s)."
