# Configuration

Settings are read from environment variables when `app.config.settings.get_settings`
is first called. Relative paths are resolved from the API process working
directory. From inside `backend`, the default database is therefore
`backend/.ai-workbench/workspaces.db`.

Unsupported repository/provider/runner names fail during application
composition. Qdrant and Ollama are optional and are not contacted under the
default configuration.

## Application And Frontend Development

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origin URLs | Allows the local Vite frontend to call the FastAPI backend during development. | The frontend runs on another host or port. |

Origins are trimmed and loaded once at backend startup. Restart the API after
changing `CORS_ALLOWED_ORIGINS`. Keep the list explicit; the backend does not
use a wildcard origin.

## Persistence

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `WORKSPACE_REPOSITORY` | `sqlite` | `sqlite`, `memory` | Selects repositories for workspaces, scans, commands, index status, and timeline. | Use `memory` for disposable experiments or focused tests. |
| `APP_DATA_DIR` | `.ai-workbench` | Filesystem path | Local application data directory; created at startup. | Place all local app data elsewhere. |
| `WORKSPACE_DB_PATH` | `<APP_DATA_DIR>/workspaces.db` | SQLite file path | Persistent workspace-state database; parent directory is created at startup. | Use a dedicated or absolute database location. |

## Vector Store

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `VECTOR_STORE` | `memory` | `memory`, `qdrant` | Selects the active vector-store adapter. | Use `qdrant` when indexed context must survive API restarts. |
| `QDRANT_URL` | `http://localhost:6333` | URL | Qdrant server used by vector storage and runtime health. | Qdrant runs at another host or port. |
| `QDRANT_COLLECTION` | `ai_workspace_chunks` | Collection base name | Base for embedding-dimension-aware Qdrant collection names. | Isolate environments or choose a naming convention. |

The in-memory vector store loses chunks on API restart. Qdrant is optional and
is contacted only when selected or checked by configured runtime health.

## Embeddings

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `EMBEDDING_PROVIDER` | `fake` | `fake`, `ollama` | Selects deterministic fake embeddings or local Ollama embeddings. | Enable real local retrieval embeddings. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL | Shared Ollama base URL for embeddings, LLM generation, and health. | Ollama runs at another host or port. |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Installed Ollama model name | Embedding model and Qdrant collection identity input. | Use another local embedding model. |
| `OLLAMA_TIMEOUT_SECONDS` | `30` | Integer seconds | Timeout for Ollama embedding requests. | Larger projects or slower hardware need more time. |

## LLM Generation

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `LLM_PROVIDER` | `fake` | `fake`, `ollama` | Selects deterministic fake answers or local Ollama generation. | Enable real local workspace answers. |
| `OLLAMA_LLM_MODEL` | `llama3.2` | Installed Ollama model name | Generation model used by `/ask` and reported in runtime health. | Use a different local model. |
| `OLLAMA_LLM_TIMEOUT_SECONDS` | `120` | Integer seconds | Timeout for Ollama generation requests. | Generation needs more or less time. |

## Local Model Catalog

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `USER_MODEL_CATALOG_PATH` | empty | Path to a JSON file | Loads additional user-defined model metadata at application startup. | Add custom local, Ollama, Hugging Face, or other model metadata without changing code. |

An empty value disables user catalog loading. Missing files, malformed JSON, and
invalid individual models do not prevent the application from starting; they
appear as warnings in `GET /models/catalog/details`. Valid user models are
merged with the static catalog. User models with duplicate IDs are skipped and
cannot override built-in definitions.

The file is metadata only. Loading it does not call model providers, download
artifacts, run benchmarks, or change active runtime settings. The desktop app
uses this file to persist custom Ollama model tags and metadata discovered by
the read-only Installed Models check. Restart the API after changing the
configured path itself. After editing the file at the current configured path,
reload its metadata with:

```bash
curl -X POST http://127.0.0.1:8000/models/catalog/reload
```

Reload replaces the current in-memory user-model snapshot. If the file becomes
invalid or unavailable, previous user models are removed, built-in models remain
available, and the reload response plus catalog details expose warnings.

The packaged macOS desktop runtime stores the catalog under its application data
directory and configures the dedicated model download worker. Browser/developer
backends remain conservative unless `MODEL_DOWNLOAD_EXECUTION_ENABLED=true` and
`COMMAND_RUNNER=local` are both explicitly configured. The worker accepts only
an exact `ollama pull <catalog-model-name>` command; normal workspace command
approval and execution policy remain separate.


## Real Local AI Runtime

The verified real local AI path uses Qdrant for persistent vector search,
Ollama for embeddings, and Ollama for answer generation. It keeps command
execution safe by leaving `COMMAND_RUNNER=fake` unless local command execution
is enabled separately and intentionally.

### Required local services

- Ollama listening on `http://localhost:11434`.
- Qdrant listening on `http://localhost:6333`.

Start or create Qdrant with Podman:

```bash
podman start qdrant
```

If the container does not exist yet:

```bash
podman run -d \
  --name qdrant \
  -p 6333:6333 \
  -v qdrant_data:/qdrant/storage \
  docker.io/qdrant/qdrant:latest
```

Verify services:

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:6333/healthz
```

### Required models

The verified baseline is:

- `nomic-embed-text` for embeddings.
- `llama3.2` for generation.

`qwen2.5-coder` is a useful optional model for later comparison experiments.
Install missing models explicitly:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
ollama pull qwen2.5-coder
```

### Runtime environment

Use these settings for the verified local AI runtime:

| Variable | Verified value | Purpose |
| --- | --- | --- |
| `VECTOR_STORE` | `qdrant` | Store and search workspace vectors in Qdrant. |
| `EMBEDDING_PROVIDER` | `ollama` | Generate real local embeddings through Ollama. |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model used for indexing and search. |
| `LLM_PROVIDER` | `ollama` | Generate real local answers through Ollama. |
| `OLLAMA_LLM_MODEL` | `llama3.2` | Default local generation model. |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP endpoint. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama HTTP endpoint. |

Preferred zsh-friendly startup method:

```bash
cd backend

export VECTOR_STORE=qdrant
export EMBEDDING_PROVIDER=ollama
export OLLAMA_EMBEDDING_MODEL=nomic-embed-text
export LLM_PROVIDER=ollama
export OLLAMA_LLM_MODEL=llama3.2

python -m uvicorn app.main:app --reload
```

Single-line alternative:

```bash
VECTOR_STORE=qdrant EMBEDDING_PROVIDER=ollama OLLAMA_EMBEDDING_MODEL=nomic-embed-text LLM_PROVIDER=ollama OLLAMA_LLM_MODEL=llama3.2 python -m uvicorn app.main:app --reload
```

Avoid copied multi-line environment commands with blank lines in zsh. If the
variables are not exported correctly, Python will see `None` and the backend
will fall back to `memory` / `fake` / `fake` defaults. Check the shell first:

```bash
python -c 'import os; print(os.getenv("VECTOR_STORE"), os.getenv("EMBEDDING_PROVIDER"), os.getenv("LLM_PROVIDER"))'
```

Expected output after export:

```text
qdrant ollama ollama
```

### Verification flow

Use the real workspace ID in place of `{workspace_id}`.

Check runtime health:

```bash
curl http://127.0.0.1:8000/runtime/health
```

Successful runtime health should show:

- `VECTOR_STORE` as `qdrant`.
- `EMBEDDING_PROVIDER` as `ollama`.
- `LLM_PROVIDER` as `ollama`.
- Qdrant `configured: true` and `status: ok`.
- Ollama `configured: true` and `status: ok`.

Reindex after changing embedding provider, embedding model, or vector store:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/index
curl http://127.0.0.1:8000/workspaces/{workspace_id}/index/status
```

Select the active Ollama LLM for `ask-selected`:

```bash
curl -X PUT http://127.0.0.1:8000/workspaces/{workspace_id}/models/selection \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "model": "llama3.2",
    "model_type": "llm",
    "selected_reason": "Use active local Ollama LLM."
  }'
```

Check model readiness:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/models/selection/status
```

Expected success signals:

- `llm_status.status` is `ready`.
- `embedding_status.status` is `ready`.
- `overall_status` is `ready`.
- Workspace index status is `indexed`.

Ask a real local question:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/ask-selected \
  -H "Content-Type: application/json" \
  -d '{"question":"How is Terraform backend configured?","limit":5}'
```

Expected success signals:

- Response has `llm_provider: ollama`.
- Response has `llm_model: llama3.2`.
- Answer is not the deterministic fake-answer text.
- Sources include relevant project files such as `terragrunt.hcl` and `main.tf`.
- `quality_warnings` is empty, or any warnings are explainable from the
  retrieved context.

Frontend verification:

- Overview shows Local AI status `Ready`.
- Models shows selected and active LLM/embedding as matching.
- Ask response badge shows `ollama/llama3.2`.
- Sources show relevant top files.
- Activity includes `Workspace Question Asked` events with `llm_provider=ollama`.

### Troubleshooting real local AI mode

Runtime still shows `memory` / `fake` / `fake`:

- An old backend process is still running on port 8000.
- Environment variables were not exported in the shell that started Uvicorn.
- Check the port with `lsof -nP -iTCP:8000 -sTCP:LISTEN`.
- Check Python environment visibility with `python -c 'import os; ...'` before
  starting Uvicorn.

`ask-selected` still uses `fake`:

- Workspace selected LLM is still a fake model.
- Update it with `PUT /workspaces/{workspace_id}/models/selection` using the
  `provider`, `model`, and `model_type` payload shown above.
- Check `/models/selection/status` before asking again.

Index or sources still look old:

- Reindex after changing embedding model or vector store.
- Qdrant collections are embedding-provider, model, and dimension aware; a new
  vector space needs a new index.

Ollama is missing a model:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
```

Qdrant is not reachable:

```bash
podman start qdrant
curl http://127.0.0.1:6333/healthz
```

## Command Runner

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `COMMAND_RUNNER` | `fake` | `fake`, `local` | Selects fake execution or the guarded local subprocess adapter. | Explicitly enable real policy-allowed local execution. |
| `COMMAND_TIMEOUT_SECONDS` | `30` | Integer seconds | Maximum local command execution time. | Approved readonly commands need a different limit. |
| `COMMAND_OUTPUT_LIMIT_CHARS` | `20000` | Integer characters | Maximum captured stdout and stderr length per stream. | Adjust audit-output size. |

Approval alone never permits execution. The command must also pass execution
policy, and local execution restricts `cwd` to the workspace project path.

## Runtime Health

| Variable | Default | Allowed/format | Purpose | Change when |
| --- | --- | --- | --- | --- |
| `RUNTIME_HEALTH_TIMEOUT_SECONDS` | `3` | Integer seconds | Timeout for lightweight configured-provider health checks. | Local providers need a slightly longer health-check window. |

## Common Modes

Default dependency-light development:

```bash
VECTOR_STORE=memory \
EMBEDDING_PROVIDER=fake \
LLM_PROVIDER=fake \
COMMAND_RUNNER=fake \
python -m uvicorn app.main:app --reload
```

Persistent local RAG with guarded fake command execution:

```bash
VECTOR_STORE=qdrant \
EMBEDDING_PROVIDER=ollama \
LLM_PROVIDER=ollama \
COMMAND_RUNNER=fake \
QDRANT_URL=http://localhost:6333 \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_EMBEDDING_MODEL=nomic-embed-text \
OLLAMA_LLM_MODEL=llama3.2 \
python -m uvicorn app.main:app --reload
```

`COMMAND_RUNNER=local` should be enabled separately and intentionally after
reviewing the command approval and policy controls.
