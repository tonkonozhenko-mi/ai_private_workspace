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
[FRONTEND_API_MAP.md](FRONTEND_API_MAP.md), and
[CONFIGURATION.md](CONFIGURATION.md) for detailed references.

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

### Model Management And Experiments

- Static local model catalog and optional reloadable user JSON catalog through
  `USER_MODEL_CATALOG_PATH` and `POST /models/catalog/reload`.
- Deterministic model recommendations by assistant profile, laptop profile,
  task, model type, and workspace performance history.
- Workspace-aware recommendation explanations and switching plans.
- Persistent model experiment runs, comparison summaries, and manual candidate
  ratings.
- Workspace model selection state for LLM and embedding preferences.
- Read-only selection status, usage plan, embedding indexing plan, models
  dashboard, and dashboard summary.
- `POST /workspaces/{workspace_id}/ask-selected` for asking with the persisted
  selected LLM without changing runtime configuration.

### Frontend Workbench

- Vite, React, and TypeScript frontend in `frontend/`.
- Dark workspace sidebar with workspace status, assistant mode, index state,
  skill count, and next action.
- Overview, Ask, Models, Actions, and Activity tabs.
- Overview cards for project status, index status, quick start, activity, local
  model status, and primary next action.
- Ask tab with manual submit, example questions, non-blocking project-question
  guidance, local session history, answer diagnostics, quality warnings, and
  source inspection.
- Models tab with selected/active runtime, readiness, recommendations,
  performance history, and copy-only local activation guide.
- Actions tab with read-only UI action catalog and endpoint inspection.
- Activity tab backed by persistent timeline data.
- Unified status badges, loading/error/empty states, polished layout, safe text
  wrapping, and responsive behavior.

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
- Fake command runner remains the safe default.

The verified runtime target is:

- `VECTOR_STORE=qdrant`
- `EMBEDDING_PROVIDER=ollama`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`
- `LLM_PROVIDER=ollama`
- `OLLAMA_LLM_MODEL=llama3.2`

This real local AI happy path has been manually verified end to end: runtime
health reported Qdrant and Ollama as configured and healthy, the workspace was
reindexed into Qdrant, model selection status became `ready`, `ask-selected`
returned an Ollama answer with relevant sources, the frontend Overview showed
Local AI status `Ready`, Ask showed `ollama/llama3.2`, and Activity recorded
Ollama-backed workspace question events.

Qdrant and Ollama remain optional. No cloud API is required for the current
backend MVP. See [CONFIGURATION.md](CONFIGURATION.md#real-local-ai-runtime)
for exact startup, verification, and troubleshooting commands.

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

**Frontend Polish And Real Local AI Happy Path**

The frontend MVP has been expanded and polished into a usable local workbench:
workspace sidebar, Overview, Ask, Models, Actions, and Activity tabs are in
place with consistent badges, shared state components, safe copy-only setup
instructions, local Ask session history, source inspection, and responsive
visual cleanup.

The real local AI happy path has also been verified with Qdrant, Ollama
embeddings, Ollama LLM generation, workspace reindexing, selected model
readiness, real `ask-selected` answers, source-grounded responses, and frontend
confirmation.

## Recommended Next Task

**Documented Runtime And Model Selection UX**

The immediate follow-up is to keep the verified real local runtime documented
and then improve the frontend model-selection editing flow. Future UI work
should continue to be explicit and safe: copy commands or explain actions, but
do not start runtimes, download models, reindex, or execute commands without a
separate deliberate design.

See [NEXT_STEPS.md](NEXT_STEPS.md) for the expected behavior and safety rules.

## Native UX Design Direction

A new Apple-style design-system foundation has been started for Phase 8. The
frontend now has shared CSS tokens for typography, spacing, radius, color,
shadows, focus rings, sidebar surfaces, and semantic states. This is intended
to move the UI from a developer-dashboard feel toward a calmer native workbench
experience while preserving the current safe behavior and local-first runtime
model.

The next UX work should avoid a full rewrite. Continue with small visual and
interaction tasks: app shell refinement, Models tab simplification, Ask tab
conversation layout, and progressive disclosure for advanced runtime and
experiment details.

## Task 106 App Shell Refinement

Phase 8 continued with an app-shell refinement. The workspace tabs now use a
segmented-control style inside a translucent navigation shell, the current
workspace is shown as contextual chrome, and the sidebar/workspace cards were
softened to feel less like a dense developer dashboard. The Overview header was
also restyled as a calmer workspace hero surface.

This task was visual-only. It did not change backend behavior, API calls,
workspace selection logic, model selection, Ask, scan/index/reindex, or
experiment flows.

## Frontend UX roadmap update — Task 107

Phase 8 native-feeling UX work continued with a Models tab simplification pass. The Models tab now has a guided hero, workflow steps, a compact insights grid, and a collapsible advanced activation guide. This is a layout/progressive-disclosure change only; existing model selection, Ask, experiment planning, experiment run, ratings, and history behavior remain unchanged.

## Frontend UX roadmap update — Task 108

Phase 8 continued with an Ask tab conversational redesign. The Ask screen is now positioned as a local workspace conversation: a guided composer, local-only safety copy, native answer card, source verification panel, and calmer verification notes. Existing behavior remains unchanged: Ask is still manual-submit only, sources/diagnostics/session history are preserved, and scan/index/reindex instructions remain copy-only.

### Ask source progressive disclosure

The Ask screen now keeps verification context visible without overwhelming the conversation: top sources appear first, previews are individually expandable, and additional sources are hidden behind an explicit Show all sources control.

## Frontend Task 110 — Actions Tab Native Simplification

Phase 8 Apple-style UX work continued with a native-feeling Actions tab pass.
The UI action catalog now reads less like an API table and more like a workspace
control inspector: grouped action cards, safety-first inspector copy, and raw API
details hidden behind progressive disclosure. No API behavior changed.

## Frontend Task 111 — Activity Native Timeline Redesign

Phase 8 Apple-style UX work continued with a native-feeling Activity tab pass.
The backend timeline is still read-only, but the UI now groups events by day,
shows compact activity summaries, uses calmer human-readable labels, and hides
raw metadata behind an explicit details disclosure. This keeps the Activity tab
useful for audits and demos without feeling like a low-level event log.

No behavior changed: the Activity tab does not replay events, execute commands,
run scan/index/reindex, mutate workspace state, or change runtime settings.

## Frontend Task 112 — Overview Product Status Section

Phase 8 Apple-style UX work continued with a Product Status section on the
Overview tab. The section summarizes workspace readiness across Local AI,
indexed context, model learning/experiment feedback, and safety posture. It is
intended for demos and day-to-day orientation so users can quickly see whether a
workspace is ready for Ask, whether indexed context exists, and what the next
recommended action is.

This change is read-only and uses data already loaded for the Overview screen.
No backend behavior changed, no API calls were added, and the frontend still does
not execute shell commands, run scan/index/reindex automatically, call models, or
change runtime settings from this section.


### Phase 8 UX Cleanup

The native-feeling UX pass now includes final wording and visual cleanup. Action
mutation labels are less alarming, Ask source previews are compact, and advanced
API details stay hidden until explicitly expanded.

## Frontend Task 114 — UX Wording Simplification

Phase 9 beginner-friendly UX work has started with a wording pass. The frontend
now prefers user-facing labels such as chosen AI model, chosen search model,
context ready, technologies found, rebuild search context, and workspace
capabilities instead of more internal terms like selected LLM, embedding,
index/reindex, or API catalog. The goal is to preserve technical accuracy while
making the app easier to understand for users who are not already familiar with
LLM/RAG terminology.

This was a wording and UI-copy change only. No backend behavior, API calls,
model calls, runtime settings, scan/index execution, or experiment behavior was
changed.
