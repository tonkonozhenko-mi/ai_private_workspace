# Runtime troubleshooting

AI Private Workspace keeps runtime troubleshooting explicit and local-first.
The frontend can display and copy commands, but it must not execute shell commands,
start services, restart the backend, pull models, or change runtime configuration.

## Main diagnostics

```bash
curl http://127.0.0.1:8000/runtime/troubleshooting
```

The endpoint combines runtime health with safe next steps for:

- Ollama reachability
- missing Ollama models
- Qdrant reachability
- fake provider mode
- memory vector store mode
- backend and frontend restart commands

## Quick script

```bash
scripts/troubleshoot_runtime.sh
```

The script only calls read-only backend endpoints. It does not modify local data.

## Common checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/runtime/health
curl http://127.0.0.1:8000/runtime/local-data
curl http://localhost:11434/api/tags
curl http://localhost:6333/collections
```

## Safe backend start

```bash
cd ~/Documents/ai_workspace/backend
source .venv/bin/activate
export VECTOR_STORE=qdrant
export EMBEDDING_PROVIDER=ollama
export OLLAMA_EMBEDDING_MODEL=nomic-embed-text
export LLM_PROVIDER=ollama
export OLLAMA_LLM_MODEL=llama3.2
python -m uvicorn app.main:app --reload
```

Always use `python -m uvicorn` from the active backend virtualenv. This avoids accidentally using a global Homebrew uvicorn with a different Python version.
