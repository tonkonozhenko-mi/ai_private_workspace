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

## Immediate Next Task: AI-Assisted Experiment Evaluator Or Real Ollama Experiments

The next recommended backend task is either an AI-assisted evaluator over saved
experiment results or an Ollama-backed real experiment flow. The evaluator
should remain explicit and read-only at first: it can analyze saved answers,
source grounding, warnings, and latency without silently selecting or activating
a winning model.

This builds naturally on the catalog, recommendations, and switching plan:

- The catalog describes available candidates.
- Recommendations rank candidates deterministically.
- The switching plan explains operational consequences.
- The experiment plan explains comparison readiness and candidate warnings.
- Experiments can compare candidate behavior before a user chooses a model.
- Comparison summaries give the UI an explainable deterministic baseline.

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

1. AI-assisted experiment evaluator or Ollama-backed real experiment polish.
2. Runtime model validation against installed Ollama models.
3. Hugging Face metadata importer.
4. UI shell and model-management views.
5. Desktop launcher and installer.

## Safety Requirements

- Never change active runtime settings automatically.
- Never download models automatically.
- Never start or stop Ollama, Qdrant, or other runtimes automatically.
- Never reindex automatically.
- Future UI flows must show the plan and require explicit user confirmation
  before runtime changes, downloads, migrations, or reindexing.
- Keep provider-specific checks and actions behind adapters.
- Keep switching-plan logic deterministic and framework-neutral.
