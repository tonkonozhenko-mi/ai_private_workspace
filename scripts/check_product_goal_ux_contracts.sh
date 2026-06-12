#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS="$ROOT_DIR/frontend/src/components/ModelsDetail.tsx"
SETTINGS="$ROOT_DIR/frontend/src/components/SettingsPanel.tsx"
CSS="$ROOT_DIR/frontend/src/styles.css"

failures=0
pass() { printf '✅ %s\n' "$1"; }
fail() { printf '❌ %s\n' "$1"; failures=$((failures+1)); }
contains() {
  local file="$1" pattern="$2" message="$3"
  if grep -qF "$pattern" "$file"; then pass "$message"; else fail "$message"; fi
}
not_contains() {
  local file="$1" pattern="$2" message="$3"
  if grep -qF "$pattern" "$file"; then fail "$message"; else pass "$message"; fi
}

contains "$MODELS" "ProductFitPanel" "Models screen keeps original product goal visible"
contains "$MODELS" "ModelSkillPresetPanel" "Model-specific skill presets are available"
contains "$MODELS" "MODEL_SKILL_PRESET_STORAGE_KEY" "Skill presets persist per model on this Mac"
contains "$MODELS" "Use for this workspace" "Model catalog has direct choose action"
contains "$MODELS" "Use for search" "Search model catalog has direct choose action"
contains "$MODELS" "MCP means external tools" "MCP explanation is human-readable"
contains "$MODELS" "Ask before each use" "MCP permission defaults are approval-based"
contains "$MODELS" "Frontend still does not execute shell commands" "Tool permissions keep frontend shell-safe"
contains "$CSS" "Task 272" "Task 272 CSS hardening exists"
contains "$CSS" ':root[data-theme="dark"] .panel' "Dark theme explicitly covers panels"
contains "$CSS" "overflow: hidden" "Overflow-safe layout rules exist"
contains "$CSS" "grid-template-columns: repeat(auto-fit" "Responsive grids are used"
contains "$SETTINGS" "selectedSkillPresets.map" "Settings shows only selected guidance template"
not_contains "$MODELS" "child_process" "Frontend does not import Node child_process"
not_contains "$MODELS" "exec(" "Models UI does not execute shell commands"
not_contains "$MODELS" "pkill" "No unsafe process killing in Models UI"

if [[ "$failures" -gt 0 ]]; then
  printf '\nProduct goal UX contract failed with %s blocker(s).\n' "$failures"
  exit 1
fi
printf '\nProduct goal UX contract passed.\n'
