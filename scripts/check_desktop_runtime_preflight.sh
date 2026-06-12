#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT_DIR/build/desktop/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"
PACKAGE_SCRIPT="$ROOT_DIR/scripts/package_macos_app_foundation.sh"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
FRONTEND_DIST="$ROOT_DIR/frontend/dist/index.html"
BACKEND_ENTRYPOINT="$ROOT_DIR/backend/app/main.py"
PYINSTALLER_CHECK="$ROOT_DIR/scripts/check_pyinstaller_backend_runtime.sh"

failures=0
reviews=0

ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace desktop runtime preflight\n'
printf 'Project root: %s\n\n' "$ROOT_DIR"

[ -f "$BACKEND_ENTRYPOINT" ] && ok "backend/app/main.py found" || fail "backend/app/main.py missing"
[ -f "$PACKAGE_SCRIPT" ] && ok "package_macos_app_foundation.sh found" || fail "package_macos_app_foundation.sh missing"
[ -f "$TAURI_MAIN" ] && ok "Tauri scaffold found" || review "Tauri scaffold missing; run scripts/prepare_tauri_shell_scaffold.sh"
[ -f "$FRONTEND_DIST" ] && ok "frontend/dist/index.html found" || review "frontend/dist missing; run: cd frontend && npm ci && npm run build"
[ -x "$PYINSTALLER_CHECK" ] && ok "PyInstaller runtime check found" || review "PyInstaller runtime check missing; Task 244 frozen-runtime PoC not available"

if [ -f "$MANIFEST" ]; then
  ok "backend runtime manifest found"
  grep -q 'requirements_sha256' "$MANIFEST" && ok "manifest contains requirements hash" || fail "manifest missing requirements hash"
  grep -q 'staging does not scan, index, rebuild' "$MANIFEST" && ok "manifest documents no automatic risky actions" || fail "manifest missing safety statement"
  grep -q 'runtime data and logs stay outside' "$MANIFEST" && ok "manifest documents runtime data excludes" || fail "manifest missing runtime data excludes"
else
  review "staged backend runtime manifest missing; run: scripts/stage_backend_runtime.sh"
fi

if grep -q 'stage_backend_runtime.sh' "$PACKAGE_SCRIPT" 2>/dev/null && grep -q 'AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json' "$PACKAGE_SCRIPT" 2>/dev/null; then
  ok "package script uses staged runtime manifest preflight"
else
  fail "package script is not wired to staged runtime manifest preflight"
fi

if grep -q 'frontend never executes shell commands' "$ROOT_DIR/docs/ROADMAP.md" 2>/dev/null || grep -q 'Frontend React code must never execute shell commands' "$ROOT_DIR/docs/ROADMAP.md" 2>/dev/null; then
  ok "roadmap keeps frontend shell-execution safety rule visible"
else
  review "roadmap should document frontend no-shell safety rule"
fi

printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
if [ "$failures" -gt 0 ]; then
  exit 1
fi
exit 0
