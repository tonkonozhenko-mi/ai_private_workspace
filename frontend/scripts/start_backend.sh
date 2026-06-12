#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
cd "$BACKEND_DIR"

if [[ ! -d .venv ]]; then
  echo "Backend .venv is missing. Create it with Python 3.12 first:"
  echo "  /opt/homebrew/bin/python3.12 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

source .venv/bin/activate

python - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required. Recreate backend/.venv with Python 3.12.")
print(f"Using Python {sys.version.split()[0]}")
PY

export VECTOR_STORE="${VECTOR_STORE:-qdrant}"
export EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-ollama}"
export OLLAMA_EMBEDDING_MODEL="${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}"
export LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
export OLLAMA_LLM_MODEL="${OLLAMA_LLM_MODEL:-llama3.2}"

mkdir -p .ai-workbench

echo "Starting backend at http://127.0.0.1:8000"
echo "Workspace DB: ${WORKSPACE_DB_PATH:-.ai-workbench/workspaces.db}"
python -m uvicorn app.main:app --reload
