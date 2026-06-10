#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

if [[ ! -d node_modules ]]; then
  echo "frontend/node_modules is missing. Installing with npm ci..."
  npm ci
fi

echo "Starting frontend at http://127.0.0.1:5173"
npm run dev
