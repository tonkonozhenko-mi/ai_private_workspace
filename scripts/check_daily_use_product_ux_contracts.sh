#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_SRC="$ROOT_DIR/frontend/src"
BLOCKERS=0

pass() { printf '✅ %s\n' "$1"; }
fail() { printf '❌ %s\n' "$1"; BLOCKERS=$((BLOCKERS + 1)); }

contains() {
  local file="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$file"
}

MODELS="$FRONTEND_SRC/components/ModelsDetail.tsx"
SETTINGS="$FRONTEND_SRC/components/SettingsPanel.tsx"
ASK="$FRONTEND_SRC/components/AskWorkspace.tsx"
CSS="$FRONTEND_SRC/styles.css"

contains "$MODELS" "function ModelCatalogPanel" \
  && pass "Models includes a local model catalog" \
  || fail "Models must include a local model catalog"

contains "$MODELS" "Qwen2.5 Coder 7B" \
  && contains "$MODELS" "Mistral 7B" \
  && contains "$MODELS" "Gemma 2 9B" \
  && contains "$MODELS" "Llama 3.2 3B" \
  && pass "Model catalog explains common local LLM choices" \
  || fail "Model catalog must explain Qwen, Mistral, Gemma, and Llama options"

contains "$MODELS" "What should I use on my Mac?" \
  && pass "Model catalog includes Mac resource guidance" \
  || fail "Model catalog must include Mac resource guidance"

contains "$MODELS" "Agent and MCP access stay approval-based" \
  && contains "$MODELS" "MCP is still part of the product" \
  && pass "MCP/agent permissions are preserved without noisy dashboard UI" \
  || fail "MCP/agent permissions must remain visible and approval-based"

contains "$SETTINGS" "selectedSkillPresets.map" \
  && pass "Ask guidance shows only selected template guidance" \
  || fail "Settings must not render every guidance preset at once"

if grep -Fq "Open Models" "$SETTINGS"; then
  fail "Settings should not contain a redundant Open Models shortcut"
else
  pass "Settings no longer duplicates Models navigation"
fi

contains "$ASK" "ask-guidance-disclosure" \
  && contains "$ASK" "Local answers with attached sources." \
  && pass "Ask surface is lighter and guidance is collapsed" \
  || fail "Ask surface must be lighter with collapsed guidance"

contains "$CSS" "Task 271 — product-grade daily-use cleanup" \
  && contains "$CSS" "overflow-wrap: anywhere" \
  && contains "$CSS" "grid-template-columns: repeat(auto-fit" \
  && pass "CSS includes overflow-safe responsive layout rules" \
  || fail "CSS must include overflow-safe responsive layout rules"

contains "$CSS" ':root[data-theme="dark"] .ask-bottom-composer' \
  && pass "Dark theme has explicit overrides for polished surfaces" \
  || fail "Dark theme must have explicit overrides"

if grep -R "shellCommand\|Command.create\|ollama pull" "$FRONTEND_SRC" --exclude-dir=node_modules | grep -v "CopyButton" | grep -v "install_command" >/tmp/aw271-shell-check.txt; then
  fail "Frontend appears to execute shell/model commands"
  cat /tmp/aw271-shell-check.txt
else
  pass "Frontend remains free of shell/model execution"
fi

if [[ "$BLOCKERS" -ne 0 ]]; then
  printf '\nDaily-use product UX contract failed with %s blocker(s).\n' "$BLOCKERS" >&2
  exit 1
fi

printf '\nDaily-use product UX contract passed.\n'
