# Desktop-like local startup

AI Private Workspace stays local-first. The app does not start shell commands from the browser.

Recommended daily startup:

1. Start the backend in one terminal:

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

2. Start the frontend in another terminal:

```bash
cd ~/Documents/ai_workspace/frontend
npm run dev
```

3. Open the browser UI.

The frontend stores the last selected workspace id in browser localStorage and restores it when that workspace still exists in the local SQLite database.

Runtime data remains in `backend/.ai-workbench/`. Do not include it in generated update archives and do not delete it during `rsync --delete` updates.

For copyable startup commands, use:

```bash
scripts/start_local_workspace.sh
```

This script prints commands only; it does not start backend/frontend processes automatically.
