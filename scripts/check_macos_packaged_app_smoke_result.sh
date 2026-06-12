#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_BUNDLE="$ROOT_DIR/frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"
TAURI_BINARY="$ROOT_DIR/frontend/src-tauri/target/release/ai-private-workspace"
FROZEN_MANIFEST="$ROOT_DIR/build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
SMOKE_LOG="$ROOT_DIR/build/desktop/smoke-logs/frozen-backend-smoke.log"

BLOCKERS=0
REVIEWS=0
ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; REVIEWS=$((REVIEWS + 1)); }
fail() { printf '❌ %s\n' "$1"; BLOCKERS=$((BLOCKERS + 1)); }

printf 'AI Private Workspace macOS packaged app smoke result check\n'
printf 'Project root: %s\n\n' "$ROOT_DIR"

if [[ -d "$APP_BUNDLE" ]]; then
  ok "packaged macOS app bundle exists"
else
  review "packaged macOS app bundle not present in source tree; run cd frontend && npm run tauri:build locally"
fi

if [[ -x "$TAURI_BINARY" ]]; then
  ok "Tauri release binary exists locally"
else
  review "Tauri release binary not present yet; run cd frontend && npm run tauri:build locally"
fi

if [[ -f "$FROZEN_MANIFEST" ]]; then
  ok "frozen backend manifest exists locally"
else
  review "frozen backend manifest not present yet; run scripts/build_pyinstaller_backend_runtime.sh locally"
fi

if [[ -f "$SMOKE_LOG" ]]; then
  if grep -Fq "Application startup complete" "$SMOKE_LOG" || grep -Fq "Uvicorn running on" "$SMOKE_LOG"; then
    ok "frozen backend smoke log shows Uvicorn startup"
  else
    review "frozen backend smoke log exists, but startup marker was not found; inspect only if smoke fails"
  fi
else
  review "frozen backend smoke log not present in source tree; run scripts/smoke_frozen_backend_runtime.sh locally"
fi

for path in \
  "$ROOT_DIR/scripts/check_pyinstaller_backend_runtime.sh" \
  "$ROOT_DIR/scripts/smoke_frozen_backend_runtime.sh" \
  "$ROOT_DIR/scripts/check_tauri_packaged_app_build.sh" \
  "$ROOT_DIR/frontend/src-tauri/tauri.conf.json" \
  "$ROOT_DIR/frontend/src-tauri/src/lib.rs"; do
  [[ -e "$path" ]] && ok "required file exists: ${path#$ROOT_DIR/}" || fail "required file missing: ${path#$ROOT_DIR/}"
done

if grep -Fq "from app.main import app" "$ROOT_DIR/backend/packaging/pyinstaller_backend_entrypoint.py" \
  && grep -Fq "uvicorn.run(app" "$ROOT_DIR/backend/packaging/pyinstaller_backend_entrypoint.py"; then
  ok "PyInstaller entrypoint imports app.main:app and passes object to uvicorn"
else
  fail "PyInstaller entrypoint must import app.main:app and pass object to uvicorn"
fi

if grep -Fq "Resources/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" "$ROOT_DIR/frontend/src-tauri/src/lib.rs"; then
  ok "Tauri packaged app searches Resources for frozen runtime manifest"
else
  fail "Tauri packaged app does not search Resources for frozen runtime manifest"
fi

if grep -Fq "GET /health HTTP/1.1" "$ROOT_DIR/frontend/src-tauri/src/lib.rs"; then
  ok "Tauri startup waits for HTTP /health readiness"
else
  fail "Tauri startup must wait for HTTP /health readiness"
fi

printf '\nSummary: %s blocker(s), %s review item(s)\n' "$BLOCKERS" "$REVIEWS"
[[ "$BLOCKERS" -eq 0 ]]
