#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SMOKE_SCRIPT="$ROOT_DIR/scripts/smoke_frozen_backend_runtime.sh"
ROUTE_FILE="$ROOT_DIR/backend/app/api/routes/local_data_safety.py"
SCHEMA_FILE="$ROOT_DIR/backend/app/api/schemas/local_data_safety_schemas.py"
BLOCKERS=0
REVIEW=0
ok() { printf 'ok: %s\n' "$1"; }
blocker() { printf 'blocker: %s\n' "$1"; BLOCKERS=$((BLOCKERS + 1)); }
contains() {
  local file="$1" token="$2" label="$3"
  if grep -Fq "$token" "$file"; then ok "$label"; else blocker "missing $label"; fi
}

[ -x "$SMOKE_SCRIPT" ] && ok "smoke script is executable" || blocker "smoke script missing or not executable"
contains "$SMOKE_SCRIPT" "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json" "manifest gate"
contains "$SMOKE_SCRIPT" "refusing to kill or replace unknown process" "port conflict refusal message"
contains "$SMOKE_SCRIPT" "kill -0" "PID-owned cleanup only"
contains "$SMOKE_SCRIPT" "urllib.request.urlopen" "health polling"
contains "$ROUTE_FILE" "/frozen-backend-smoke-contract" "backend API endpoint"
contains "$SCHEMA_FILE" "FrozenBackendSmokeContractResponse" "backend API schema"
if grep -Eq "pkill|killall|taskkill|lsof.*-t" "$SMOKE_SCRIPT"; then
  blocker "smoke script must not kill processes by name or port"
else
  ok "no broad process-kill command in smoke script"
fi
printf 'summary: %s blockers, %s review items\n' "$BLOCKERS" "$REVIEW"
[ "$BLOCKERS" -eq 0 ]
