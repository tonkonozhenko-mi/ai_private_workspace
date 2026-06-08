# Architecture

Private Project AI Workbench uses a small Ports and Adapters architecture. The
core describes application behavior, while FastAPI, SQLite, the filesystem,
Qdrant, Ollama, and subprocess execution remain replaceable edge concerns.

## Dependency Direction

```text
FastAPI routes and composition
        |
        v
application use cases --> core ports <-- adapters
        |
        v
domain models and deterministic rules
```

Dependencies point inward:

- `core/domain` contains dataclasses, registries, classifiers, prompt building,
  deterministic analyzers, and other business rules.
- `core/use_cases` coordinates domain behavior through ports. It does not
  import FastAPI, SQLite, or concrete adapters.
- `core/ports` defines protocols for repositories, filesystem access, vector
  storage, embeddings, LLM generation, command execution, and runtime health.
- `adapters` implement those ports using local or optional runtime technology.
- `api/routes` translates HTTP requests into use-case inputs and domain errors
  into HTTP responses.
- `api/schemas` contains Pydantic request/response models and domain-to-API
  conversion helpers.
- `api/dependencies.py` is the composition root that selects concrete adapters
  from settings and supplies them to routes.

## Core Domain

The domain is intentionally framework-neutral. Major areas include:

- Workspace lifecycle, overview, summary, readiness, quick start, dashboard,
  assistant profiles, onboarding, and runtime setup guidance.
- Deterministic project scanning and the data-driven Skill Registry.
- Terraform, Terragrunt, GitLab CI, and GitHub Actions static analysis.
- Index chunks, index status, RAG prompts, diagnostics, and answer warnings.
- Command proposals, risk classification, execution policy, and suggestions.
- Persistent timeline events and deterministic timeline backfill.
- Static local model metadata and deterministic model recommendation scoring.

Domain models are separate from API schemas so HTTP representation changes do
not become core dependencies.

### Local Model Catalog

The local model catalog is a core-owned static registry. It describes a small
initial set of fake and Ollama LLM/embedding models using honest, nullable
metadata and recommends them with deterministic scoring based on requested model
type, assistant profile, laptop profile, local-only suitability, quality tier,
and low-power speed.

The optional user-catalog adapter implements a core loader port and parses and
validates a configured JSON file, returning valid domain models plus warning
objects. The shared in-memory core registry merges valid user models, skips
duplicate IDs, exposes warnings separately from the backward-compatible catalog
list, and can replace its user-model snapshot on explicit reload. Catalog
listing, reload, and recommendation do not call Ollama or Hugging Face, inspect
installed models, download artifacts, run benchmarks, or update runtime
settings. Future adapters can enrich the catalog with installed model metadata
or evaluation results without moving recommendation logic into API routes.

The deterministic Model Switching Plan reads the same current catalog and can
optionally validate a workspace and inspect its persisted index-status metadata.
It explains whether a proposed LLM or embedding-model change requires a backend
restart, reindex, or new dimension-aware vector collection. The use case is
advisory only: it does not change settings, call providers, download models, or
mutate workspace/index state.

## Use Cases And Ports

Use cases are the application orchestration layer. They load domain state
through repository ports, call provider ports when required, apply deterministic
rules, and persist results through ports.

Repository ports cover workspaces, scans, index status, commands, and timeline
events. Provider ports cover:

- `FileSystemPort`: safe local project listing and text reads.
- `VectorStorePort`: workspace-scoped chunk upsert, search, and clear.
- `EmbeddingProviderPort`: text-to-vector conversion plus provider metadata.
- `LLMProviderPort`: prompt generation plus provider metadata.
- `LLMProviderFactoryPort`: configured-default or supported per-request LLM
  provider/model selection without changing runtime settings.
- `CommandRunnerPort`: approved command execution.
- `RuntimeHealthCheckerPort`: lightweight configured-component checks.

This makes in-memory test doubles and optional local runtime integrations
interchangeable without changing use cases.

## Adapters

### Persistence

SQLite adapters live under `adapters/memory` alongside in-memory repository
implementations. SQLite is the default for workspace state; in-memory
repositories remain useful for focused unit tests.

The SQLite schema stores:

- workspace metadata and archive state
- latest project scan JSON
- command proposals, policy decisions, and execution results
- index-status metadata
- timeline events and metadata JSON
- model experiment runs and per-candidate result JSON
- append-only user ratings for model experiment candidates
- workspace-selected LLM and embedding-model preference metadata

Schema initialization uses `CREATE TABLE IF NOT EXISTS` and small compatible
column migrations. SQL does not appear in core or API routes.

### Filesystem And Deterministic Analysis

`LocalFileSystem` recursively scans project paths, skips generated/dependency
directories and oversized files, detects file types, and safely reads files
inside the project root. Static analyzers consume this capability through
`FileSystemPort`; they do not execute Terraform, Terragrunt, GitLab, or GitHub
workflows.

### Vector, Embedding, And LLM Providers

The default development path is fully local and dependency-light:

- in-memory vector store
- fake deterministic embeddings
- fake deterministic LLM

Optional adapters provide Qdrant vector persistence and Ollama embeddings or
generation. Qdrant collections are derived from collection base name, embedding
provider/model, and vector dimension to avoid incompatible reuse. Core code
knows only the provider ports. The LLM provider factory creates the configured
default provider or a supported `fake`/`ollama` per-request override; provider
selection remains in adapters rather than RAG use cases or API routes.
Fake-provider model overrides preserve the requested model label for deterministic
testing and experiment comparisons while keeping generated fake-answer behavior
unchanged.

### Runtime Health

Dedicated health adapters perform short, lightweight checks only when Qdrant or
Ollama is selected. The command-runner checker reports mode without executing a
command. Runtime health is advisory: unavailable optional providers degrade
health responses rather than preventing the default app from starting.

## Command Safety

Command handling is deliberately layered:

1. Suggestions are templates only and create no proposal.
2. A proposal records the command, working directory, reason, risk, and policy.
3. The user must explicitly approve or reject the proposal.
4. Execution requires both approved status and `auto_executable` policy mode.
5. Destructive and compound-shell commands are blocked; write and unknown-risk
   commands are manual-only.
6. `FakeCommandRunner` is the default.
7. `LocalCommandRunner`, when explicitly enabled, uses `shell=False`, enforces a
   timeout and output limit, and restricts `cwd` to the workspace project path.

API routes do not contain subprocess logic.

## Timeline And Read Models

Use cases append timeline events after meaningful mutations such as scans,
indexing, report generation, command activity, and workspace questions. SQLite
persists these events. Backfill reconstructs missing historical events from
already-persisted state without modifying scans, vectors, or commands.

Summary, readiness, quick start, dashboard, and workspaces overview are
deterministic read models built from the same repositories. They do not trigger
scan, index, or command execution.

## Model Experiments

Model experiment planning is advisory. Experiment execution is explicit and
requires an indexed workspace. `RunModelExperimentUseCase` embeds the question
and searches the active vector store once, builds one shared prompt, then uses
`LLMProviderFactoryPort` for each requested candidate. Candidate failures are
isolated, and completed, partial, or failed runs are persisted through
`ModelExperimentRepositoryPort` with a workspace timeline event.

This keeps comparisons fair: candidates receive identical retrieved context,
and no candidate triggers reindexing, model downloads, runtime-setting changes,
or shell commands.

Persisted experiment runs can also be summarized by a deterministic comparison
read model. The comparison use case reads a saved run, scores each candidate
from observable signals such as completion status, source count, quality-warning
count, answer length, and latency, then recommends the highest-scoring completed
candidate. This is intentionally not a semantic quality evaluator; it gives the
UI a concise, explainable comparison while leaving deeper AI-assisted
evaluation as future work.

Manual candidate ratings form a separate user-feedback loop. A rating use case
validates the saved experiment and candidate, then appends a rating record with
an optional preference, tags, and comment. Original experiment answers remain
immutable. Comparison summaries expose rating counts, averages, and preferred
votes, but user ratings do not yet alter deterministic comparison scores or
model recommendations.

The workspace-scoped Model Performance Summary is another read model over saved
experiment runs and ratings. It aggregates completion and failure counts,
latency, source and warning averages, rating averages, preferred votes, and
common feedback tags by provider/model. Its deterministic score is transparent
and advisory; reading performance never reruns experiments, calls providers, or
mutates experiment/rating data. Future rating-aware recommendations can consume
these signals through core use cases without moving aggregation into API routes.

Workspace-aware model recommendations now compose the existing static catalog
recommendation use case with the workspace performance read model. Catalog
scores remain visible, performance scores and explicit historical adjustments
are added separately, and models without workspace history retain their catalog
score with a warning. Fake/testing providers remain visible but receive an
explicit workspace-use penalty so historical test feedback cannot promote them
above similarly scored real local models. The resulting ranking is advisory and
read-only; it does not activate a model, change runtime settings, call
providers, or mutate feedback.

The Model Recommendation Explanation is a deterministic read model over those
same sources. It presents catalog fit, workspace history, switching impact,
risks, and suggested actions for both known and unknown models. Availability and
installation remain explicitly unverified because the explanation does not call
Ollama, Hugging Face, or any provider. LLM explanations state that reindexing is
not required; embedding explanations state that reindexing is required.

Workspace Model Selection is a separate persisted preference layer. Selecting an
LLM or embedding model preserves the other selection, records timeline activity,
and reports whether the preference matches active provider/model configuration.
Unknown catalog models remain selectable with a validation note. Replacing an
embedding preference adds a reindex warning, but selection never changes active
settings, restarts services, downloads models, calls providers, or triggers
reindexing.

Workspace Model Selection Status is a read-only readiness projection over
persisted selections, active configured provider/model names, and persisted
index status. It distinguishes missing selections, runtime mismatches, embedding
reindex requirements, and fully ready state, then returns deterministic next
actions. It does not inspect installed models, restart the backend, change
configuration, or trigger indexing.

Selected Model Usage Plan builds on that state while preserving an important
runtime distinction. Supported LLM selections can be passed to `/ask` as a
per-request provider/model override without changing the active backend
configuration. Embedding selections cannot be applied per request because
indexing and search must use the same active embedding provider, model, and
vector space. An embedding mismatch therefore requires an explicit runtime
change followed by reindexing before selected-model search is available.

Ask With Selected LLM is a thin orchestration use case over the existing
workspace question-answering flow. It validates the persisted selected LLM and
provider-factory support, then delegates retrieval, prompting, generation,
diagnostics, quality checks, and timeline recording to
`AskWorkspaceQuestionUseCase` with a per-request LLM override. Retrieval always
uses the active embedding and vector-store configuration. When a separately
selected embedding does not match that active configuration, the response adds
a deterministic warning rather than changing embeddings or reindexing.

Selected Embedding Indexing Plan is a read-only projection over the persisted
embedding selection, active embedding provider/model identity, and workspace
index status. A matching active embedding can index immediately and can search
once indexed. A mismatch represents a different vector space, so the plan marks
backend restart, a new vector collection, and reindexing as required actions.
The plan does not call providers, create collections, change configuration, or
run indexing.

Local AI Activation Guide turns persisted workspace model selections, active
configuration names, and index metadata into ordered setup instructions. It can
recommend starting Qdrant, starting or pulling Ollama models, restarting the
backend with selected provider/model environment variables, reindexing, and
asking with the selected LLM. These are command strings for the user only: the
guide performs no health checks, provider calls, downloads, configuration
changes, process restarts, or indexing.

Workspace Models Dashboard is a read-only aggregate over the existing model
selection, selection status, selected-model usage plan, selected-embedding
indexing plan, workspace-aware recommendations, and performance summary use
cases. It adds only a deterministic overall status and primary next model
action. Provider calls, indexing, selection changes, recommendations, and
performance scoring remain owned by their existing boundaries rather than being
reimplemented in the API route or dashboard.

Workspace Models Dashboard Summary is a compact projection built from the
detailed dashboard use case. It formats selected and active model identities,
exposes the top recommendation and primary next action, counts performance
models, and derives a warning total from recommendation warnings,
embedding-indexing warnings, and non-ready usage capabilities. The detailed
dashboard remains the source for full diagnostics and is unchanged.

The main Workspace Dashboard includes this compact Models summary as a nested
read model for its small Models card. It reuses
`GetWorkspaceModelsDashboardSummaryUseCase`; model selection, recommendation,
warning, and readiness logic are not duplicated in the main dashboard or API
route. The dedicated detailed and compact Models dashboard endpoints remain
unchanged.

## Testing Boundaries

Normal tests use fake providers, in-memory vector storage, temporary SQLite
databases, and mocked optional-runtime calls. Live Qdrant and Ollama contract
tests are opt-in through environment variables, so the standard suite remains
self-contained.
