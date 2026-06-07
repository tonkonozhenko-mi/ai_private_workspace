# Roadmap

This roadmap describes the likely product sequence for Private Project AI
Workbench. It is directional rather than a release commitment. Safety,
local-first operation, clean architecture, and replaceable adapters should
remain stable constraints throughout every phase.

## Phase 1: Backend Foundation

**Status:** Mostly done

Delivered foundations include:

- FastAPI and Pydantic API boundary.
- Clean Architecture with domain, use cases, ports, and adapters.
- SQLite and in-memory persistence adapters.
- Workspace lifecycle and read models.
- Project scanner and Skill Registry.
- Deterministic DevOps analyzers and reports.
- Command approval, policy, fake runner, and guarded local runner.
- Timeline and timeline backfill.
- Onboarding, assistant profiles, runtime health, and setup guidance.
- Stabilized API inventory, architecture, and configuration documentation.

Remaining work in this phase should focus on maintenance, consistency, and
carefully scoped shared abstractions rather than new foundational rewrites.

## Phase 2: Local AI And RAG Foundation

**Status:** Partially done, working MVP

Delivered foundations include:

- Deterministic indexing and persistent index-status metadata.
- Context search.
- In-memory vector store and optional Qdrant.
- Fake embeddings and optional Ollama embeddings.
- Fake LLM and optional Ollama LLM.
- Source-grounded workspace question answering.
- RAG diagnostics and deterministic quality warnings.
- Embedding-dimension-aware Qdrant collections.

Likely future improvements:

- Better chunking and retrieval strategies.
- Retrieval diagnostics and index inspection.
- Explicit reindex planning and user confirmation.
- More deterministic answer-validation rules.
- RAG evaluation and experiment history.

## Phase 3: Model Management And Experiments

**Status:** In progress

Delivered foundations include:

- Static local model catalog.
- Deterministic model recommendations.
- User-defined JSON catalog loading and validation.
- Reloadable user model catalog.
- Deterministic model switching plans.

Next planned tasks:

1. Model Experiment Runs.
2. Compare answers across models.
3. Runtime model validation against installed Ollama models.
4. Hugging Face metadata importer.

This phase must keep model downloads, provider changes, reindexing, and runtime
configuration changes explicit and user-controlled.

## Phase 4: Frontend And UI Wizard

**Status:** Not started

Likely scope:

- Application home using Workspaces Overview.
- Workspace dashboard and Continue Workspace experience.
- Onboarding wizard for project, assistant, laptop, privacy, and runtime choices.
- Runtime setup and health views.
- Scan, detected-skill, analysis, report, and timeline views.
- RAG question interface with visible sources and quality warnings.
- Command suggestion, proposal, approval, and execution review.
- Model catalog, recommendation, switching-plan, and experiment views.

The frontend should use existing aggregate endpoints where possible and avoid
reimplementing deterministic backend decisions.

## Phase 5: Desktop Packaging And Installer

**Status:** Not started

Likely scope:

- Desktop launcher and process lifecycle management.
- Cross-platform installer or packaged distribution.
- Local data-directory selection.
- Guided Qdrant and Ollama setup.
- Safe environment configuration.
- Backup, restore, diagnostics, and update flows.

Packaging must preserve command approval, local-only defaults, and transparent
runtime configuration.

## Phase 6: Advanced Integrations

**Status:** Later

Possible future work:

- Additional deterministic analyzers and skill packs.
- User-defined skill and analyzer plugins.
- Git provider integrations with explicit permissions.
- Additional vector stores, embedding providers, and LLM providers.
- Hugging Face metadata and model discovery.
- Benchmark and evaluation suites.
- Shared team summaries or exportable project reports.
- Optional cloud integrations behind explicit configuration and consent.

Advanced integrations should remain optional and isolated behind ports and
adapters.
