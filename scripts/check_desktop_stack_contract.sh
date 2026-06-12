#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROUTE_FILE="$ROOT_DIR/backend/app/api/routes/local_data_safety.py"
SCHEMA_FILE="$ROOT_DIR/backend/app/api/schemas/local_data_safety_schemas.py"
TAURI_MAIN="$ROOT_DIR/frontend/src-tauri/src/main.rs"
DOC_FILE="$ROOT_DIR/docs/TASK242_DESKTOP_STACK_AND_RUNTIME_CONTRACT.md"

failures=0
reviews=0

ok() { printf '✅ %s\n' "$1"; }
review() { printf '⚠️  %s\n' "$1"; reviews=$((reviews + 1)); }
fail() { printf '❌ %s\n' "$1"; failures=$((failures + 1)); }

printf 'AI Private Workspace desktop stack contract check\n'
printf 'Project root: %s\n\n' "$ROOT_DIR"

[ -f "$ROUTE_FILE" ] && ok "runtime route file found" || fail "runtime route file missing"
[ -f "$SCHEMA_FILE" ] && ok "runtime schema file found" || fail "runtime schema file missing"
[ -f "$TAURI_MAIN" ] && ok "Tauri scaffold found" || review "Tauri scaffold missing"
[ -f "$DOC_FILE" ] && ok "Task 242 contract document found" || fail "Task 242 contract document missing"

if grep -q '/desktop-stack-runtime-contract' "$ROUTE_FILE" 2>/dev/null; then
  ok "desktop stack runtime contract endpoint is registered"
else
  fail "desktop stack runtime contract endpoint is missing"
fi

for token in 'open-source/free' 'Tauri + React' 'PyInstaller' 'macOS and Windows' 'Frontend still cannot execute shell commands'; do
  if grep -q "$token" "$ROUTE_FILE" "$DOC_FILE" 2>/dev/null; then
    ok "contract documents: $token"
  else
    fail "contract missing required decision text: $token"
  fi
done

if grep -q 'backend_start_enabled: false' "$TAURI_MAIN" 2>/dev/null; then
  ok "Tauri backend startup remains disabled while runtime freeze is pending"
else
  fail "Tauri backend startup is not explicitly disabled"
fi

if grep -q 'scan, index, rebuild, MCP, Agent, or model downloads' "$ROUTE_FILE" "$DOC_FILE" 2>/dev/null; then
  ok "contract preserves no-auto-actions launch rule"
else
  fail "contract missing no-auto-actions launch rule"
fi

printf '\nSummary: %s blocker(s), %s review item(s)\n' "$failures" "$reviews"
if [ "$failures" -gt 0 ]; then
  exit 1
fi
exit 0
