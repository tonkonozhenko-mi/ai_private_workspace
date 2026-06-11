# Model download manager plan

Task 202 adds the safe foundation for local model downloads.

Current behavior:
- The UI shows recommended local models.
- The UI explains which model is used for answers and which model is used for search context.
- The UI provides copyable `ollama pull ...` commands.
- The frontend does not execute shell commands.
- The backend does not download models yet.

Target behavior for the real desktop package:
1. User opens the desktop app.
2. App checks whether Ollama is reachable.
3. User chooses a model from a curated list.
4. App shows model purpose, estimated size, and safety impact.
5. User explicitly approves the download.
6. Backend supervisor runs the allowed `ollama pull <model>` action.
7. App verifies the model with `ollama list`.
8. If the embedding model changed, app asks the user to rebuild local search context.

Guardrails:
- No model is downloaded during startup.
- No model is downloaded from the frontend.
- No scan, index, rebuild, MCP server, or agent workflow starts because a model was downloaded.
- Embedding changes must be treated as context-impacting changes.

## Task 204 update — backend worker design

The project now exposes `GET /models/local-download-worker-plan` to describe the next safe execution stage. It keeps `worker_enabled=false` and documents the intended guardrails before adding real `ollama pull` execution.

## Task 206 update

The backend now has an opt-in execution foundation for approved model download drafts:

- `GET /models/local-download-execution-capability`
- `POST /models/local-install-drafts/{command_id}/run`

Execution remains disabled by default. It is intended for a trusted local desktop runtime and requires `MODEL_DOWNLOAD_EXECUTION_ENABLED=true` plus `COMMAND_RUNNER=local`.
