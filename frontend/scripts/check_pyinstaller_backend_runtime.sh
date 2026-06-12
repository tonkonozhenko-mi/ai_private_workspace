#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRYPOINT="$ROOT_DIR/backend/packaging/pyinstaller_backend_entrypoint.py"
SPEC_FILE="$ROOT_DIR/backend/packaging/ai_private_workspace_backend.spec"
BUILD_SCRIPT="$ROOT_DIR/scripts/build_pyinstaller_backend_runtime.sh"
OUTPUT_DIR="${AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_DIR:-$ROOT_DIR/build/desktop/frozen-backend-runtime}"
MANIFEST="$OUTPUT_DIR/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
failures=0
reviews=0
ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace PyInstaller backend runtime check\n'
printf 'Project root: %s\n\n' "$ROOT_DIR"

[ -f "$ENTRYPOINT" ] && ok "PyInstaller entrypoint exists" || fail "PyInstaller entrypoint missing"
[ -f "$SPEC_FILE" ] && ok "PyInstaller spec exists" || fail "PyInstaller spec missing"
[ -x "$BUILD_SCRIPT" ] && ok "PyInstaller build script is executable" || fail "PyInstaller build script missing or not executable"

if [ -f "$ENTRYPOINT" ]; then
  grep -q 'from app.main import app' "$ENTRYPOINT" && grep -q 'uvicorn.run(app' "$ENTRYPOINT" && ok "entrypoint imports app.main:app and passes the app object to uvicorn" || fail "entrypoint does not import app.main:app and pass app object to uvicorn"
  grep -q 'AI_PRIVATE_WORKSPACE_HOST' "$ENTRYPOINT" && ok "entrypoint uses explicit host env" || fail "entrypoint missing host env"
fi
if [ -f "$BUILD_SCRIPT" ]; then
  for token in 'PyInstaller is not installed' 'build does not start backend' 'frontend still cannot execute shell commands' 'build/desktop/frozen-backend-runtime'; do
    grep -q "$token" "$BUILD_SCRIPT" && ok "build script contains: $token" || fail "build script missing required token: $token"
  done
fi
if [ -f "$MANIFEST" ]; then
  grep -q 'pyinstaller_poc_built' "$MANIFEST" && ok "frozen runtime manifest was generated" || fail "frozen runtime manifest has unexpected status"
else
  review "frozen runtime manifest not present yet; run scripts/build_pyinstaller_backend_runtime.sh in a packaging venv"
fi
UNEXPECTED_BINARY=""
while IFS= read -r candidate; do
  case "$candidate" in
    "$ROOT_DIR/build/"*) ;;
    "$ROOT_DIR/frontend/src-tauri/target/"*) ;;
    *) UNEXPECTED_BINARY="$candidate"; break ;;
  esac
done < <(find "$ROOT_DIR" \
  \( -path "$ROOT_DIR/.git" -o -path "$ROOT_DIR/backend/.venv" -o -path "$ROOT_DIR/frontend/node_modules" \) -prune -o \
  \( -name 'ai-private-workspace-backend' -o -name 'ai-private-workspace-backend.exe' \) -print 2>/dev/null)

if [ -n "$UNEXPECTED_BINARY" ]; then
  fail "frozen backend executable appears outside allowed generated locations: $UNEXPECTED_BINARY"
else
  ok "no generated backend binary outside allowed generated locations"
fi
printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
[ "$failures" -eq 0 ]
