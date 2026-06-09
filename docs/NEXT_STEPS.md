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

Read-only **Selected Embedding Indexing Plan** is implemented at
`GET /workspaces/{workspace_id}/models/embedding-indexing-plan`. It explains
whether the selected embedding matches the active runtime, whether indexing and
search can proceed, and whether restart, a new vector collection, and reindexing
are required. It performs none of those actions.

Read-only **Workspace Models Dashboard** is implemented at
`GET /workspaces/{workspace_id}/models/dashboard`. It aggregates selected
models, readiness/status, usage guidance, embedding-indexing guidance,
workspace-aware recommendations, performance history, and the primary next
model action for the future workspace Models UI.

Compact **Workspace Models Dashboard Summary** is implemented at
`GET /workspaces/{workspace_id}/models/dashboard/summary`. It projects the
detailed dashboard into a lightweight model status card with selected/active
models, top recommendation, warning count, readiness, and next action.

Read-only **Local AI Activation Guide** is implemented at
`GET /workspaces/{workspace_id}/local-ai/activation-guide`. It turns selected
workspace models, active configuration, and index metadata into explicit
Qdrant, Ollama, backend-restart, reindex, and ask-selected instructions without
executing or verifying any of them.

Read-only **Workspace UI Action Catalog** is implemented at
`GET /workspaces/{workspace_id}/ui-actions`. It gives the future frontend stable
button/card metadata, action status, target HTTP method and endpoint, mutation
flags, and one deterministic primary action without executing any action.

The **Frontend API Map** is documented in
[FRONTEND_API_MAP.md](FRONTEND_API_MAP.md). It maps app screens, cards, action
buttons, provider boundaries, mutations, and timeline effects to the current
backend surface.

The **Frontend Workbench MVP** now exists in `frontend/`. It uses Vite, React,
and TypeScript to render a polished local workbench with a dark workspace
sidebar plus Overview, Ask, Models, Actions, and Activity tabs. The frontend
uses the stable API map, keeps setup commands copy-only, and never executes
workspace actions.

The **Real Local AI Happy Path** has been manually verified end to end:

- Runtime health shows `VECTOR_STORE=qdrant`, `EMBEDDING_PROVIDER=ollama`, and
  `LLM_PROVIDER=ollama`.
- Qdrant and Ollama are configured and healthy.
- `nomic-embed-text` is used for embeddings.
- `llama3.2` is used for local generation.
- Workspace reindex into Qdrant succeeds.
- Workspace selected LLM and embedding status becomes `ready`.
- `ask-selected` returns a real Ollama answer with relevant `terragrunt.hcl` and
  `main.tf` sources.
- Frontend Overview shows Local AI status `Ready`, Ask shows `ollama/llama3.2`,
  and Activity records Ollama-backed question events.

## Latest Frontend Model Selection Editing Flow

The frontend Models tab now includes a safe model selection editing flow. Users
can update selected LLM and selected embedding preferences from the UI without
using curl. The flow remains advisory and explicit:

- Shows current selected and active LLM/embedding.
- Lets the user choose from current selection, active runtime, and available
  recommendations.
- Saves one selection at a time only after explicit button click.
- Uses the correct backend payload: `provider`, `model`, `model_type`, and
  optional `selected_reason`.
- Refreshes read-only workspace/model dashboard state after save.
- Does not restart the backend.
- Does not download models.
- Does not reindex automatically.
- Does not execute setup commands.

## Next Recommended Tasks

1. Add copy-only frontend reindex guidance when selected embedding and active
   runtime match but the workspace needs a fresh index.
2. Add optional model catalog browsing beyond the top workspace recommendations.
3. Add better source-ranking diagnostics for Ask results.
4. Run a `llama3.2` vs `qwen2.5-coder` comparison experiment against the same
   workspace context.
- Usage and embedding-indexing plans explain whether ask/search/indexing can
  proceed.
- The Local AI Activation Guide provides copy-only setup instructions.

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

1. Frontend model selection editing flow with explicit confirmation and
   copy-only restart/reindex guidance.
2. Frontend reindex guidance that copies the correct curl command but does not
   execute it automatically.
3. Better source-ranking diagnostics for Ask results, including low-score and
   irrelevant-source explanations.
4. Optional `qwen2.5-coder` comparison experiment against `llama3.2` using the
   existing experiment endpoints.
5. Runtime model validation against installed Ollama models.
6. Ollama-backed real experiment polish and AI-assisted experiment evaluator.
7. Hugging Face metadata importer.
8. Desktop launcher and installer.

## Safety Requirements

- Never change active runtime settings automatically.
- Never download models automatically.
- Never start or stop Ollama, Qdrant, or other runtimes automatically.
- Never reindex automatically.
- Future UI flows must show the plan and require explicit user confirmation
  before runtime changes, downloads, migrations, or reindexing.
- Keep provider-specific checks and actions behind adapters.
- Keep switching-plan logic deterministic and framework-neutral.

## Completed: Frontend reindex guidance

The Ask and Models screens now show copy-only reindex guidance when the workspace index is missing, sources are empty, or selected embedding search/index readiness requires manual attention. The frontend still does not execute reindexing automatically.

Follow-up ideas:
- Add a dedicated setup checklist screen that combines runtime health, model selection, and index state.
- Add source ranking diagnostics for low-score or off-topic retrieval.
- Add optional qwen2.5-coder comparison experiments after the local Ollama/Qdrant path is stable.

## Frontend scan-before-index guidance

The frontend now shows copy-only scan and index commands when a workspace has no usable index. This reflects the backend requirement that project scanning must happen before workspace indexing. The UI still does not execute scan or index automatically.


## Task 99: LLM Runtime Mismatch Guidance

Frontend Models now treats LLM selection mismatches as an informational per-request preference, while embedding runtime mismatches remain action-required because they affect search/index compatibility. Saving LLM or embedding preferences remains manual-submit only and does not restart runtime, reindex, or execute commands.

## Completed: Frontend model experiment plan UI

The Models tab now includes a safe LLM comparison planner that calls
`POST /models/experiments/plan` and displays candidate readiness, shared-context
strategy, required restart/reindex flags, recommended actions, and notes. It is
advisory only and does not call models or run experiments.

Recommended next tasks:
- Add an explicitly confirmed frontend experiment run flow using `POST /models/experiments/run`.
- Add a comparison results screen for `GET /models/experiments/{id}/comparison`.
- Add manual rating UI for model experiment candidates.

## Completed: Frontend model experiment run UI

The Models tab can now run an explicitly requested local LLM comparison with
`POST /models/experiments/run` after the user generates a comparison plan. The
UI shows the experiment id, status, candidate answer previews, latency, source
counts, warning counts, notes, and simple manual-review hints. The flow calls
local LLMs but does not execute shell commands, change selected models, restart
runtime, download models, scan, index, or rebuild workspace context.

Recommended next tasks:
- Add a saved experiment details view using `GET /models/experiments/{experiment_id}`.
- Add deterministic comparison scoring view using `GET /models/experiments/{experiment_id}/comparison`.
- Add manual rating UI for model experiment candidates.

## After Task 102: Experiment ratings

Completed:

- Frontend can display experiment run results.
- Frontend can save manual ratings for experiment candidates.
- Ratings include provider/model, score, preferred flag, tags, and comment.
- Saved ratings are shown under the completed experiment result.

Recommended next tasks:

1. Add a small "Apply preferred model" guidance flow that copies or calls the existing model selection endpoint only after explicit confirmation.
2. Add experiment history browsing from the Models tab using existing workspace experiment endpoints.
3. Improve performance summary cards using accumulated ratings and preferred votes.
