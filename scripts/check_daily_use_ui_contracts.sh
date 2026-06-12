#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

blockers=0
pass() { echo "✅ $1"; }
fail() { echo "❌ $1"; blockers=$((blockers + 1)); }

APP="frontend/src/App.tsx"
CREATE="frontend/src/components/CreateWorkspacePanel.tsx"
SETTINGS="frontend/src/components/SettingsPanel.tsx"
MODELS="frontend/src/components/ModelsDetail.tsx"
TAURI="frontend/src-tauri/src/lib.rs"
SCRIPT="scripts/run_desktop_mvp_smoke.sh"

if grep -q 'label: "Reports"\|label: "Capabilities"\|label: "Activity"' "$APP"; then
  fail "Main workspace tabs still expose report/capability/activity noise"
else
  pass "Main workspace tabs are simplified"
fi

if grep -q 'sidebar-footer-simple' "$APP" && ! grep -q '<code>{preferences.apiBaseUrl}</code>' "$APP"; then
  pass "Sidebar no longer exposes backend URL by default"
else
  fail "Sidebar still exposes developer backend details"
fi

if grep -q 'chooseProjectDirectory' "$CREATE" && grep -q 'Choose folder' "$CREATE"; then
  pass "Create workspace has a visible folder picker action"
else
  fail "Create workspace needs a visible folder picker action"
fi

if grep -q 'choose_project_directory' "$TAURI" && grep -q 'choose folder with prompt' "$TAURI"; then
  pass "Tauri exposes a narrow native folder picker command"
else
  fail "Native folder picker command is missing"
fi

if grep -q 'ReleaseCandidateAudit\|GitHub\|v0.1 demo\|release gate' "$SETTINGS"; then
  fail "Settings still contains release/GitHub/developer runbook content"
else
  pass "Settings is focused on user controls, not release/dev runbooks"
fi

if grep -q '<DesktopPackagingRealityPanel\|<AgentMCPReadinessOverview\|<MCPServerRegistryPanel' "$MODELS"; then
  fail "Models screen still renders heavy product/agent/MCP panels"
else
  pass "Models screen main flow is simplified"
fi

if [[ -x "$SCRIPT" ]] && grep -q 'npm run tauri:build' "$SCRIPT"; then
  pass "One-command desktop smoke script exists"
else
  fail "One-command desktop smoke script is missing or incomplete"
fi

if grep -R "frontend executes shell\|generic shell" -n frontend/src >/dev/null 2>&1; then
  fail "Frontend contains generic shell execution wording"
else
  pass "Frontend does not expose generic shell execution"
fi

if [[ "$blockers" -ne 0 ]]; then
  echo "Daily-use UI contract failed with $blockers blocker(s)."
  exit 1
fi

echo "Daily-use UI contract passed."
