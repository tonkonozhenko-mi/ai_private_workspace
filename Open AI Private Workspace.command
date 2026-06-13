#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
./scripts/open_ai_private_workspace.sh
status=$?
if [ "$status" -ne 0 ]; then
  printf '\nAI Private Workspace could not be opened (exit %s).\n' "$status"
  printf 'See build/desktop/open-ai-private-workspace.log for details.\n'
  read -r -p "Press Enter to close this window..."
  exit "$status"
fi
