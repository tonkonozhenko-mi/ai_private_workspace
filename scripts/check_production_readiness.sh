#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
DB_PATH="$BACKEND_DIR/.ai-workbench/workspaces.db"

echo "AI Private Workspace production readiness"
echo "Root: $ROOT_DIR"

echo ""
echo "[1/6] Root structure"
test -d "$BACKEND_DIR" && echo "ok backend/" || echo "missing backend/"
test -d "$FRONTEND_DIR" && echo "ok frontend/" || echo "missing frontend/"
test -d "$ROOT_DIR/docs" && echo "ok docs/" || echo "missing docs/"
test -d "$ROOT_DIR/scripts" && echo "ok scripts/" || echo "missing scripts/"

echo ""
echo "[2/6] Local DB"
if [[ -f "$DB_PATH" ]]; then
  ls -lh "$DB_PATH"
else
  echo "missing $DB_PATH"
fi

echo ""
echo "[3/6] Python"
if command -v python3 >/dev/null 2>&1; then
  python3 --version
else
  echo "python3 not found"
fi

echo ""
echo "[4/6] Frontend dependencies"
if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "node_modules present"
else
  echo "node_modules missing; run cd frontend && npm ci"
fi

echo ""
echo "[5/6] Runtime endpoints"
echo "If backend is running, try: curl http://127.0.0.1:8000/runtime/production-readiness"

echo ""
echo "[6/6] Safe update reminder"
echo "Use scripts/apply_generated_update.sh --dry-run SOURCE TARGET before applying generated archives."
