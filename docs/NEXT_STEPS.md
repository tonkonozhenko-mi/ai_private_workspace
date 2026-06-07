# Next Steps

## Immediate Next Task: Model Switching Plan

The next recommended backend task is a deterministic **Model Switching Plan**.
It should explain what would happen if a user selected another LLM, embedding
model, or vector-store configuration before any settings, indexes, or runtimes
are changed.

The plan should be advisory only. It must not edit environment variables,
restart services, download models, switch providers, or trigger indexing.

## Why This Comes Next

The model catalog can now describe, recommend, extend, and reload model
metadata. The next missing piece is explaining the operational consequences of
selecting a different model.

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
information when deriving collection names. A switching plan should explain
which workspaces need reindexing and why.

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

## Expected Future Endpoints

These endpoint names are proposed and are not implemented yet.

### `POST /models/switching-plan`

Expected purpose:

- Compare current runtime model/vector configuration with a requested target.
- Explain whether restart, model installation, or workspace reindexing would be
  required.
- Return deterministic warnings and ordered user-confirmation steps.
- Apply no changes.

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

After the Model Switching Plan:

1. Model Experiment Runs.
2. Compare answers across models.
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
