# API Inventory

This inventory describes the current backend MVP surface. `Writes` means the
endpoint persists or updates application data. `Runtime` identifies local
filesystem, provider, or command-runner activity outside SQLite repositories.

## Health And Runtime

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /health` | Process liveness check. | No | No | No | App shell |
| `GET /runtime/health` | Report configured Qdrant, Ollama, and command-runner health. | No | No | Lightweight Qdrant/Ollama checks when configured | Runtime status |
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
| `GET /models/catalog/details` | List filtered models plus user-catalog loading and validation warnings. | No | No | No | Model catalog diagnostics |
| `POST /models/catalog/reload` | Reload the configured user model file into the in-memory catalog. | In-memory catalog only | No | Local metadata file read | Model catalog settings |
| `POST /models/recommend` | Rank catalog models for an assistant profile, laptop profile, task, and model type. | No | No | No | Model selection/setup wizard |
| `POST /models/switching-plan` | Explain deterministic restart, reindex, and collection impact before switching a model. | No | No | No | Model selection/experiments |
| `POST /models/experiments/plan` | Plan a shared-context LLM comparison and enrich candidates with catalog/runtime guidance. | No | No | No | Model experiments |
| `POST /models/experiments/run` | Retrieve workspace context once, run explicitly requested LLM candidates, and persist comparison results. | Experiment and timeline | No | Configured embedding/vector providers plus explicitly selected LLM providers | Model experiments |
| `GET /models/experiments/{experiment_id}` | Get a persisted model experiment run and candidate results. | No | No | No | Model experiments |
| `GET /models/experiments/{experiment_id}/comparison` | Summarize a saved experiment run with deterministic candidate scores, warnings, and a recommended winner. | No | No | No | Model experiments |

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

## Workspace Dashboard And Setup

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /workspaces/{workspace_id}/summary` | Return workspace, scan, index, command, and recent activity summary. | No | No | No | Workspace overview |
| `GET /workspaces/{workspace_id}/readiness` | Derive capabilities and setup readiness from persisted state and provider names. | No | No | No | Workspace overview |
| `GET /workspaces/{workspace_id}/quick-start` | Return current setup stage and next action. | No | No | No | Continue setup |
| `GET /workspaces/{workspace_id}/dashboard` | Aggregate summary, readiness, quick start, recommendation, activity, and runtime health. | No | No | Lightweight Qdrant/Ollama checks when configured | Main workspace |

## Scanning, Indexing, And RAG

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `POST /projects/scan` | Deterministically scan an arbitrary local project path. | No | No | Local filesystem read | Project inspection |
| `POST /workspaces/{workspace_id}/scan` | Scan the workspace project and persist the latest result. | Scan and timeline | No | Local filesystem read | Workspace setup |
| `GET /workspaces/{workspace_id}/scan` | Get the latest persisted scan. | No | No | No | Detected skills/files |
| `POST /workspaces/{workspace_id}/index` | Chunk scanned files, embed them, and update the active vector store. | Index status, vector store, timeline | No | Filesystem plus configured embedding/vector providers | Workspace setup |
| `GET /workspaces/{workspace_id}/index/status` | Get persistent index-status metadata. | No | No | No | Workspace setup |
| `GET /workspaces/{workspace_id}/context/search` | Search active indexed context. | No | No | Configured embedding/vector providers | Context inspector |
| `POST /workspaces/{workspace_id}/ask` | Retrieve context, generate an answer, and return diagnostics and quality warnings; optional `llm_provider`/`llm_model` select a supported provider for this request only. | Timeline | No | Configured embedding/vector providers and selected/default LLM provider | Ask workspace |
| `GET /workspaces/{workspace_id}/model-experiments` | List newest persisted model experiment runs for a workspace. | No | No | No | Model experiments |

## Reports And Deterministic Analysis

| Endpoint | Purpose | Writes | Executes commands | Runtime | Main UI surface |
| --- | --- | --- | --- | --- | --- |
| `GET /workspaces/{workspace_id}/reports/project-overview` | Generate a deterministic project overview report. | Timeline | No | Local filesystem read for analyzers | Reports |
| `GET /workspaces/{workspace_id}/analysis/summary` | Aggregate relevant deterministic analyzer findings. | No | No | Local filesystem read | Analysis overview |
| `GET /workspaces/{workspace_id}/analysis/terraform` | Analyze Terraform structure using static text rules. | No | No | Local filesystem read | Terraform analysis |
| `GET /workspaces/{workspace_id}/analysis/terragrunt` | Analyze Terragrunt structure using static text rules. | No | No | Local filesystem read | Terragrunt analysis |
| `GET /workspaces/{workspace_id}/analysis/gitlab-ci` | Analyze GitLab CI YAML. | No | No | Local filesystem read | CI/CD analysis |
| `GET /workspaces/{workspace_id}/analysis/github-actions` | Analyze GitHub Actions YAML. | No | No | Local filesystem read | CI/CD analysis |

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
