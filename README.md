# Private Project AI Workbench

Initial FastAPI foundation for a local AI workbench application.

This skeleton keeps the application core independent from FastAPI and concrete adapters. Real vector database, local LLM, embedding, memory, and command execution integrations are intentionally not implemented yet.

## Requirements

- Python 3.11+
- Docker, optional

## Local Setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Use any Python 3.11+ executable if your local command is not `python3.11`.

## Run Tests

From the repository root:

```bash
source backend/.venv/bin/activate
pytest backend/tests
```

## Start The API

From inside `backend`:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Docker

From the repository root:

```bash
docker compose up --build
```

## Workspace Storage

Workspace metadata is persisted in SQLite by default. The local database is stored at `.ai-workbench/workspaces.db` relative to the directory where the API process starts.

Override the database path with an environment variable:

```bash
WORKSPACE_DB_PATH=/absolute/path/to/workspaces.db uvicorn app.main:app --reload
```

You can also switch the repository adapter:

```bash
WORKSPACE_REPOSITORY=memory uvicorn app.main:app --reload
```

Reset local app data by stopping the API and deleting `.ai-workbench/`.

## Endpoints

- `GET /health`
- `POST /workspaces`
- `GET /workspaces`
- `GET /workspaces/{workspace_id}`
- `POST /workspaces/{workspace_id}/scan`
- `GET /workspaces/{workspace_id}/scan`
- `GET /workspaces/{workspace_id}/summary`
- `GET /workspaces/{workspace_id}/analysis/terraform`
- `GET /workspaces/{workspace_id}/analysis/gitlab-ci`
- `GET /workspaces/{workspace_id}/analysis/github-actions`
- `GET /workspaces/{workspace_id}/analysis/terragrunt`
- `GET /workspaces/{workspace_id}/analysis/summary`
- `POST /workspaces/{workspace_id}/commands`
- `GET /workspaces/{workspace_id}/commands`
- `GET /workspaces/{workspace_id}/commands/suggestions`
- `POST /commands/{command_id}/approve`
- `POST /commands/{command_id}/reject`
- `POST /commands/{command_id}/execute`
- `POST /projects/scan`
- `GET /runtime/health`
- `POST /runtime/setup-guide`
- `POST /onboarding/plan`
- `POST /onboarding/setup-commands`

Example workspace payload:

```json
{
  "name": "Example Workspace",
  "project_path": "/path/to/local/project",
  "assistant_mode": "local",
  "privacy_mode": "private"
}
```

## Project Scanning

Scan a local project directory to detect deterministic signals such as Terraform, Python, Docker, Kubernetes, Helm, GitLab CI, GitHub Actions, Markdown documentation, YAML configuration, and shell scripts.

```bash
curl -X POST http://127.0.0.1:8000/projects/scan \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/absolute/path/to/project"}'
```

The scanner walks the local filesystem, skips common generated/dependency directories, skips files larger than 2 MB, and uses filenames, extensions, and small content checks for detection. No AI, embeddings, vector database, Ollama, LangChain, or LlamaIndex is used yet.

The scanner detects file signals first, then the core Skill Registry maps those signals to skill matches and categories such as `devops`, `developer`, `documentation`, and `general`. New skills can be added by extending registry definitions without changing the API route or scan use case.

## Workspace Project Scans

After creating a workspace, scan the project path saved on that workspace:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/scan
```

Read the latest saved scan:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/scan
```

The latest workspace scan is persisted as JSON in SQLite in the `workspace_project_scans` table. This keeps restart behavior simple for now while leaving room to normalize files and skills later.

## Workspace Summary

Use the workspace summary endpoint to power a future welcome-back or continue-workspace dashboard:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/summary
```

The summary returns lightweight workspace metadata, whether a latest scan exists, detected skills, deterministic suggested actions, and command activity counts. Command activity includes pending, approved, rejected, executed, and failed command totals plus the most recently proposed command. It only reads persisted command proposals and does not execute commands.

## Project Overview Report

After scanning a workspace project, generate a deterministic project overview report:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/reports/project-overview
```

The report summarizes workspace metadata, detected technologies, infrastructure signals, CI/CD signals, application code, documentation, deterministic findings, recommended next steps, and read-only command suggestions. It uses the latest saved scan, the analysis summary, command suggestion templates, and deterministic rules. It does not use AI, embeddings, vector search, or command execution. Later, this report can become clean context for AI/RAG features.

## Workspace Indexing

After scanning a workspace project, build the first local context index:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/index
```

Search indexed chunks:

```bash
curl "http://127.0.0.1:8000/workspaces/{workspace_id}/context/search?query=terraform&limit=5"
```

Indexing reads text-like files from the latest saved project scan, chunks file contents with deterministic character-based chunking, generates embeddings through the replaceable `EmbeddingProviderPort`, and stores chunks through the replaceable `VectorStorePort`. Fake embeddings and the in-memory vector store remain the defaults. Reindexing clears the previous index for that workspace before storing new chunks. Optional local Ollama embeddings and Qdrant storage are available, but no cloud APIs, LangChain, LlamaIndex, LLM chat generation, or command execution are involved.

Check persistent index status metadata:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/index/status
```

The vector chunks themselves are still in-memory for now, but lightweight index status metadata is persisted in SQLite in `workspace_index_status`. The status records whether the workspace is `not_indexed`, `indexed`, or `failed`, plus indexed file count, chunk count, skipped file count, last indexed timestamp, and the last error if indexing failed. Workspace summary responses include this same `index_status` object for the future welcome-back dashboard.

## Ask Workspace Question

After indexing a workspace, ask a question using retrieved workspace context:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How is Terraform backend configured?",
    "limit": 5
  }'
```

The ask flow embeds the question, searches indexed context through `VectorStorePort`, builds a source-grounded context-only prompt, and calls `LLMProviderPort`. The prompt requires technical claims to mention source paths, asks the model to compare relevant configurations across files, and prevents it from claiming something is absent when any retrieved chunk contains it. `FakeLLMProvider` is the default and returns a deterministic fake answer; no cloud API is used.

An LLM can still produce an incorrect answer despite these grounding instructions. The response includes deterministic `quality_warnings` for suspicious patterns such as an empty answer despite available sources, claims that no context exists, missing source-path citations, or possible absence claims that conflict with retrieved content. These warnings are guardrails, not proof that an answer is wrong. The response source list should be shown by the UI and used by the user to verify technical claims against the retrieved project files.

Context retrieval follows the configured adapters, so development can use fake embeddings with the in-memory vector store, while optional Ollama embeddings and Qdrant storage can be enabled independently.

When no context is found, the response includes `diagnostic_code` and `diagnostic_message` fields:

- `workspace_not_indexed`: no persisted index metadata exists; run workspace indexing first.
- `index_metadata_exists_but_no_chunks_found`: indexing metadata exists, but the active vector store returned no chunks.
- `no_relevant_context_found`: the active index returned no context for the question.

The in-memory vector store loses all chunks when the API process restarts, while SQLite index-status metadata survives. This can produce `index_metadata_exists_but_no_chunks_found`; reindex the workspace after restart. Qdrant persists vector chunks and is recommended when RAG context must survive API restarts. When using Qdrant, verify the configured vector store, embedding provider, embedding model, and generated collection if this diagnostic appears.

## Workspace Timeline

The persistent workspace timeline powers the future "Welcome back" and "Continue where you left off" experience. It records chronological events for workspace creation, project scans, indexing, project overview generation, command approval activity, command execution results, and workspace questions.

Get the newest workspace events:

```bash
curl "http://127.0.0.1:8000/workspaces/{workspace_id}/timeline?limit=50"
```

Timeline events are stored in SQLite as lightweight records with string metadata and are returned newest first. Workspace summary responses also include the five newest events in `recent_events`.

### Timeline Backfill

Existing workspaces created before timeline support can initialize their activity history from already-persisted workspace, latest scan, index-status, and command records:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/timeline/backfill
```

Backfilled events use original workspace, command, and indexing timestamps when available and include `"backfilled": "true"` metadata. Running the backfill repeatedly is safe: workspace/scan/index events are deduplicated by event type, while command events are deduplicated by event type plus `command_id`. Backfill does not execute commands or modify scan, index, or vector data.

## Workspace Readiness

The workspace readiness endpoint provides a lightweight dashboard decision model for what a workspace can do now and what the user should do next:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/readiness
```

Readiness is derived only from persisted workspace, scan, index-status, and command records plus configured adapter settings. It reports `needs_setup` before scanning or indexing, `ready` after a successful index, and `degraded` after an indexing failure. It also lists capabilities, pending command-review recommendations, and the configured vector store, embedding provider, LLM provider, and command runner.

The readiness endpoint does not call Ollama or Qdrant health endpoints and does not execute commands. Provider configuration indicates selected adapters, not confirmed external-service availability.

## Runtime Health

The runtime health endpoint checks whether configured local runtime dependencies are currently reachable:

```bash
curl http://127.0.0.1:8000/runtime/health
```

Qdrant is checked with a lightweight collections request only when `VECTOR_STORE=qdrant`. Ollama is checked with `/api/tags` only when the embedding or LLM provider is set to `ollama`, and configured Ollama models are verified against the returned model list. The command-runner check only reports the configured mode and never executes a command.

Optional Qdrant or Ollama services report `not_configured` under the default memory/fake configuration. If a selected dependency is unreachable or returns an error, runtime health reports `degraded` without preventing the application from starting. Health checks use the short `RUNTIME_HEALTH_TIMEOUT_SECONDS` timeout, which defaults to `3`.

## Assistant Profiles

Assistant Profiles power the future onboarding wizard by describing role-oriented capabilities, actions, and recommended local runtime configuration:

```bash
curl http://127.0.0.1:8000/assistant-profiles
```

Available profiles are DevOps Assistant, Developer Assistant, Documentation Assistant, Support Incident Assistant, and Manager Summary Assistant.

Get deterministic recommendations for a workspace's selected `assistant_mode`:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/assistant-recommendation
```

Recommendations combine the selected profile with the latest detected skills and index status. Missing scans recommend `scan_project`; detected Terraform, Terragrunt, Python, or CI/CD skills enable their relevant profile actions; and missing indexing or default fake/in-memory providers are reported as missing capabilities. Legacy or unknown assistant modes use the Developer Assistant profile while preserving the workspace's stored mode. No AI calls or commands are executed.

## Onboarding Plan

The onboarding plan endpoint powers the future setup wizard by combining an assistant profile, laptop performance profile, and privacy preference into deterministic runtime recommendations and ordered setup steps:

```bash
curl -X POST http://127.0.0.1:8000/onboarding/plan \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_profile_id": "devops",
    "laptop_profile_id": "balanced",
    "privacy_mode": "local_only"
  }'
```

`low_power` recommends memory and fake providers so real local AI can be enabled later. `balanced` recommends Qdrant, Ollama, `nomic-embed-text`, and `llama3.2`. `powerful` recommends the same local stack with `qwen2.5-coder` as the stronger coding-model placeholder. Local-only plans prefer local providers except when the low-power constraint intentionally selects lightweight defaults.

The endpoint only returns a plan. It does not create a workspace, start Qdrant or Ollama, pull models, execute commands, or make AI calls.

### Onboarding Setup Commands

The onboarding wizard can request concrete setup instructions for either Podman or Docker:

```bash
curl -X POST http://127.0.0.1:8000/onboarding/setup-commands \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_profile_id": "devops",
    "laptop_profile_id": "balanced",
    "privacy_mode": "local_only",
    "container_runtime": "podman"
  }'
```

Use `"container_runtime": "docker"` to receive the Docker Compose Qdrant instruction instead. Plans that recommend Qdrant include its container setup command, plans that recommend Ollama include model-pull instructions, and every plan includes an example backend start command with the recommended provider settings.

These commands are instructions only. They are classified with the deterministic command-risk classifier, always return `can_be_proposed: false`, are never executed, and are never automatically created as workspace command proposals.

### Runtime Setup Guide

The runtime setup guide combines the desired onboarding runtime with lightweight current runtime health, then marks each setup instruction as `done` or `needed`:

```bash
curl -X POST http://127.0.0.1:8000/runtime/setup-guide \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_profile_id": "devops",
    "laptop_profile_id": "balanced",
    "privacy_mode": "local_only",
    "container_runtime": "podman"
  }'
```

Use `"container_runtime": "docker"` for Docker-oriented Qdrant instructions. The guide marks Qdrant setup done when the selected Qdrant runtime is reachable, marks Ollama model pulls done only when the required models are reported as installed, and recommends a backend restart when the current provider settings differ from the onboarding plan.

The overall status is `ready` when all required actions are done, `degraded` when a configured runtime dependency is unhealthy, and `needs_setup` otherwise. The endpoint performs only lightweight runtime health checks; it does not execute commands, create proposals, index workspaces, ask questions, or mutate workspace data.

## Qdrant Vector Store

Qdrant is an optional `VectorStorePort` adapter. The default remains the in-memory vector store, so the API and normal test suite do not require Qdrant.

Start the optional Qdrant service:

```bash
docker compose --profile qdrant up -d qdrant
```

Enable Qdrant when starting the API:

```bash
VECTOR_STORE=qdrant \
QDRANT_URL=http://localhost:6333 \
QDRANT_COLLECTION=ai_workbench_chunks \
uvicorn app.main:app --reload
```

The adapter stores all workspaces using the same embedding configuration in one collection and filters searches and deletions by `workspace_id`. Qdrant persists vector chunks, but it remains optional and no LLM chat generation is included.

Qdrant collection names are derived automatically from the configured base name, embedding provider, embedding model, and actual vector dimension. For example:

```text
ai_workbench_chunks_fake_fake_embedding_128
ai_workbench_chunks_ollama_nomic_embed_text_768
```

This prevents a collection created with fake 128-dimension embeddings from being reused with Ollama 768-dimension embeddings. Switching embedding providers or models creates and uses a different compatible collection. Existing collections are never deleted automatically.

Run the optional live Qdrant contract test:

```bash
RUN_QDRANT_TESTS=true QDRANT_URL=http://localhost:6333 pytest backend/tests/test_qdrant_vector_store_contract.py
```

## Ollama Embeddings

Ollama is an optional local `EmbeddingProviderPort` adapter. Fake deterministic embeddings remain the default, so the API and normal test suite do not require Ollama.

Install and run Ollama separately, then pull the default embedding model:

```bash
ollama pull nomic-embed-text
```

Enable Ollama embeddings when starting the API:

```bash
EMBEDDING_PROVIDER=ollama \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_EMBEDDING_MODEL=nomic-embed-text \
OLLAMA_TIMEOUT_SECONDS=30 \
uvicorn app.main:app --reload
```

Ollama embeddings can be combined with the optional Qdrant vector store:

```bash
VECTOR_STORE=qdrant \
EMBEDDING_PROVIDER=ollama \
QDRANT_URL=http://localhost:6333 \
OLLAMA_BASE_URL=http://localhost:11434 \
uvicorn app.main:app --reload
```

The Ollama embedding adapter calls only the local `/api/embeddings` endpoint. No cloud APIs, LangChain, or LlamaIndex integration is included.

Run the optional live Ollama integration test:

```bash
RUN_OLLAMA_TESTS=true \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_EMBEDDING_MODEL=nomic-embed-text \
pytest backend/tests/test_ollama_embedding_provider.py
```

## Ollama LLM Provider

Ollama is also available as an optional local `LLMProviderPort` adapter for workspace question answers. `FakeLLMProvider` remains the default, so normal development and tests do not require an Ollama generation model.

Pull the default local generation model:

```bash
ollama pull llama3.2
```

Enable Ollama generation for `/workspaces/{workspace_id}/ask`:

```bash
LLM_PROVIDER=ollama \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_LLM_MODEL=llama3.2 \
OLLAMA_LLM_TIMEOUT_SECONDS=120 \
uvicorn app.main:app --reload
```

Run the complete optional local RAG stack:

```bash
VECTOR_STORE=qdrant \
EMBEDDING_PROVIDER=ollama \
LLM_PROVIDER=ollama \
QDRANT_URL=http://localhost:6333 \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_EMBEDDING_MODEL=nomic-embed-text \
OLLAMA_LLM_MODEL=llama3.2 \
uvicorn app.main:app --reload
```

The Ollama LLM adapter calls only the local `/api/generate` endpoint with streaming disabled. No cloud APIs, LangChain, or LlamaIndex integration is included.

Run the optional live Ollama LLM integration test:

```bash
RUN_OLLAMA_TESTS=true \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_LLM_MODEL=llama3.2 \
pytest backend/tests/test_ollama_llm_provider.py
```

## Terraform Analysis

After scanning a workspace project, run deterministic Terraform static analysis:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/analysis/terraform
```

The Terraform analyzer reads Terraform files from the latest saved scan and checks for backend, provider, variable, output, and module blocks using simple text rules. It does not use AI and does not run the Terraform CLI yet.

## GitLab CI Analysis

After scanning a workspace project, run deterministic GitLab CI static analysis:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/analysis/gitlab-ci
```

The GitLab CI analyzer reads `.gitlab-ci.yml` from the latest saved scan, parses YAML safely, and reports stages, includes, variables, jobs, job features, and deterministic findings. It does not use AI and does not execute GitLab pipelines.

## GitHub Actions Analysis

After scanning a workspace project, run deterministic GitHub Actions static analysis:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/analysis/github-actions
```

The GitHub Actions analyzer reads `.github/workflows/*.yml` and `.github/workflows/*.yaml` files from the latest saved scan, parses YAML safely, and reports workflow names, triggers, job counts, matrix usage, permissions configuration, reusable workflows, and secrets references. It does not use AI, call the GitHub API, or execute workflows.

## Analysis Summary

After scanning a workspace project, aggregate deterministic analyzer output into a lightweight DevOps overview:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/analysis/summary
```

The analysis summary runs relevant deterministic analyzers for detected Terraform, Terragrunt, GitLab CI, and GitHub Actions files. It returns analyzer status, severity counts, top findings, and recommended next steps. This endpoint is intended to feed future dashboards, project overview generation, manager summaries, documentation drafts, and LLM context preparation, but it does not use AI or execute external commands.

## Command Approval

The command approval workflow stores proposed terminal commands for review before execution. Commands are classified with a deterministic risk label, persisted for auditability, and can be approved or rejected.

Propose a command:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/commands \
  -H "Content-Type: application/json" \
  -d '{
    "command": "git status",
    "cwd": "/absolute/path/to/project",
    "reason": "Check current repository state"
  }'
```

Approve a proposed command:

```bash
curl -X POST http://127.0.0.1:8000/commands/{command_id}/approve
```

Execute an approved command:

```bash
curl -X POST http://127.0.0.1:8000/commands/{command_id}/execute
```

List workspace commands:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/commands
```

For now execution uses a fake command runner only. No real shell commands are executed.

## Command Execution Policy

Approval alone is not enough for execution. A proposed command must also pass the deterministic execution policy before the assistant can send it to the command runner.

The current policy is conservative:

- Destructive commands are blocked.
- Compound shell commands with operators like `;`, `&&`, `||`, pipes, backticks, or `$(` are blocked.
- A small read-only allowlist can be fake-executed after approval.
- Write and unknown-risk commands are marked manual-only and must be run outside the assistant.

The runner is still fake, so even policy-allowed commands do not execute real shell commands yet.

## Local Command Runner

The real local command runner is available but disabled by default. Enable it explicitly:

```bash
COMMAND_RUNNER=local uvicorn app.main:app --reload
```

Optional settings:

```bash
COMMAND_TIMEOUT_SECONDS=30
COMMAND_OUTPUT_LIMIT_CHARS=20000
```

Safety controls:

- `FakeCommandRunner` remains the default.
- Commands must be approved and policy-allowed before a runner is called.
- Destructive, manual-only, and unknown-risk commands are not auto-executed.
- The local runner uses `subprocess.run` with `shell=False`.
- Commands are split with `shlex.split`.
- `cwd` must exist, be a directory, and stay inside the workspace `project_path`.
- Output is captured and truncated to the configured limit.

## Command Suggestions

Command suggestions are deterministic templates based on the latest workspace scan. They are not created as command proposals automatically, and they are never approved or executed automatically.

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/commands/suggestions
```

To run a suggestion through the approval workflow, the user must explicitly propose it with `POST /workspaces/{workspace_id}/commands`, then approve it, then execute it. Execution still uses the fake runner for now.

## Terragrunt Analysis

The scanner detects `terragrunt.hcl` directly and detects other `.hcl` files only when they contain Terragrunt-like blocks such as `terraform`, `include`, `dependency`, `inputs`, or `remote_state`.

After scanning a workspace project, run deterministic Terragrunt static analysis:

```bash
curl http://127.0.0.1:8000/workspaces/{workspace_id}/analysis/terragrunt
```

The Terragrunt analyzer reads Terragrunt files from the latest saved scan and checks for remote state, include blocks, dependencies, inputs, and Terraform source configuration. It does not use AI and does not execute the Terragrunt or Terraform CLI.

## Current Limitations

- Workspace metadata is stored in SQLite by default; the in-memory repository remains available for tests and local experiments.
- Project scanning is deterministic and rule-based only.
- The vector store defaults to an in-memory stub and embeddings default to a fake deterministic provider; optional Qdrant and Ollama adapters are available.
- Workspace question answers use `FakeLLMProvider` by default; optional local Ollama generation is available.
- Workspace project paths are not validated during workspace creation yet.
- No frontend is included.
