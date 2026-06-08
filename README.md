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
- [Project state and handoff](docs/PROJECT_STATE.md)
- [Roadmap](docs/ROADMAP.md)
- [Next steps](docs/NEXT_STEPS.md)
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

Add optional user-defined metadata by setting `USER_MODEL_CATALOG_PATH`:

```bash
cd backend
USER_MODEL_CATALOG_PATH=../examples/user_model_catalog.example.json \
uvicorn app.main:app --reload
```

The configured JSON file uses a top-level `models` list; see
[`examples/user_model_catalog.example.json`](examples/user_model_catalog.example.json).
Valid unique-ID models are merged with the built-in catalog and participate in
recommendations. Invalid entries and duplicate IDs are skipped without crashing
the app. Inspect warnings with:

```bash
curl http://127.0.0.1:8000/models/catalog/details
```

After editing the configured file, reload it without restarting the backend:

```bash
curl -X POST http://127.0.0.1:8000/models/catalog/reload
```

Reload replaces the previous user-model snapshot. Invalid metadata removes
stale user models, keeps built-ins available, and returns warnings. Changing the
configured file path still requires restarting the backend.

This metadata-only feature does not call Hugging Face or Ollama, download
models, validate installed models, run benchmarks, or change active settings.
Future versions can import Hugging Face metadata, installed Ollama models, and
benchmark or evaluation results.

## Model Switching Plan

Preview the operational impact of changing an LLM or embedding model:

```bash
curl -X POST http://127.0.0.1:8000/models/switching-plan \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "embedding",
    "current_provider": "fake",
    "current_model": "fake-embedding",
    "target_provider": "ollama",
    "target_model": "nomic-embed-text",
    "workspace_id": null
  }'
```

The deterministic plan explains restart, reindex, and vector-collection impact.
LLM switches preserve existing indexes; embedding switches require a new
dimension-aware collection and reindex. The endpoint only returns advice: it
does not change settings, download models, restart services, or reindex data.

## Model Experiment Plan

Plan a future comparison of multiple LLM candidates against the same workspace
question and indexed context:

```bash
curl -X POST http://127.0.0.1:8000/models/experiments/plan \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "WORKSPACE_ID",
    "question": "How is Terraform backend configured?",
    "experiment_type": "llm_comparison",
    "candidates": [
      {"provider": "ollama", "model": "llama3.2"},
      {"provider": "ollama", "model": "qwen2.5-coder"}
    ]
  }'
```

The deterministic plan reports catalog knowledge, installation or adapter
warnings, index readiness, and whether a candidate supports per-request model
override. It does not call LLMs, download models, reindex, change settings, or
persist an experiment run.

## Per-Request LLM Override

Normal workspace questions still use the configured default LLM provider and
model. A caller can optionally select a supported `fake` or `ollama` provider
and model for one request without changing runtime settings:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How is Terraform backend configured?",
    "limit": 5,
    "llm_provider": "ollama",
    "llm_model": "qwen2.5-coder"
  }'
```

The response `llm_provider` and `llm_model` fields identify the provider and
model actually selected. This foundation makes same-context model experiments
possible later; it does not run multiple models, install models, or change the
configured default.

## Model Experiment Runs

Run an explicit same-question comparison using one shared retrieved context:

```bash
curl -X POST http://127.0.0.1:8000/models/experiments/run \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "WORKSPACE_ID",
    "question": "How is Terraform backend configured?",
    "experiment_type": "llm_comparison",
    "limit": 3,
    "candidates": [
      {"provider": "fake", "model": "fake-llm"},
      {"provider": "fake", "model": "fake-llm-alt"}
    ]
  }'
```

Each candidate receives the exact same retrieved chunks and prompt. Results,
latency, quality-warning counts, failures, and source counts are persisted in
SQLite and can be read with:

```bash
curl http://127.0.0.1:8000/models/experiments/EXPERIMENT_ID
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/model-experiments
```

Get a concise deterministic comparison summary for a saved run:

```bash
curl http://127.0.0.1:8000/models/experiments/EXPERIMENT_ID/comparison
```

The summary scores completed candidates from observable signals such as source
count, quality-warning count, answer length, and latency. It is not a semantic
quality evaluator, and it does not call another LLM.

Save manual feedback for an experiment candidate and list the experiment's
ratings:

```bash
curl -X POST http://127.0.0.1:8000/models/experiments/EXPERIMENT_ID/ratings \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "fake",
    "model": "fake-llm",
    "rating": 4,
    "is_preferred": true,
    "tags": ["useful", "fast"],
    "comment": "Clear enough for this test."
  }'

curl http://127.0.0.1:8000/models/experiments/EXPERIMENT_ID/ratings
```

Ratings are append-only user feedback. They do not rerun experiments, change
original answers, call an LLM, or change runtime settings. Comparison summaries
include rating counts, average ratings, and preferred votes.

Summarize historical candidate outcomes and ratings for a workspace:

```bash
curl "http://127.0.0.1:8000/workspaces/WORKSPACE_ID/model-performance?limit=20"
```

The read-only summary groups recent saved experiment candidates by
provider/model and reports completion, failure, rating, preference, tag,
latency, quality-warning, and source statistics. Its score is deterministic and
advisory; it does not call models or change saved data.

Request workspace-aware model recommendations:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_profile_id": null,
    "laptop_profile_id": "balanced",
    "task_type": "workspace_ask",
    "model_type": "llm"
  }'
```

The endpoint starts with catalog recommendation scores, then adds matching
workspace performance scores and explicit rating, preference, and failure
adjustments. Models without history remain eligible with their catalog score and
a warning. Fake/testing providers remain visible but receive a workspace-use
penalty so close real local models rank above them. Recommendations are
read-only and never activate a model.

Explain a model recommendation before selecting or installing anything:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/explain \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "model": "qwen2.5-coder",
    "model_type": "llm",
    "assistant_profile_id": null,
    "laptop_profile_id": "balanced",
    "task_type": "workspace_ask"
  }'
```

The deterministic explanation includes catalog fit, workspace history,
switching impact, risks, installation guidance, and suggested next actions.
Installed-model availability is not verified, and no providers are called.

Persist and read workspace model preferences:

```bash
curl -X PUT http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/selection \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "model": "qwen2.5-coder",
    "model_type": "llm",
    "selected_reason": "Recommended for DevOps workspace questions."
  }'

curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/selection
```

LLM and embedding preferences are stored independently. Selecting one preserves
the other. Responses note whether selections match active runtime configuration,
and replacing an embedding preference warns that reindexing may be needed. No
runtime settings are changed and no reindex is triggered.

Inspect selection readiness against active configuration and index status:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/selection/status
```

The status reports per-model runtime matches, backend restart requirements,
embedding reindex requirements, overall readiness, and deterministic next
actions. It reads configuration and persisted metadata only; no runtime changes
or indexing occur.

Get a deterministic plan for using the selected models:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/usage-plan
```

Supported selected LLMs can be passed to `/ask` through per-request override,
even when they differ from the active default LLM. Selected embeddings must
match the active embedding configuration and have an indexed matching vector
space before search can use them. The plan only returns capabilities and ordered
next actions; it never restarts the backend or reindexes.

Ask using the persisted selected workspace LLM:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/WORKSPACE_ID/ask-selected \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How is Terraform backend configured?",
    "limit": 3
  }'
```

This delegates to the existing RAG ask flow with the selected LLM as a
per-request override. Retrieval still uses the active embedding/index
configuration. If a selected embedding differs from the active embedding, the
response includes a deterministic quality warning. Ollama is contacted only
when the user explicitly invokes this endpoint with an Ollama LLM selected.

Inspect the indexing impact of the selected embedding:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/embedding-indexing-plan
```

The plan reports whether the selected embedding matches the active runtime,
whether indexing and search can proceed now, and whether restart, reindexing,
or a new vector collection is required. It is advisory only: no providers are
called, no collection is created, and no indexing or runtime change occurs.

Load the complete read-only workspace Models dashboard:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/dashboard
```

The dashboard aggregates selected models, selection status, selected-model
usage, embedding-indexing guidance, workspace-aware recommendations, historical
performance, and the primary next model action. It does not call providers,
select models, change runtime settings, or trigger indexing.

Load the compact Models status-card summary:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/models/dashboard/summary
```

The compact summary includes selected and active model identities, readiness,
the primary next action, top recommendation, historical performance-model
count, and a deterministic warning count. Use the detailed Models dashboard for
full diagnostics. Both endpoints are read-only.

The main workspace dashboard also includes this compact summary as
`models_summary`:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/dashboard
```

This lets the main workspace UI render a small Models card without separately
loading the full Models dashboard. The dedicated detailed and summary endpoints
remain available and unchanged.

Generate explicit instructions for activating the workspace's selected local AI
models:

```bash
curl http://127.0.0.1:8000/workspaces/WORKSPACE_ID/local-ai/activation-guide
```

The guide compares persisted model selections with active configuration and
index metadata, then returns ordered Qdrant, Ollama, backend-restart, reindex,
and ask-selected steps. Commands are instructions only: this endpoint does not
call providers, download models, restart the backend, change settings, or
reindex the workspace. For Qdrant, the primary command starts an existing
Podman container, while the step's `commands` list also includes the separate
create-container command to use only when the container does not exist yet.

Experiments require an indexed workspace. They never reindex, download models,
change runtime settings, or execute shell commands. Ollama is contacted only
when an experiment explicitly includes an Ollama candidate.

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
