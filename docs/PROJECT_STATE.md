# Project State

## Project

**Name:** Private Project AI Workbench  
**Current state snapshot:** June 8, 2026

Private Project AI Workbench is a local-first AI workbench for project
onboarding, DevOps, developer, documentation, support, and manager assistants.
It combines deterministic project inspection, local RAG, safe command approval,
and local model experimentation foundations while keeping private project data
under the user's control.

This document is the primary handoff reference for continuing work after a chat
session, context window, or contributor change.

## Architecture Summary

The current application is a Python 3.11+ FastAPI backend organized using Clean
Architecture and Ports and Adapters.

- `backend/app/core/domain`: framework-neutral domain models, registries,
  deterministic rules, analyzers, prompts, and policies.
- `backend/app/core/use_cases`: application orchestration through ports.
- `backend/app/core/ports`: interfaces for persistence, filesystem access,
  model catalog loading, vector storage, embeddings, LLMs, command execution,
  and runtime health.
- `backend/app/adapters`: SQLite, in-memory repositories, local filesystem,
  Qdrant, Ollama, command runners, runtime health checkers, and user model
  catalog loading.
- `backend/app/api/routes`: thin FastAPI HTTP routes.
- `backend/app/api/schemas`: Pydantic request/response models and domain
  conversion helpers.
- `backend/app/api/dependencies.py`: composition root selecting configured
  adapters and shared in-memory services.
- SQLite: default persistence for workspace state, scans, index status,
  commands, and timeline events.
- Qdrant: optional persistent vector-store adapter.
- Ollama embeddings: optional local embedding-provider adapter.
- Ollama LLM: optional local answer-generation adapter.

Core code must remain independent from FastAPI, SQLite, concrete adapters,
Qdrant clients, Ollama clients, and subprocess execution.

See [ARCHITECTURE.md](ARCHITECTURE.md), [API_INVENTORY.md](API_INVENTORY.md),
and [CONFIGURATION.md](CONFIGURATION.md) for detailed references.

## Current Major Capabilities

### Workspace And Onboarding

- Workspace creation, retrieval, listing, metadata updates, archive, and restore.
- Lightweight workspaces overview for the app home screen.
- Workspace summary, dashboard, readiness, and Quick Start read models.
- Runtime health and deterministic runtime setup guide.
- Assistant profiles and workspace assistant recommendations.
- Onboarding plan, setup-command instructions, and bootstrap workspace flow.

### Project Understanding

- Deterministic local project scanning.
- Data-driven Skill Registry.
- Terraform, Terragrunt, GitLab CI, and GitHub Actions analyzers.
- Deterministic analysis summary and project overview report.

### Command Safety

- Deterministic command suggestions.
- Persistent command proposal, approval, rejection, and audit workflow.
- Command risk classification and conservative execution policy.
- Fake command runner by default.
- Optional guarded local command runner using `shell=False`, policy approval,
  timeouts, output limits, and workspace-root restrictions.

### Local RAG

- Deterministic file chunking and workspace indexing.
- Persistent index-status metadata.
- In-memory vector store by default and optional Qdrant adapter.
- Fake embeddings by default and optional Ollama embeddings.
- Context search.
- Workspace question answering through fake or optional Ollama LLM providers.
- Source-grounded RAG prompts, no-context diagnostics, and deterministic answer
  quality warnings.

### Activity And Continuation

- Persistent workspace timeline.
- Timeline backfill for workspaces created before timeline support.
- Recent activity included in workspace read models.

### Model Management Foundation

- Static local model catalog.
- Deterministic model recommendations by assistant profile, laptop profile,
  task, and model type.
- Optional user-defined JSON model catalog through
  `USER_MODEL_CATALOG_PATH`.
- Validation warnings for malformed, invalid, missing, or duplicate user model
  metadata.
- Reloadable in-memory user model catalog through
  `POST /models/catalog/reload`.

## Current Runtime Modes

### Default Development Mode

- SQLite workspace persistence.
- In-memory vector store.
- Fake deterministic embeddings.
- Fake deterministic LLM.
- Fake command runner.

This mode is self-contained and used by the normal test suite.

### Real Local Mode

- Qdrant for persistent vector context.
- Ollama for local embeddings.
- Ollama for local LLM generation.
- Optional guarded local command runner.

Qdrant and Ollama remain optional. No cloud API is required for the current
backend MVP.

## Safety Principles

- Commands are never executed without explicit proposal approval and a
  policy-allowed decision.
- Destructive and compound-shell commands are blocked from automatic execution.
- Write and unknown-risk commands remain manual-only.
- Setup commands and onboarding commands are instructions only.
- Real command execution is disabled by default.
- No model downloads happen automatically.
- No active runtime settings are changed automatically.
- No cloud APIs are used by default.
- Project data and model workflows are designed to remain local-first.

## Latest Completed Task

**Workspace-Aware, Rating-Aware Model Recommendations**

The backend can now rank catalog models for a workspace using both static
catalog fit and persisted experiment/rating history. Catalog score, historical
performance score, final score, reasons, warnings, and historical signals
remain explicit and read-only.

## Recommended Next Task

**Recommendation Explanation And UI Model Selection State**

The next capability should make recommendation decisions and active model state
easy for the future UI to inspect without silently changing runtime settings.

See [NEXT_STEPS.md](NEXT_STEPS.md) for the expected behavior and safety rules.
