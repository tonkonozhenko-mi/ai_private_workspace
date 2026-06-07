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
knows only the provider ports.

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

## Testing Boundaries

Normal tests use fake providers, in-memory vector storage, temporary SQLite
databases, and mocked optional-runtime calls. Live Qdrant and Ollama contract
tests are opt-in through environment variables, so the standard suite remains
self-contained.
