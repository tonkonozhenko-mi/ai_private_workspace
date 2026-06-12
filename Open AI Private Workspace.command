#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./scripts/open_ai_private_workspace.sh || ./scripts/build_and_open_ai_private_workspace.sh
