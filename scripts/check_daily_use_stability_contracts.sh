#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

blockers=0
pass() { echo "✅ $1"; }
fail() { echo "❌ $1"; blockers=$((blockers + 1)); }

if grep -q "friendlyAskError" frontend/src/components/AskWorkspace.tsx; then
  pass "Ask shows friendly model/runtime errors"
else
  fail "Ask does not map raw model/runtime failures to friendly guidance"
fi

if grep -q "selected_llm_runtime_unavailable" backend/app/core/use_cases/ask_workspace_question.py; then
  pass "Backend returns diagnostic answer for selected model runtime failures"
else
  fail "Backend can still surface selected model runtime failures as generic 500"
fi

if grep -q "safe proposed change" backend/app/core/domain/rag_prompt.py; then
  pass "File create/edit requests are handled as proposed changes with approval wording"
else
  fail "Prompt does not guide file create/edit requests into safe proposed changes"
fi

if grep -q "Task 273" frontend/src/styles.css && grep -q "color-scheme: dark" frontend/src/styles.css; then
  pass "Task 273 visual/dark hardening rules are present"
else
  fail "Dark theme hardening rules are missing"
fi

if [ -x scripts/build_and_open_ai_private_workspace.sh ] && [ -x scripts/open_ai_private_workspace.sh ]; then
  pass "One-command build/open scripts are available"
else
  fail "One-command app scripts are missing or not executable"
fi

if [ -x "Open AI Private Workspace.command" ]; then
  pass "Double-click macOS launcher is available"
else
  fail "Double-click macOS launcher is missing"
fi

if grep -R "pkill\|killall\|taskkill\|lsof.*kill" -n frontend/src scripts/open_ai_private_workspace.sh scripts/build_and_open_ai_private_workspace.sh "Open AI Private Workspace.command" >/tmp/aw273_kill_hits.txt 2>/dev/null; then
  cat /tmp/aw273_kill_hits.txt
  fail "New launch scripts must not kill processes by name or port"
else
  pass "New launch scripts do not kill processes by name or port"
fi

if [ "$blockers" -ne 0 ]; then
  echo "Daily-use stability contracts failed with $blockers blocker(s)."
  exit 1
fi

echo "Daily-use stability contracts passed."
