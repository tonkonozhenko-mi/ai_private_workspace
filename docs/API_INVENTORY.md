# API Inventory

This inventory describes the current backend MVP surface. `Writes` means the
endpoint persists or updates application data. `Runtime` identifies local
filesystem, provider, or command-runner activity outside SQLite repositories.

## Health And Runtime

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /health` | Process liveness check. | No | No | No | App shell |
| `GET /runtime/health` | Report configured Qdrant, Ollama, and command-runner health. | No | No | Lightweight Qdrant/Ollama checks when configured | Runtime status |
| `GET /runtime/troubleshooting` | Build a read-only troubleshooting plan for Ollama, Qdrant, fake providers, memory vector store, and safe restart commands. | No | No | Runtime health checks only | Settings troubleshooting assistant |
| `GET /runtime/first-launch-readiness` | Return read-only desktop post-launch checklist for backend, workspace data, local models, search store, and macOS launcher readiness. | No | No | Read-only runtime settings and SQLite diagnostics | Models desktop setup |
| `POST /runtime/setup-guide` | Compare recommended onboarding runtime with active runtime health. | No | No | Lightweight Qdrant/Ollama checks when configured | Setup wizard |

## Onboarding And Assistant Profiles

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /assistant-profiles` | List deterministic assistant profiles. | No | No | No | Setup wizard |
| `GET /workspaces/{workspace_id}/assistant-recommendation` | Recommend assistant capabilities from persisted workspace state. | No | No | No | Workspace setup |
| `POST /onboarding/plan` | Build a deterministic setup plan. | No | No | No | Setup wizard |
| `POST /onboarding/setup-commands` | Return setup command instructions without proposing them. | No | No | No | Setup wizard |
| `POST /onboarding/bootstrap-workspace` | Create a workspace and return initial onboarding state. | Workspace and timeline | No | Lightweight health checks through the setup guide | Setup wizard |

## Local Model Catalog

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /models/catalog` | List and filter static plus valid user-defined model metadata. | No | No | No | Model selection |
| `GET /models/gguf-catalog` | Curated GGUF models (Hugging Face repo + file) for the llama.cpp / Ollama-free backend, with download URLs and recommended flags. Read-only metadata; downloads happen via a separate job. | No | No | No | Model selection (llama.cpp) |
| `POST /models/gguf-downloads` | Start a background GGUF model download (by catalog id, or a custom Hugging Face repo + filename) for the llama.cpp backend. Returns a pollable job. Streams to a temp file and publishes atomically on success. | In-memory download job | No | Hugging Face download | Model setup (llama.cpp) |
| `GET /models/gguf-downloads/{job_id}` | Poll a GGUF download job's progress (bytes, percent, status, destination). | No | No | No | Model setup (llama.cpp) |
| `POST /models/gguf-downloads/{job_id}/cancel` | Request cancellation of a running GGUF download; the partial file is discarded. | In-memory download job | No | No | Model setup (llama.cpp) |
| `GET /models/llama-runtime/status` | Report the llama.cpp runtime: whether the bundled binary is present, whether the default models are downloaded, whether the answer/embedding servers are running, and their URLs. | No | No | Local process check | Model setup (llama.cpp) |
| `POST /models/llama-runtime/start` | Start the bundled `llama-server` for answers and a second one (`--embedding`) for search, against the downloaded GGUF models. 409 if the binary is not bundled or models are missing. | Local llama-server processes | No | Launches bundled binary | Model setup (llama.cpp) |
| `POST /models/llama-runtime/stop` | Stop both llama-server processes. | Local llama-server processes | No | No | Model setup (llama.cpp) |
| `POST /models/llama-runtime/llm` | Switch the built-in engine's answer model to another already-downloaded GGUF, persisting the choice and restarting only the answer process. 409 if the model is unknown or not downloaded. | Local llama-server answer process | No | Restarts answer process | Model setup (llama.cpp) |
| `GET /models/reranker` | Report the optional "sharper search" reranker state: whether it is enabled, its model id, whether the model is downloaded, and whether the reranker server is running. | No | No | Local process check | Model setup (llama.cpp) |
| `POST /models/reranker` | Toggle the "sharper search" cross-encoder reranker. Enabling persists the choice and starts a `llama-server --reranking` process if the model is downloaded; disabling stops it. Falls back to plain hybrid retrieval when off or unavailable. | Local llama-server reranker process | No | Launches/stops bundled binary | Model setup (llama.cpp) |
| `POST /models/gguf-delete` | Delete a downloaded GGUF model file from disk (by catalog id or repo/filename). 409 if it is the model the engine is currently running. Only model data is removed. | Local GGUF file | No | Deletes model file | Model setup (llama.cpp) |
| `POST /models/gguf-resolve` | Pick a usable GGUF filename from a Hugging Face repo (auto-chooses a good quant), so the user only pastes the repo id. Reads the public HF model API. | No | No | Reads Hugging Face model metadata | Model setup (llama.cpp) |
| `POST /models/workspace-runtime/{workspace_id}` | Re-activate the engine a workspace uses (the active backend is app-global): start the llama.cpp engine and point embeddings at it, or point embeddings back at Ollama. Best-effort. | Active embedding delegate, llama.cpp engine | No | May launch llama.cpp engine | Model setup (engine choice) |
| `POST /models/active-backend` | Switch the app-wide embedding engine between Ollama and llama.cpp so indexing and search use the chosen backend. | Active embedding delegate | No | No | Model setup (engine choice) |
| `GET /models/catalog/details` | List filtered models plus user-catalog loading and validation warnings. | No | No | No | Model catalog diagnostics |
| `POST /models/catalog/reload` | Reload the configured user model file into the in-memory catalog. | In-memory catalog only | No | Local metadata file read | Model catalog settings |
| `POST /models/recommend` | Rank catalog models for an assistant profile, laptop profile, task, and model type. | No | No | No | Model selection/setup wizard |
| `GET /models/agent-capabilities` | Describe which local LLMs appear suitable for safe planning or future tool-calling workflows. | No | No | No | Agent capability awareness |
| `POST /models/agent-planning-preview` | Build a review-only multi-step agent plan for a selected model and goal without executing anything. | No | No | No | Safe agent planning |
| `GET /workspaces/{workspace_id}/agent-workflows` | List saved manual agent workflow drafts for a workspace. | No | No | No | Agent workflow tracking |
| `POST /workspaces/{workspace_id}/agent-workflows` | Save a safe planning preview as a manual workflow checklist. | Workflow draft | No | No | Agent workflow tracking |
| `GET /workspaces/{workspace_id}/agent-workflows/{workflow_id}` | Open a saved manual agent workflow. | No | No | No | Agent workflow tracking |
| `PATCH /workspaces/{workspace_id}/agent-workflows/{workflow_id}/steps/{step_id}` | Mark a manual agent workflow step as todo, in progress, done, skipped, or needing review. Requires approval before in-progress/done for gated steps. | Workflow step status | No | No | Agent workflow tracking |
| `POST /workspaces/{workspace_id}/agent-workflows/{workflow_id}/steps/{step_id}/approval-preview` | Show a copy-only approval gate plan for a workflow step, including proposed tool, risk, evidence, and blocked actions. | Approval preview | No | No | Agent approval gates |
| `PATCH /workspaces/{workspace_id}/agent-workflows/{workflow_id}/steps/{step_id}/approval` | Record user approval/rejection intent for a workflow step. Does not execute tools or commands. | Approval status | No | No | Agent approval gates |
| `PATCH /workspaces/{workspace_id}/agent-workflows/{workflow_id}/steps/{step_id}/evidence` | Attach manual evidence notes/sources to a workflow step after the user checks results outside the browser. | Evidence metadata | No | No | Agent evidence tracking |
| `GET /workspaces/{workspace_id}/agent-workflows/{workflow_id}/execution-readiness` | Map workflow steps to approved MCP/tool inventory and show blockers before manual execution tracking. | No | No | No | Agent execution readiness |
| `PATCH /workspaces/{workspace_id}/agent-workflows/{workflow_id}/archive` | Archive or restore a manual agent workflow draft. | Workflow archived flag | No | No | Agent workflow tracking |
| `DELETE /workspaces/{workspace_id}/agent-workflows/{workflow_id}` | Delete a saved manual agent workflow draft. | Workflow delete | No | No | Agent workflow tracking |
| `POST /models/switching-plan` | Explain deterministic restart, reindex, and collection impact before switching a model. | No | No | No | Model selection/experiments |
| `POST /models/experiments/plan` | Plan a shared-context LLM comparison and enrich candidates with catalog/runtime guidance. | No | No | No | Model experiments |
| `POST /models/experiments/run` | Retrieve workspace context once, run explicitly requested LLM candidates, and persist comparison results. | Experiment and timeline | No | Configured embedding/vector providers plus explicitly selected LLM providers | Model experiments |
| `GET /models/experiments/{experiment_id}` | Get a persisted model experiment run and candidate results. | No | No | No | Model experiments |
| `GET /models/experiments/{experiment_id}/comparison` | Summarize a saved experiment run with deterministic candidate scores, warnings, and a recommended winner. | No | No | No | Model experiments |
| `POST /models/experiments/{experiment_id}/ratings` | Save user-provided rating, preference, tags, and feedback for an experiment candidate. | Rating and timeline | No | No | Model experiments |
| `GET /models/experiments/{experiment_id}/ratings` | List user-provided ratings for a saved experiment. | No | No | No | Model experiments |

The catalog is deterministic local metadata. An optional user JSON file is read
at application startup or explicit reload, and valid unique-ID entries are
merged with the built-in catalog. Reload replaces the previous user-model
snapshot; invalid files leave built-ins available and expose warnings. These
endpoints do not inspect installed Ollama models, call Hugging Face, download
models, run benchmarks, or change active runtime configuration.

## Workspace Lifecycle And Home

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `POST /workspaces` | Create a workspace. | Workspace and timeline | No | No | Create workspace |
| `GET /workspaces` | List all workspaces, including archived workspaces. | No | No | No | Compatibility/list view |
| `GET /workspaces/overview` | Return lightweight home-screen workspace state; archived workspaces are optional. | No | No | No | App home |
| `GET /workspaces/{workspace_id}` | Get workspace metadata. | No | No | No | Workspace settings |
| `PATCH /workspaces/{workspace_id}` | Update name, assistant mode, or privacy mode. | Workspace and timeline | No | No | Workspace settings |
| `POST /workspaces/{workspace_id}/archive` | Reversibly archive a workspace. | Workspace and timeline | No | No | App home/settings |
| `POST /workspaces/{workspace_id}/restore` | Restore an archived workspace. | Workspace and timeline | No | No | Archived workspaces |
| `DELETE /workspaces/{workspace_id}` | Permanently delete a workspace and all of its app-owned data (index, conversations, notes, scan, metadata). Project files on disk are never touched. | Workspace and all per-workspace tables, vector store | No | No | App home/settings |
| `GET /workspaces/{workspace_id}/storage` | Report the approximate app storage used by a workspace, broken down by category (index, conversations, notes, scan, other). Pass `recompute=true` to refresh the cached value. | Storage stats cache | No | No | Sidebar project size |
| `POST /workspaces/{workspace_id}/index/clear` | Clear the workspace search index (embeddings) to reclaim space and reset index status. Conversations and notes are kept. | Index status, vector store, timeline, storage stats cache | No | No | Sidebar project actions |
| `POST /workspaces/{workspace_id}/persistence` | Set whether a workspace is permanent (`saved`) or ephemeral (`temporary`). Used by the "Keep forever" action to promote a temporary project. | Workspace and timeline | No | No | Sidebar project actions |
| `POST /workspaces/temporary/purge` | Delete all temporary workspaces and their app-owned data. Triggered when the user confirms, on quit, that ephemeral projects should be forgotten. Project files on disk are never touched. | Workspaces and all per-workspace tables, vector store | No | No | Quit confirmation |

## Workspace Dashboard And Setup

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /workspaces/{workspace_id}/summary` | Return workspace, scan, index, command, and recent activity summary. | No | No | No | Workspace overview |
| `GET /workspaces/{workspace_id}/readiness` | Derive capabilities and setup readiness from persisted state and provider names. | No | No | No | Workspace overview |
| `GET /workspaces/{workspace_id}/quick-start` | Return current setup stage and next action. | No | No | No | Continue setup |
| `GET /workspaces/{workspace_id}/dashboard` | Aggregate summary, readiness, quick start, recommendation, activity, runtime health, and compact models summary. | No | No | Lightweight Qdrant/Ollama checks when configured | Main workspace |
| `GET /workspaces/{workspace_id}/ui-actions` | Return deterministic frontend action metadata derived from Quick Start, readiness, and compact model status. | No | No | No | Workspace navigation/actions |
| `GET /workspaces/{workspace_id}/local-ai/activation-guide` | Return deterministic commands and ordered guidance for activating the workspace's selected local AI models. | No | No | No | Local AI setup |

## Scanning, Indexing, And RAG

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `POST /projects/scan` | Deterministically scan an arbitrary local project path. | No | No | Local filesystem read | Project inspection |
| `POST /workspaces/{workspace_id}/scan` | Scan the workspace project and persist the latest result. | Scan and timeline | No | Local filesystem read | Workspace setup |
| `GET /workspaces/{workspace_id}/scan` | Get the latest persisted scan. | No | No | No | Detected skills/files |
| `GET /workspaces/{workspace_id}/scan/changes` | Read-only detection of whether on-disk project files changed (added/removed/modified by size or mtime) since the last saved scan, so the UI can offer to re-scan/re-index. Never re-scans, persists, or indexes. | No | No | Local filesystem read | Re-scan prompt |
| `POST /workspaces/{workspace_id}/index` | Chunk scanned files, embed them, and update the active vector store. | Index status, vector store, timeline | No | Filesystem plus configured embedding/vector providers | Workspace setup |
| `GET /workspaces/{workspace_id}/index/status` | Get persistent index-status metadata. | No | No | No | Workspace setup |
| `GET /workspaces/{workspace_id}/context/search` | Search active indexed context. | No | No | Configured embedding/vector providers | Context inspector |
| `POST /workspaces/{workspace_id}/files/preview` | Preview which local project files would be included or excluded by file-selection rules before scanning/indexing. | No | No | Local filesystem read | Workspace setup |
| `POST /workspaces/{workspace_id}/files/write` | Create or explicitly overwrite one reviewed UTF-8 text file inside the workspace project path; absolute paths and path traversal are rejected. | Project file and timeline | No | Local filesystem write after explicit user confirmation | Ask answer file draft |
| `POST /workspaces/{workspace_id}/jobs/scan` | Queue an async project scan job that can be polled and cancellation-requested. | Job memory plus scan/timeline when completed | No | Local filesystem read | Workspace setup |
| `POST /workspaces/{workspace_id}/jobs/index` | Queue an async search-context build job that can be polled and cancellation-requested. | Job memory plus index/vector/timeline when completed | No | Filesystem plus configured embedding/vector providers | Workspace setup |
| `GET /workspaces/{workspace_id}/jobs` | List newest async scan/index jobs for the workspace, including progress, duration, request summary, result summary, and applied file-rule metadata. | No | No | No | Workspace setup / Activity |
| `GET /workspaces/{workspace_id}/jobs/{job_id}` | Poll one async workspace job status, message, progress, duration, request summary, result summary, or error. | No | No | No | Workspace setup / Activity |
| `POST /workspaces/{workspace_id}/jobs/{job_id}/cancel` | Request cancellation for a queued or running async workspace job; running jobs stop at safe checkpoints. | Job memory | No | No | Workspace setup |
| `POST /workspaces/{workspace_id}/ask` | Retrieve context, generate an answer, and return diagnostics and quality warnings; optional `llm_provider`/`llm_model` select a supported provider for this request only. | Timeline | No | Configured embedding/vector providers and selected/default LLM provider | Ask workspace |
| `POST /workspaces/{workspace_id}/ask-selected` | Ask using the persisted selected workspace LLM as a per-request override. | Timeline | No | Active embedding/vector providers and selected LLM provider | Ask workspace |
| `POST /workspaces/{workspace_id}/ask-selected/stream` | Same as `ask-selected` but streams the answer token-by-token as Server-Sent Events (`token`/`final`/`error`), then persists the final answer. | Timeline | No | Active embedding/vector providers and selected LLM provider | Ask workspace |
| `POST /workspaces/{workspace_id}/understanding` | Generate a grounded, plain-language project understanding (summary plus cited risks) over the RAG index using the workspace's selected LLM, then cache it; reports which model produced it. Requires the workspace to be indexed and a selected LLM. | Project understanding cache | No | Active embedding/vector providers and selected LLM provider | Project understanding |
| `GET /workspaces/{workspace_id}/understanding` | Return the cached project understanding for a workspace if present (404 otherwise), including `is_stale` when the currently selected LLM differs from the stored model. | No | No | No | Project understanding |
| `GET /workspaces/{workspace_id}/git-insights` | Read-only snapshot of the project's git history (last commit, total and 30-day commit counts, contributors, project age, and 90-day most-changed files). Returns `is_repo: false` when the folder is not a git repository or git is unavailable; never modifies the repository. | No | No | Local `git` (read-only) | Home project activity |
| `GET /workspaces/{workspace_id}/todos` | Deterministic inventory of TODO/FIXME/HACK/XXX/BUG markers read verbatim from project files (respecting the same selection rules and `.gitignore` as scanning). Nothing is generated by a model or persisted. | No | No | Local filesystem read | Home TODOs card |
| `GET /workspaces/{workspace_id}/model-experiments` | List newest persisted model experiment runs for a workspace. | No | No | No | Model experiments |
| `GET /workspaces/{workspace_id}/model-performance` | Aggregate saved experiment outcomes and manual ratings into deterministic model performance signals. | No | No | No | Model experiments/model selection |
| `POST /workspaces/{workspace_id}/models/recommend` | Rank catalog models using static metadata plus historical workspace experiment and rating signals. | No | No | No | Model selection |
| `POST /workspaces/{workspace_id}/models/explain` | Explain catalog fit, workspace history, switching impact, risks, and next actions for a model. | No | No | No | Model selection |
| `GET /workspaces/{workspace_id}/models/setup-guide` | Return beginner-friendly local model setup guidance with recommended defaults, dropdown options, custom-model hints, packaging notes, and safety notes. | No | No | No | Model setup |
| `GET /workspaces/{workspace_id}/models/selection` | Get persisted workspace LLM and embedding-model preference state plus runtime-configuration match notes. | No | No | No | Model selection |
| `PUT /workspaces/{workspace_id}/models/selection` | Persist one workspace model preference while preserving the other model type. | Selection and timeline | No | No | Model selection |
| `GET /workspaces/{workspace_id}/models/selection/status` | Compare selected models with active configuration and index status, then return readiness and next actions. | No | No | No | Model selection/readiness |
| `GET /workspaces/{workspace_id}/models/usage-plan` | Explain whether selected models can be used for ask, index, and search, plus ordered next actions. | No | No | No | Model selection/readiness |
| `GET /workspaces/{workspace_id}/models/embedding-indexing-plan` | Explain active-runtime match, vector-collection impact, and indexing steps for the selected embedding. | No | No | No | Model selection/indexing |
| `GET /workspaces/{workspace_id}/models/dashboard` | Aggregate workspace model selection, readiness, usage, embedding-indexing guidance, recommendations, performance, and primary next action. | No | No | No | Workspace models |
| `GET /workspaces/{workspace_id}/models/dashboard/summary` | Return compact workspace model status, selected/active identities, embedding runtime/index state, top recommendation, warning count, and next action. | No | No | No | Workspace models status card |

## Reports And Deterministic Analysis

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /workspaces/{workspace_id}/reports/project-overview` | Generate a deterministic project overview report. | Timeline | No | Local filesystem read for analyzers | Reports |
| `GET /workspaces/{workspace_id}/reports/catalog` | List local-first report templates and safety notes. | None | No | None | Reports |
| `GET /workspaces/{workspace_id}/reports/{report_type}` | Generate a selected read-only workspace report draft with quality checks and source coverage metadata. | Timeline | No | Local filesystem read for analyzers and saved workspace context | Reports |
| `POST /workspaces/{workspace_id}/reports/custom-preview` | Build a custom read-only report draft from explicitly selected saved notes, conversations, source paths, and user drafting context, including quality checks. | None | No | None | Reports custom builder |
| `POST /workspaces/{workspace_id}/reports/custom-save` | Build and persist a custom read-only report from explicitly selected local workspace context. | Saved report | No | None | Reports custom builder |
| `POST /workspaces/{workspace_id}/reports/draft-save` | Persist an explicitly edited report draft with selected sections, documentation-ready markdown, and quality metadata. | Saved report | No | None | Reports editor |
| `POST /workspaces/{workspace_id}/reports/{report_type}/save` | Generate and persist a selected workspace report as local report history. | Saved report | No | Local filesystem read for analyzers and saved workspace context | Reports |
| `GET /workspaces/{workspace_id}/reports/saved` | List saved reports with search/type/pinned filters. | None | No | None | Reports history |
| `GET /workspaces/{workspace_id}/reports/saved/{report_id}` | Read one saved report including markdown/text/json exports, quality checks, and source coverage metadata. | None | No | None | Reports history |
| `PATCH /workspaces/{workspace_id}/reports/saved/{report_id}` | Rename or update saved report metadata. | Saved report | No | None | Reports history |
| `PATCH /workspaces/{workspace_id}/reports/saved/{report_id}/pin` | Pin or unpin a saved report. | Saved report | No | None | Reports history |
| `DELETE /workspaces/{workspace_id}/reports/saved/{report_id}` | Delete a saved report from local workspace history. | Saved report | No | None | Reports history |
| `GET /workspaces/{workspace_id}/analysis/summary` | Aggregate relevant deterministic analyzer findings. | No | No | Local filesystem read | Analysis overview |
| `GET /workspaces/{workspace_id}/analysis/terraform` | Analyze Terraform structure using static text rules. | No | No | Local filesystem read | Terraform analysis |
| `GET /workspaces/{workspace_id}/analysis/terragrunt` | Analyze Terragrunt structure using static text rules. | No | No | Local filesystem read | Terragrunt analysis |
| `GET /workspaces/{workspace_id}/analysis/gitlab-ci` | Analyze GitLab CI YAML. | No | No | Local filesystem read | CI/CD analysis |
| `GET /workspaces/{workspace_id}/analysis/github-actions` | Analyze GitHub Actions YAML. | No | No | Local filesystem read | CI/CD analysis |
| `POST /workspaces/{workspace_id}/intelligence/build` | Build the Project Intelligence graph from deterministic analyzers (explicit action). | No | No | Local filesystem read | Project Intelligence |
| `GET /workspaces/{workspace_id}/intelligence` | Latest project graph projected through the role lens. | No | No | Local DB read | Project Intelligence |
| `GET /workspaces/{workspace_id}/intelligence/overview-text` | Optional LLM overview written only from the graph facts. | No | No | Local model | Project Intelligence |

## Command Approval

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /workspaces/{workspace_id}/commands` | List persisted command proposals and outcomes. | No | No | No | Command activity |
| `POST /workspaces/{workspace_id}/commands` | Create a pending proposal with risk and policy decisions. | Command and timeline | No | No | Command review |
| `GET /workspaces/{workspace_id}/commands/suggestions` | Return deterministic suggestion templates. | No | No | No | Command suggestions |
| `POST /commands/{command_id}/approve` | Approve a pending proposal. | Command and timeline | No | No | Command review |
| `POST /commands/{command_id}/reject` | Reject a pending proposal. | Command and timeline | No | No | Command review |
| `POST /commands/{command_id}/execute` | Execute only an approved, policy-allowed proposal. | Command and timeline | Yes, fake by default; local only when enabled | Configured command runner | Command review |

## Timeline

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /workspaces/{workspace_id}/timeline` | List newest workspace activity events. | No | No | No | Activity timeline |
| `POST /workspaces/{workspace_id}/timeline/backfill` | Create missing historical events from persisted workspace state. | Timeline only | No | No | Activity timeline |

## OpenAPI

FastAPI exposes interactive documentation at `/docs`, alternative documentation
at `/redoc`, and the OpenAPI contract at `/openapi.json`. Routers use coarse
tags for health, runtime, onboarding, projects, workspaces, assistant profiles,
models, and commands. This document provides the finer product-oriented grouping.

- `GET /workspaces/{workspace_id}/indexing-rules` — return saved or default workspace indexing rules.
- `PUT /workspaces/{workspace_id}/indexing-rules` — save workspace indexing rules for future preview, scan, and index actions.

### Workspace skill profile

- `GET /workspaces/{workspace_id}/skill-profile` — return the saved workspace skill profile, or safe default skill guidance if none is saved.
- `PUT /workspaces/{workspace_id}/skill-profile` — save active skills and custom instructions for the workspace. Ask uses the saved profile as guidance only; retrieved sources remain the basis for project claims.

### Workspace conversations

- `POST /workspaces/{workspace_id}/conversations` — create an explicit saved conversation for a workspace. No scan/index/rebuild is started.
- `GET /workspaces/{workspace_id}/conversations` — list saved workspace conversations with message counts, update times, and optional filters: `search`, `pinned_only`, `include_archived`.
- `GET /workspaces/{workspace_id}/conversations/{conversation_id}` — return one saved conversation with persisted user/assistant messages, restored source snapshots, and answer history metadata.
- `PATCH /workspaces/{workspace_id}/conversations/{conversation_id}` — rename one saved conversation. No scan/index/rebuild is started.
- `PATCH /workspaces/{workspace_id}/conversations/{conversation_id}/pin` — pin or unpin one saved conversation. This changes local conversation metadata only.
- `PATCH /workspaces/{workspace_id}/conversations/{conversation_id}/archive` — archive or restore one saved conversation without deleting its messages.
- `GET /workspaces/{workspace_id}/conversations/{conversation_id}/export` — export a saved conversation as markdown, text, or JSON content for local reuse, including captured source paths/previews where available. No network upload or shell execution.
- `GET /workspaces/{workspace_id}/conversations/{conversation_id}/context-preview` — prepare a reusable local context preview from one saved conversation, its notes, and captured source paths. This does not inject history into Ask automatically.
- `GET /workspaces/{workspace_id}/answer-notes` — list reusable answer notes saved from assistant messages, with optional search, pinned-only, and source-path filters.
- `POST /workspaces/{workspace_id}/conversations/{conversation_id}/messages/{message_id}/note` — save an assistant answer as a reusable local note with its source question and captured source paths.
- `PATCH /workspaces/{workspace_id}/answer-notes/{note_id}` — edit a reusable answer note title/content and optionally pin/unpin it.
- `PATCH /workspaces/{workspace_id}/answer-notes/{note_id}/pin` — pin or unpin a reusable answer note.
- `DELETE /workspaces/{workspace_id}/answer-notes/{note_id}` — delete a reusable answer note.
- `DELETE /workspaces/{workspace_id}/conversations/{conversation_id}` — delete one saved conversation and its messages.

### MCP server registry

- `GET /mcp/catalog` — list safe MCP server templates, risk levels, setup notes, and recommended setup flow. No server is started.
- `POST /mcp/config-preview` — generate a disabled-by-default local MCP config preview for a selected template. Copy-only; no filesystem writes and no process start.
- `POST /mcp/connection-check` — return a manual connection test plan and copyable commands for a selected MCP template. Copy-only; no tool execution.
- `GET /mcp/workspaces/{workspace_id}/configs` — list workspace-saved MCP server configs, review status, approved tools, and guardrails. No server is started.
- `POST /mcp/workspaces/{workspace_id}/configs` — save a disabled-by-default MCP config for a workspace from a catalog template. No tool execution.
- `PATCH /mcp/workspaces/{workspace_id}/configs/{config_id}` — enable/disable or review an MCP config and store approved/denied tool lists. No tool execution.
- `DELETE /mcp/workspaces/{workspace_id}/configs/{config_id}` — remove a saved workspace MCP config.
- `GET /mcp/workspaces/{workspace_id}/tool-inventory` — summarize enabled MCP configs and approved tools visible to future agent planning. No tool execution.
- `POST /mcp/workspaces/{workspace_id}/configs/{config_id}/approval-preview` — preview which tools would be approved/denied for one MCP config before saving review state.

## Task 202 — local model install guide

- `GET /models/local-install-guide`
- `GET /models/ollama-recommendations`
  - Returns a manual, copy-only local model install plan.
  - Does not download models.
  - Does not execute shell commands.
  - Intended as the safe foundation for a future desktop-packaged model download manager.

## Task 203 — local model install draft approval

- `POST /models/local-install-drafts`
  - Creates a reviewable manual-only download draft for an Ollama model.
  - Records user intent as a pending command proposal.
  - Does not download the model.
  - Does not execute shell commands from the frontend or backend.
  - Marks the draft as `manual_only` so it is not auto-executable by the command policy.

## Task 204 — controlled backend model download worker design

- `GET /models/local-download-worker-plan`
  - Returns the backend-only worker design for future approved Ollama downloads.
  - Makes the current execution state explicit with `worker_enabled=false`.
  - Documents guardrails: no frontend shell, catalog allowlist, exact backend-generated commands, observable status, and no hidden index rebuilds.
  - Does not download models or execute shell commands.

## Task 205 — installed model detection

- `GET /models/local-install-status`
  - Read-only Ollama model detection via `/api/tags`.
- `GET /models/runtime-memory`
  - Read-only memory footprint of currently loaded local models via Ollama `/api/ps`, plus total physical RAM.
  - Returns recommended model status: `installed`, `missing`, or `unknown`.
  - Does not pull, delete, rebuild, execute MCP tools, or run frontend shell commands.

- `POST /models/local-install/delete`
  - Remove a locally installed Ollama model via `/api/delete` to reclaim disk space.
  - Gated behind the model-management execution flag; never touches project files.

## Task 206 — approved model download execution foundation

- `GET /models/local-download-execution-capability`
  - Returns whether backend model download execution is enabled for the current runtime.
  - Disabled by default unless the trusted local desktop runtime sets `MODEL_DOWNLOAD_EXECUTION_ENABLED=true` and `COMMAND_RUNNER=local`.
  - Documents the safety requirements before any executable model download flow is shown.

- `POST /models/local-install-drafts/{command_id}/run`
  - Runs one approved model download draft through the backend worker only when execution is explicitly enabled.
  - Accepts only exact `ollama pull <catalog-model-name>` commands generated from the local model catalog.
  - Does not allow arbitrary shell text, frontend shell execution, MCP execution, scan/index/rebuild, or automatic embedding reindexing.

## Task 207 update

Added model download job foundation endpoints: `POST /models/local-install-drafts/{command_id}/jobs` and `GET /models/local-download-jobs/{job_id}`. Jobs are backend-owned status records for approved Ollama downloads. The frontend can start and refresh a job, but still never runs shell commands. Execution remains opt-in and allowlisted.


### Background model download worker

- `POST /models/local-install-drafts/{command_id}/jobs` starts a backend-owned background model download job and returns `202 Accepted` quickly.
- `GET /models/local-download-jobs/{job_id}` reads queued/running/succeeded/failed status for polling UI.

## Task 210 — model download jobs history and cancel-safe semantics

- `GET /models/local-download-jobs` — list local model download jobs, newest first.
- `GET /models/local-download-jobs?workspace_id=<workspace-id>` — list download jobs for one workspace.
- `POST /models/local-download-jobs/{job_id}/cancel` — request cancel using safe semantics.

Cancel semantics are intentionally conservative: queued jobs can become `cancelled`; running jobs record a cancel request and finish safely instead of force-killing Ollama.


## Task 214 — Desktop packaging design lock


## Task 215 — macOS app package foundation


## Task 218 — backend runtime bundle readiness


## Task 220 — Tauri supervisor bridge





### Release candidate audit


## Task 223 — v0.1 demo and GitHub handoff





## Task 242 runtime endpoint



## Task 244 runtime endpoint


## Task 245 runtime endpoint


## Task 247 runtime endpoint



## Task 248 — app-owned backend startup implementation

- Tauri now has narrow commands to report, start, and stop only the app-owned frozen backend runtime.
- Startup is gated by the frozen backend manifest; missing manifest means blocked startup, not arbitrary fallback.
- Shutdown is PID-owned and no kill-by-port/generic shell execution is allowed.


## Task 250 — Tauri backend health readiness


## Task 251 — macOS packaged app smoke preflight





## Task 255 — Tauri icon assets


## Task 256 — Tauri dev smoke readiness


## Task 257 — Tauri packaged app build readiness


## Task 258 — frozen backend startup diagnostics




## Task 261 note

`/runtime/packaged-app-frontend-bootstrap` now also verifies the packaged Tauri global invoke bridge (`withGlobalTauri`) and the npm install-script allowlist policy for `esbuild` and `fsevents`.
