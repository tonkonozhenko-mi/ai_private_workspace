#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_DIR="${AI_PRIVATE_WORKSPACE_RUNTIME_STAGE_DIR:-$ROOT_DIR/build/desktop/backend-runtime}"
MANIFEST="$STAGE_DIR/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"
LAUNCHER="$STAGE_DIR/run_backend.sh"
APP_MAIN="$STAGE_DIR/app/app/main.py"
REQUIREMENTS="$STAGE_DIR/requirements.txt"

failures=0
reviews=0

ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace staged backend runtime check\n'
printf 'Project root: %s\n' "$ROOT_DIR"
printf 'Stage dir: %s\n\n' "$STAGE_DIR"

[ -d "$STAGE_DIR" ] && ok "staged runtime directory exists" || fail "staged runtime directory missing; run scripts/stage_backend_runtime.sh"
[ -f "$MANIFEST" ] && ok "runtime manifest exists" || fail "runtime manifest missing"
[ -x "$LAUNCHER" ] && ok "runtime launcher exists and is executable" || fail "runtime launcher missing or not executable"
[ -f "$APP_MAIN" ] && ok "staged backend app entrypoint exists" || fail "staged backend app/main.py missing"
[ -f "$REQUIREMENTS" ] && ok "staged requirements.txt exists" || fail "staged requirements.txt missing"

if [ -f "$MANIFEST" ]; then
  for token in 'staged_source_runtime' 'requirements_sha256' 'frontend still cannot execute shell commands' 'staging does not start backend'; do
    if grep -q "$token" "$MANIFEST"; then
      ok "manifest contains: $token"
    else
      fail "manifest missing required token: $token"
    fi
  done
fi

if find "$STAGE_DIR" \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '__pycache__' -o -name '.pytest_cache' -o -name '.venv' \) -print -quit 2>/dev/null | grep -q .; then
  fail "staged runtime contains forbidden runtime/cache/database artifacts"
else
  ok "staged runtime excludes DB/cache/venv artifacts"
fi

if [ -f "$LAUNCHER" ] && grep -q 'python3 -m uvicorn app.main:app' "$LAUNCHER"; then
  review "launcher is source-runtime based; frozen PyInstaller/Nuitka binary is still future work"
fi

printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
if [ "$failures" -gt 0 ]; then
  exit 1
fi
exit 0
