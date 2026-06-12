#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRYPOINT="$ROOT_DIR/backend/packaging/pyinstaller_backend_entrypoint.py"
SPEC_FILE="$ROOT_DIR/backend/packaging/ai_private_workspace_backend.spec"
SMOKE_SCRIPT="$ROOT_DIR/scripts/smoke_frozen_backend_runtime.sh"
failures=0
reviews=0
ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace frozen backend startup diagnostics check\n'
printf 'Project root: %s\n\n' "$ROOT_DIR"

[ -f "$ENTRYPOINT" ] && ok "PyInstaller entrypoint exists" || fail "PyInstaller entrypoint missing"
[ -f "$SPEC_FILE" ] && ok "PyInstaller spec exists" || fail "PyInstaller spec missing"
[ -x "$SMOKE_SCRIPT" ] && ok "frozen backend smoke script is executable" || fail "frozen backend smoke script missing or not executable"

if [ -f "$ENTRYPOINT" ]; then
  grep -q 'def _import_app' "$ENTRYPOINT" && ok "entrypoint performs explicit app import preflight" || fail "entrypoint does not perform explicit app import preflight"
  grep -q -- '--runtime-self-check' "$ENTRYPOINT" && ok "entrypoint supports runtime self-check" || fail "entrypoint missing runtime self-check"
  grep -q 'traceback.print_exc' "$ENTRYPOINT" && ok "entrypoint prints startup traceback" || fail "entrypoint does not print startup traceback"
  grep -q 'APP_DATA_DIR' "$ENTRYPOINT" && ok "entrypoint sets desktop app data defaults" || fail "entrypoint missing desktop app data defaults"
  grep -q 'uvicorn.run(app' "$ENTRYPOINT" && ok "entrypoint passes imported FastAPI app to uvicorn" || fail "entrypoint should pass imported app object to uvicorn"
fi

if [ -f "$SPEC_FILE" ]; then
  for token in '"uvicorn"' '"fastapi"' '"starlette"' '"pydantic"' 'collect_submodules(package)' 'datas=datas'; do
    grep -q "$token" "$SPEC_FILE" && ok "spec contains: $token" || fail "spec missing required token: $token"
  done
fi

if [ -f "$SMOKE_SCRIPT" ]; then
  for token in '--runtime-self-check' 'print_log_tail' 'frozen backend process exited before health became ready' 'APP_DATA_DIR=' 'WORKSPACE_DB_PATH='; do
    grep -q -- "$token" "$SMOKE_SCRIPT" && ok "smoke script contains: $token" || fail "smoke script missing required token: $token"
  done
fi

if [ -f "$ROOT_DIR/build/desktop/smoke-logs/frozen-backend-smoke.log" ]; then
  review "local frozen backend smoke log exists; inspect it only if the smoke script fails"
else
  ok "no generated smoke log in source tree"
fi

printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
[ "$failures" -eq 0 ]
