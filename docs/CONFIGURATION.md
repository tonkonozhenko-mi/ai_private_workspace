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
| `QDRANT_COLLECTION` | `ai_workbench_chunks` | Collection base name | Base for embedding-dimension-aware Qdrant collection names. | Isolate environments or choose a naming convention. |

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

The file is metadata only. Loading it does not call model providers, validate
installed models, download artifacts, run benchmarks, or change active runtime
settings. Restart the API after changing the configured path itself. After
editing the file at the current configured path, reload its metadata with:

```bash
curl -X POST http://127.0.0.1:8000/models/catalog/reload
```

Reload replaces the current in-memory user-model snapshot. If the file becomes
invalid or unavailable, previous user models are removed, built-in models remain
available, and the reload response plus catalog details expose warnings.

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
uvicorn app.main:app --reload
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
uvicorn app.main:app --reload
```

`COMMAND_RUNNER=local` should be enabled separately and intentionally after
reviewing the command approval and policy controls.
