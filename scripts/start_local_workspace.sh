#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "AI Private Workspace local startup"
echo "Root: $ROOT_DIR"
echo

echo "1) Backend command:"
echo "cd '$BACKEND_DIR' && source .venv/bin/activate && export VECTOR_STORE=qdrant EMBEDDING_PROVIDER=ollama OLLAMA_EMBEDDING_MODEL=nomic-embed-text LLM_PROVIDER=ollama OLLAMA_LLM_MODEL=llama3.2 && python -m uvicorn app.main:app --reload"
echo

echo "2) Frontend command:"
echo "cd '$FRONTEND_DIR' && npm run dev"
echo

echo "This script is intentionally copy-guidance only. Run each command in its own terminal so logs stay visible."
