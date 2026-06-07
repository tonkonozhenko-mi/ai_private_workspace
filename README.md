# Private Project AI Workbench

Private Project AI Workbench is a local-first FastAPI backend MVP for inspecting
and working with private project folders. It uses Ports and Adapters so
filesystem scanning, SQLite persistence, vector storage, embeddings, LLMs, and
command execution remain replaceable.

There is no frontend yet. The backend currently provides deterministic project
scanning and DevOps analysis, workspace read models, onboarding guidance,
indexing and RAG foundations, persistent activity history, and a guarded command
approval workflow.

## Documentation

- [API inventory](docs/API_INVENTORY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Configuration](docs/CONFIGURATION.md)
- Interactive API documentation after startup: `http://127.0.0.1:8000/docs`

## Runtime Modes

The default mode is dependency-light and safe for development:

- SQLite workspace persistence
- in-memory vector store
- fake deterministic embeddings
- fake deterministic LLM answers
- fake command execution

Optional real local mode supports Qdrant for persistent vectors and Ollama for
embeddings and LLM generation. The local command runner is separately opt-in and
still requires explicit proposal approval plus a policy-allowed command.

No cloud APIs, LangChain, or LlamaIndex are used.

## Local Model Catalog

List the current deterministic local model metadata:

```bash
curl "http://127.0.0.1:8000/models/catalog?model_type=llm&provider=ollama"
```

Request a deterministic recommendation:

```bash
curl -X POST http://127.0.0.1:8000/models/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_profile_id": "devops",
    "laptop_profile_id": "balanced",
    "task_type": "workspace_ask",
    "model_type": "llm"
  }'
```

The catalog is static local metadata only. It does not call Hugging Face or
Ollama, download models, run benchmarks, or change active settings. Future
versions can import user-defined model files, Hugging Face metadata, installed
Ollama models, and benchmark or evaluation results.

## Requirements

- Python 3.11+
- Docker or Podman only when using optional local runtimes

## Local Setup

From the repository root:

```bash
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

Use any Python 3.11+ executable if `python3.11` is not available.

## Run Tests

```bash
source backend/.venv/bin/activate
pytest backend/tests
```

Live Qdrant and Ollama integration tests are opt-in; the normal suite does not
require either runtime.

## Start The API

From inside `backend`:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

## Optional Qdrant

Start the optional Qdrant service:

```bash
docker compose --profile qdrant up -d qdrant
```

Run the backend with persistent local RAG providers:

```bash
cd backend
VECTOR_STORE=qdrant \
EMBEDDING_PROVIDER=ollama \
LLM_PROVIDER=ollama \
QDRANT_URL=http://localhost:6333 \
OLLAMA_BASE_URL=http://localhost:11434 \
uvicorn app.main:app --reload
```

Pull the default Ollama models separately before using that mode:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
```

## Local Data

SQLite workspace state is stored at `.ai-workbench/workspaces.db` relative to
the API process working directory by default. When started from `backend`, that
is `backend/.ai-workbench/workspaces.db`.

Override the location with `APP_DATA_DIR` or `WORKSPACE_DB_PATH`. To reset local
application state, stop the API and remove the relevant `.ai-workbench`
directory. Vector chunks stored in the default in-memory vector store disappear
on restart; Qdrant is recommended when RAG context must persist.

## Safety Notes

- Scanning and deterministic analyzers read local project files but execute no
  project tooling.
- Setup and command suggestions are instructions only.
- Command proposals require explicit approval.
- Approval alone is insufficient: destructive and compound-shell commands are
  blocked, while write and unknown-risk commands are manual-only.
- Real local execution is disabled unless `COMMAND_RUNNER=local`.
- The local runner uses `shell=False` and restricts `cwd` to the workspace
  project path.

## Current Limitations

- No frontend is included.
- Project scanning and analyzers are deterministic and intentionally shallow.
- Fake embeddings, fake LLM answers, and in-memory vectors remain the defaults.
- RAG quality warnings are deterministic guardrails, not proof of correctness.
- Workspace project paths are not validated during basic workspace creation.
