# Background model download worker

Task 209 moves local model download jobs away from a synchronous request/response execution model.

## What changed

`POST /models/local-install-drafts/{command_id}/jobs` now creates a backend-owned job and returns quickly. The UI should poll:

```text
GET /models/local-download-jobs/{job_id}
```

The job can move through:

```text
queued -> running -> succeeded
queued -> running -> failed
```

## Safety model

The frontend still never executes shell commands.

A download job can run only when all conditions are true:

- `MODEL_DOWNLOAD_EXECUTION_ENABLED=true`
- `COMMAND_RUNNER=local`
- the command draft was created by the backend
- the command is exactly `ollama pull <catalog-model-name>`
- the model is present in the backend allowlist catalog

The backend generates and validates the command. The UI only starts the approved job and reads status.

## UX model

The product should feel like a normal desktop app:

1. User selects a recommended model.
2. User creates an approved download draft.
3. User starts the backend-owned job.
4. UI shows calm status: queued, running, complete, failed.
5. After success, UI re-checks installed models.
6. Rebuild/indexing remains a separate explicit user action.

## Current limitation

The worker is an in-process background thread. This is enough for the current local desktop foundation, but a packaged app should later add a stronger supervisor/persistence layer for crash recovery.
