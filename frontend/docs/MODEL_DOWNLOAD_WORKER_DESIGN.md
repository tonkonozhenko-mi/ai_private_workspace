# Controlled backend model download worker design

Task 204 defines the safe execution architecture for future local model downloads.

## Product goal

The final desktop app should let a user choose a local model, approve the download, watch progress, and then use the installed model without opening a terminal.

## Current status

- Download guide exists.
- Download draft intent exists.
- Backend worker execution is **not enabled yet**.
- Frontend shell execution remains forbidden.

## Worker flow

1. User chooses a recommended Ollama model.
2. Backend creates a download draft from provider/model fields.
3. User reviews size, purpose, and exact command.
4. Future backend worker receives explicit approval.
5. Backend runs only an allowlisted command pattern: `ollama pull <catalog-model-name>`.
6. Backend records pending/running/succeeded/failed status.
7. Backend verifies the installed model list.
8. User explicitly saves the model as a workspace preference or starts index rebuild.

## Guardrails

- The browser UI never executes commands.
- Users cannot submit arbitrary shell commands for model downloads.
- First executable version should allow only known catalog models.
- Embedding model install must not silently rebuild indexes.
- Progress and failure state must be visible.
- MCP/tool execution is separate and must not be mixed with model download execution.

## Planned API shape

- `POST /models/local-install-drafts/{id}/approve`
- `POST /models/local-install-drafts/{id}/run`
- `GET /models/local-install-jobs/{id}`
- `GET /models/installed`

## Why not execute yet?

This project is moving toward a packaged local desktop app. Model downloads are safer than arbitrary agent tools, but they still touch the user machine and network. The architecture is intentionally staged: guide → draft → approval → backend worker → packaged app supervisor.
