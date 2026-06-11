# Model download execution foundation

Task 206 adds the first executable backend foundation for local model downloads, but keeps it disabled by default.

## What changed

- The UI can show whether backend model download execution is available.
- A previously created download draft can be sent to `POST /models/local-install-drafts/{command_id}/run`.
- The backend validates the command before execution.

## Safety model

Execution is allowed only when all of these are true:

1. `MODEL_DOWNLOAD_EXECUTION_ENABLED=true`.
2. `COMMAND_RUNNER=local`.
3. The command proposal already exists as a model download draft.
4. The command matches exactly: `ollama pull <catalog-model-name>`.
5. The model exists in the local Ollama model catalog.

The frontend never executes shell commands. It only calls the backend endpoint.

## Explicit non-goals

This task does not add:

- automatic model downloads;
- arbitrary command execution;
- custom shell command execution;
- MCP tool execution;
- automatic scan/index/rebuild/restart;
- automatic embedding index rebuild after model install.

## Runtime notes

For a trusted local desktop runtime, configure:

```bash
MODEL_DOWNLOAD_EXECUTION_ENABLED=true
COMMAND_RUNNER=local
COMMAND_TIMEOUT_SECONDS=3600
```

The longer timeout is useful because `ollama pull` can take several minutes.

## Recommended next step

Task 207 should add job-style progress/status instead of a single blocking request:

- create download job;
- run in background worker;
- stream or poll status;
- allow safe cancel where supported;
- re-check installed models after completion.

## Task 207 update

Added model download job foundation endpoints: `POST /models/local-install-drafts/{command_id}/jobs` and `GET /models/local-download-jobs/{job_id}`. Jobs are backend-owned status records for approved Ollama downloads. The frontend can start and refresh a job, but still never runs shell commands. Execution remains opt-in and allowlisted.
