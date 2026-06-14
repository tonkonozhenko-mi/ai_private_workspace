#!/usr/bin/env bash
# One command for local development: starts the FastAPI backend (which reads
# backend/.env) and the Vite frontend together, and stops the backend when you
# quit the frontend (Ctrl+C). Used by `npm run dev` in the frontend.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BACKEND_PID=""
cleanup() {
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "▶ Starting backend (uvicorn, reads backend/.env) ..."
(
  cd "$ROOT/backend"
  if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  exec uvicorn app.main:app --reload
) &
BACKEND_PID=$!

echo "▶ Starting frontend (vite) ..."
cd "$ROOT/frontend"
npm run dev:vite
