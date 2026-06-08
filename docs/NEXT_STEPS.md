# Next Steps

## Latest Completed Tasks

The deterministic **Model Switching Plan** is implemented at
`POST /models/switching-plan`. It explains what would happen if a user selected
another LLM or embedding model before any settings, indexes, or runtimes are
changed.

The plan is advisory only. It does not edit environment variables,
restart services, download models, switch providers, or trigger indexing.

The deterministic **Model Experiment Plan** is implemented at
`POST /models/experiments/plan`. It validates a workspace, enriches LLM
candidates from the current catalog, reports index readiness and per-request
override support, and describes future comparison measurements without running
or persisting an experiment.

Per-request LLM override is implemented on
`POST /workspaces/{workspace_id}/ask` for supported `fake` and `ollama`
providers. It allows one selected model to answer using the existing workspace
context without changing active runtime settings or restarting the backend.

Persistent **Model Experiment Runs** are implemented at
`POST /models/experiments/run`. Each run retrieves workspace context once,
executes explicitly selected candidates against the same prompt, isolates
candidate failures, persists results, and records timeline activity.

The deterministic **Model Experiment Comparison Summary** is implemented at
`GET /models/experiments/{experiment_id}/comparison`. It reads a saved run and
returns candidate completion state, answer length, latency, source count,
quality-warning count, deterministic scores, warnings, and a recommended
candidate.

Manual **Model Experiment Candidate Ratings** are implemented at
`POST /models/experiments/{experiment_id}/ratings` and
`GET /models/experiments/{experiment_id}/ratings`. Users can append ratings,
preferences, tags, and comments without changing original experiment answers.
Comparison summaries expose rating counts, averages, and preferred votes.

The workspace-scoped **Model Performance Summary** is implemented at
`GET /workspaces/{workspace_id}/model-performance`. It aggregates saved
candidate outcomes and manual feedback into explainable historical statistics
and deterministic performance scores without calling a provider or mutating
history.

Workspace-aware, rating-aware **Model Recommendations** are implemented at
`POST /workspaces/{workspace_id}/models/recommend`. The endpoint combines
current catalog scoring with workspace performance history while keeping every
historical adjustment visible and leaving models without history eligible.
Fake/testing models remain visible but receive an explicit workspace-use
penalty so they are not promoted above similarly scored real local models.

Deterministic **Model Recommendation Explanations** are implemented at
`POST /workspaces/{workspace_id}/models/explain`. Explanations combine catalog
fit, workspace history, switching impact, risks, and suggested next actions
without checking providers or changing model selection.

Persistent **Workspace Model Selection State** is implemented at
`GET /workspaces/{workspace_id}/models/selection` and
`PUT /workspaces/{workspace_id}/models/selection`. It stores selected LLM and
embedding preferences separately, reports configuration-match notes, and warns
when an embedding preference change may require reindexing.

Read-only **Workspace Model Selection Status** is implemented at
`GET /workspaces/{workspace_id}/models/selection/status`. It compares selections
with active configured provider/model names and workspace index metadata, then
reports restart, reindex, readiness, and next-action guidance.

Read-only **Selected Model Usage Plan** is implemented at
`GET /workspaces/{workspace_id}/models/usage-plan`. It explains whether the
selected LLM can be used through `/ask` per-request override and whether the
selected embedding can safely index and search with the active vector space.
It returns ordered setup, restart, reindex, and ask actions without performing
any of them.

**Ask With Selected LLM** is implemented at
`POST /workspaces/{workspace_id}/ask-selected`. It resolves the persisted
selected LLM, validates per-request provider support, and delegates to the
existing RAG ask flow. It never changes the active runtime or embedding/index
configuration.

## Immediate Next Task: Selected Embedding Indexing Plan Or Real Ollama Experiment Run

The next recommended task is either an explicit selected-embedding indexing
plan, which explains the required restart/reindex sequence without performing
it, or further polishing of explicitly invoked real Ollama model experiments.

This builds naturally on the catalog, recommendations, and switching plan:

- The catalog describes available candidates.
- Recommendations rank candidates deterministically.
- The switching plan explains operational consequences.
- The experiment plan explains comparison readiness and candidate warnings.
- Experiments can compare candidate behavior before a user chooses a model.
- Comparison summaries give the UI an explainable deterministic baseline.
- Manual ratings capture real user/project feedback for future recommendations.
- Workspace-aware recommendations merge catalog fit with that feedback.

## Implemented Switching Rules

### LLM Changes

Changing only the LLM provider or LLM model does **not** require reindexing.
Existing vector chunks and embeddings can still be retrieved, then passed to
the newly selected generation model.

A switching plan should still warn about:

- Model availability not being verified unless a later runtime validation step
  is explicitly requested.
- Different context-window or performance characteristics.
- Potential answer-quality changes.

### Embedding Model Changes

Changing the embedding provider or embedding model **does** require a new index.
Stored vectors were created in the previous model's vector space and cannot be
safely searched using embeddings from another model.

The current Qdrant adapter already uses embedding-provider, model, and dimension
information when deriving collection names. The switching plan explains that a
new collection and workspace reindex are required.

### Vector Database Changes

Changing the vector-store adapter or vector database may require reindexing or
migration because the newly selected store may not contain existing workspace
chunks.

Examples:

- Moving from the in-memory vector store to Qdrant requires indexing into
  Qdrant.
- Moving from Qdrant to memory requires rebuilding the active in-memory index.
- Changing Qdrant URL or collection base name may point to an empty store and
  require reindexing.

Vector-store switching itself remains a future planning capability.

## Expected Future Endpoints

### `POST /models/experiments`

Expected purpose:

- Create a user-approved model experiment definition.
- Record selected models, task, workspace, inputs, and evaluation intent.
- Avoid silently changing active workspace/runtime configuration.

### `GET /models/experiments/{id}`

Expected purpose:

- Read experiment status and results.
- Support later answer comparison, benchmark evidence, and model-selection
  decisions.

## Follow-On Tasks

1. Selected embedding indexing plan or real Ollama experiment run.
2. Runtime selection validation against installed/available local models.
3. Ollama-backed real experiment polish.
4. AI-assisted experiment evaluator.
3. Runtime model validation against installed Ollama models.
4. Hugging Face metadata importer.
5. UI shell and model-management views.
6. Desktop launcher and installer.

## Safety Requirements

- Never change active runtime settings automatically.
- Never download models automatically.
- Never start or stop Ollama, Qdrant, or other runtimes automatically.
- Never reindex automatically.
- Future UI flows must show the plan and require explicit user confirmation
  before runtime changes, downloads, migrations, or reindexing.
- Keep provider-specific checks and actions behind adapters.
- Keep switching-plan logic deterministic and framework-neutral.
