# Installed model detection

Task 205 adds a read-only local model status check.

## Endpoint

`GET /models/local-install-status`

The backend calls Ollama `GET /api/tags` and maps recommended catalog models to one of:

- `installed`
- `missing`
- `unknown` when Ollama is not reachable

## Safety

This endpoint is read-only. It does not:

- run `ollama pull`;
- remove models;
- start or stop Ollama;
- rebuild indexes;
- execute MCP tools;
- run shell commands from the frontend.

The UI can use this endpoint to tell the user which models are already present before offering manual install commands or future approved download worker actions.
