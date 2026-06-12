#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ_FILE="$ROOT_DIR/backend/requirements.txt"
SPEC_FILE="$ROOT_DIR/backend/packaging/ai_private_workspace_backend.spec"
BUILD_SCRIPT="$ROOT_DIR/scripts/build_pyinstaller_backend_runtime.sh"
TAURI_PACKAGE="$ROOT_DIR/frontend/package.json"

blockers=0
reviews=0

ok() { printf '✅ %s\n' "$1"; }
fail() { printf '❌ %s\n' "$1"; blockers=$((blockers + 1)); }
review() { printf '⚠️ %s\n' "$1"; reviews=$((reviews + 1)); }

check_file() {
  [ -f "$ROOT_DIR/$1" ] && ok "$2 exists" || fail "$2 missing: $1"
}
check_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  grep -q "$pattern" "$file" && ok "$label" || fail "$label missing"
}

check_file "backend/requirements.txt" "backend requirements"
check_file "backend/packaging/ai_private_workspace_backend.spec" "PyInstaller spec"
check_file "backend/packaging/pyinstaller_backend_entrypoint.py" "PyInstaller entrypoint"
check_file "scripts/build_pyinstaller_backend_runtime.sh" "PyInstaller build script"
check_file "frontend/package.json" "frontend package.json"

if [ -f "$REQ_FILE" ]; then
  check_contains "$REQ_FILE" '^pyinstaller' "PyInstaller dependency is declared"
fi

if [ -f "$SPEC_FILE" ]; then
  check_contains "$SPEC_FILE" 'SPECPATH' "PyInstaller spec resolves paths from spec location"
  check_contains "$SPEC_FILE" 'ENTRYPOINT = BACKEND_DIR / "packaging" / "pyinstaller_backend_entrypoint.py"' "PyInstaller spec avoids duplicated backend/packaging path"
fi

if [ -f "$BUILD_SCRIPT" ]; then
  check_contains "$BUILD_SCRIPT" 'python3 -m PyInstaller' "build script invokes PyInstaller via active Python"
fi

if [ -f "$TAURI_PACKAGE" ]; then
  check_contains "$TAURI_PACKAGE" '"tauri"' "npm tauri script is available"
  check_contains "$TAURI_PACKAGE" '@tauri-apps/cli' "Tauri CLI dev dependency is declared"
fi

if command -v cargo >/dev/null 2>&1; then
  ok "cargo is installed: $(cargo --version)"
else
  review "cargo is not installed. On macOS install Rust/Cargo with: brew install rust OR rustup from https://rustup.rs"
fi

if command -v python3 >/dev/null 2>&1 && python3 -m PyInstaller --version >/dev/null 2>&1; then
  ok "PyInstaller is importable in the active Python environment"
else
  review "PyInstaller is not importable in the active Python. Run: cd backend && python3 -m pip install -r requirements.txt"
fi

printf '\nPackaging toolchain prerequisite check complete: %s blockers, %s review items.\n' "$blockers" "$reviews"
[ "$blockers" -eq 0 ]
