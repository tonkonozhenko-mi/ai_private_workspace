# Model download jobs

Task 207 adds a safer UX foundation for approved local model downloads.

## What changed

The old execution foundation could run a model download draft as one blocking request. The new flow introduces a backend-owned job object:

1. User creates a model download draft.
2. User explicitly starts an approved download job.
3. Backend validates the draft command against the local Ollama model catalog allowlist.
4. Backend records job status, progress message, command output preview, and final result.
5. Frontend can refresh job status, but it never executes shell commands.

## Endpoints

- `POST /models/local-install-drafts/{command_id}/jobs`
- `GET /models/local-download-jobs/{job_id}`

## Current limitation

This is a foundation step. The job runner records queued/running/final states, but the actual command still runs synchronously inside the trusted backend request. A later task can move this to a background worker with live streaming progress and cancel support.

## Safety rules

- Frontend does not execute shell commands.
- Execution remains disabled by default.
- Real execution requires `MODEL_DOWNLOAD_EXECUTION_ENABLED=true` and `COMMAND_RUNNER=local`.
- Only `ollama pull <catalog-model-name>` is allowed.
- The model must exist in the local allowlist catalog.
- Installing an embedding model does not rebuild indexes automatically.

## Task 208 UX refinement

The job API remains the same, but the UI now treats the job status as a human workflow instead of a raw command screen:

- successful jobs show a completion note and a direct installed-model refresh action;
- failed jobs hide backend output behind a troubleshooting disclosure;
- running jobs can be refreshed without exposing shell execution details;
- installed model detection is refreshable from the same panel.
