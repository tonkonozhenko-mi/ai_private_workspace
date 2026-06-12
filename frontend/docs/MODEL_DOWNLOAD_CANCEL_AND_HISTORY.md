# Model download cancel and history semantics

Task 210 adds the user-facing safety model for local model download jobs.

## What changed

- Model download jobs can be listed with `GET /models/local-download-jobs`.
- Jobs can be filtered by workspace with `?workspace_id=<id>`.
- A cancel request can be recorded with `POST /models/local-download-jobs/{job_id}/cancel`.
- The Models UI now has a small download history panel and cancel-safe messaging.

## Cancel behavior

The app intentionally avoids unsafe process killing.

- `queued` jobs can be cancelled before execution starts.
- `running` jobs record a cancel request, but the backend does not blindly kill the Ollama process.
- The worker waits for a safe final result and records `succeeded` or `failed`.
- Finished jobs cannot be cancelled.

This keeps the desktop runtime predictable and avoids leaving partially written model files in an unknown state.

## Safety rules

- The frontend never executes shell commands.
- The backend only runs allowlisted `ollama pull <catalog-model-name>` commands.
- Execution is still disabled by default.
- Installing an embedding model does not rebuild indexes automatically.
- MCP/tools/agent execution are not affected by this feature.

## API

```text
GET  /models/local-download-jobs
GET  /models/local-download-jobs?workspace_id=<workspace-id>
GET  /models/local-download-jobs/{job_id}
POST /models/local-download-jobs/{job_id}/cancel
```

## UX intent

The user should see one calm flow:

1. Pick a model.
2. Create a draft.
3. Start the approved backend job.
4. Watch status.
5. Cancel safely if it has not started, or request safe cancel if already running.
6. Re-check installed models after completion.
