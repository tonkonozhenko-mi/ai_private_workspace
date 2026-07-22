# Architecture

AI Private Workspace is a Tauri desktop shell over a FastAPI backend, built as
Ports and Adapters. The core describes application behavior; FastAPI, SQLite,
the filesystem, the local model engines (bundled llama.cpp and Ollama), and
subprocess execution remain replaceable edge concerns.

## Dependency Direction

```text
Tauri shell (supervises the packaged backend)
        |
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
  chunking, retrieval scoring, answer evaluation, deterministic analyzers, and
  other business rules.
- `core/use_cases` coordinates domain behavior through ports. It does not
  import FastAPI, SQLite, or concrete adapters.
- `core/ports` defines protocols for repositories, filesystem access, vector
  storage, embeddings, LLM generation, reranking, command execution, and
  runtime health.
- `adapters` implement those ports using local runtime technology.
- `api/routes` translates HTTP requests into use-case inputs and domain errors
  into HTTP responses; `api/schemas` holds the Pydantic boundary;
  `api/dependencies.py` is the composition root.

## Desktop shell and packaged runtime

The packaged app is a Tauri (Rust + React) shell that supervises a frozen
PyInstaller backend executable. Startup is gated by the frozen-runtime
manifest, readiness requires an application-level `/health` 200 (not just an
open port), shutdown is PID-owned (never kill-by-port), and supervisor/backend
logs live in the app-owned data directory. The frontend never executes shell
commands — it may only display and copy them. App launch never starts scans,
indexing, model downloads, or rebuilds; every expensive action is an explicit
user click. During backend startup the process raises its own file-descriptor
limit (`app/config/fd_limit.py`) so large indexing runs don't exhaust the
default macOS ceiling.

## Local engines

Two interchangeable engine adapters sit behind the same provider ports:

- **Built-in llama.cpp** — the app manages a bundled `llama-server` process
  (lifecycle, health, model loading) and a GGUF catalog with explicit,
  user-approved downloads from Hugging Face. It also unlocks JSON-Schema
  constrained output and the cross-encoder reranker.
- **Ollama** — the app points at an existing Ollama install; user-pulled
  models appear as detected installs. Thinking-capable models stream their
  reasoning in a separate field, which the provider re-wraps for the UI.

`SwitchableEmbeddingProvider` is a global delegate so the active embedding
backend can follow the workspace's persisted selection; index builds first
re-align the delegate with that selection and fail loudly (not silently
mis-embed) when the selected engine is down. Fake deterministic LLM/embedding
providers back the test suite.

## Persistence

SQLite is the default for all state — workspace metadata, scans, index status
and manifest, conversations, project memory, timeline, model preferences, and
the vector index itself (`SQLiteVectorStore`, the packaged default; in-memory
and optional Qdrant adapters implement the same port). Connections are opened
per operation with WAL journal mode, `synchronous=NORMAL`, and a busy timeout;
the PRAGMAs fail open on filesystems that reject them (network mounts).
Schema initialization uses `CREATE TABLE IF NOT EXISTS` plus small compatible
migrations; SQL never appears in core or API routes.

## Retrieval pipeline

Indexing is explicit and incremental (content-hash manifest). Documents are
chunked structure-aware (AST/brace/markdown-aware, ~1500 chars with overlap),
and each chunk is stored with a deterministic contextual header
(`[source: path › label · part i/n]`; json/yaml headers also list the chunk's
config keys so "how is X configured?" matches by key name). The header is for
search and display — the dense vector embeds the stripped content. The
project handbook (a deterministic digest of the project map) is indexed as a
pseudo-document so "what is this project about?" questions retrieve it.

A query is answered through: domain-synonym expansion (csp ↔
content-security-policy and ~25 infra pairs, add-only) → optional LLM query
rewrite (on by default only when the reranker is on) → dense + BM25 (SQLite
FTS5 over content *and* paths) → Reciprocal Rank Fusion → path/environment
boost → per-file caps → MMR diversity → optional cross-encoder rerank →
parent-document expansion (±1 neighbours, budget-aware). It degrades to
vector-only search if FTS is unavailable.

## Context budget

A local model has a fixed window — typically 8192 tokens on a laptop — and every
part of the prompt competes for it. The allocation is deliberately *not* a set of
per-category percentages, because a share reserved for project memory is spent
even when there is no memory to put in it, and on an 8k window that is expensive.

Only two things are reserved outright:

| Reserved | Tokens | Why |
| --- | ---: | --- |
| Answer headroom | 768 | The model must have room to write. Discovering it does not, mid-sentence, is a truncated answer. |
| Prompt scaffold | 900 | The fixed instructions and the per-chunk framing (`[n] source_path: …`). Constant regardless of the question. |

Everything else is **measured, not reserved**: the project memory and handbook
section, the conversation history, the question itself, and the role hint are
counted at their real size. Whatever remains of the window goes to the retrieved
chunks — with a floor of 600 characters, so a tiny window still gets *some*
context rather than none.

Two consequences worth knowing:

- **A bloated section silently eats the answer's evidence.** Measured live: a
  page of pasted standing instructions consumed 1,792 of 6,516 available tokens
  — 28% of the window — and the retrieved chunks arrived shortened. This is why
  `instruction_split` searches with the request rather than the whole message.
- **Token counts are script-aware.** A Latin-trained tokenizer spends roughly one
  token per 4 ASCII characters, but about one per 2 Cyrillic and one per CJK
  character. Budgeting Ukrainian at 4 chars/token meant spending double what the
  budget believed. The conversion back to a character budget uses the ratio
  measured on the text actually in play, and where the engine exposes a real
  tokenizer (llama.cpp `/tokenize`) that is preferred over the estimate.

When no engine could report its window at all, the fallback is 4096 — the
smallest any local model ships with, because under-estimating means sending less
than fits, while over-estimating is the overflow this module exists to prevent.

The numbers above are asserted against the constants in
`backend/app/core/domain/context_budget.py` by
`backend/tests/test_context_budget_is_documented.py`, so this table cannot
quietly drift away from the code.

## Answer honesty

Grounded answering is wrapped in deterministic honesty mechanisms:

- **Small-talk router** — `looks_general_chat()` sends obvious chit-chat
  straight to general conversation, with no retrieval and no project sources.
- **Calibrated abstention** — the relevance floor is calibrated per index
  against the embedding model's own similarity noise; the answering threshold
  sits a fixed margin below that floor. Below it, the app abstains honestly.
- **Small-project full-context** — when the whole index provably fits the
  model window, retrieval is skipped and every file is provided (citations
  intact), gated so general questions don't inherit fake relevance.
- **CRAG-lite corrective pass** — about to abstain on a project-looking
  question, or a finished answer carries hard grounding warnings: one bounded
  corrective retrieval (with a deliberately *different* rewrite prompt) and at
  most one regeneration, adopted only if grounding provably improves.
- **Deterministic evaluation** — every answer passes groundedness checks
  (uncited sources, terms absent from context, quote-not-in-sources with a
  how-to shell-example exemption) that surface as review warnings in the UI,
  never silent edits.
- **Structured citations (experimental, flagged)** — on engines with
  schema-constrained output, Deep-dive mode can request
  `{answer_md, citations:[{path, quote}]}`; parsing is fail-open.

## Project intelligence

A deterministic scanner recognizes what a folder contains (Terraform,
Kubernetes, CI, docs, application code …) and classifies the project by its
dominant type. On top of the map sit read-only tools: role lenses, CI/CD and
environment views, security review, git activity and per-file inspection,
self-maintaining project memory with guardrails, a dated change journal,
starter questions generated from map facts, and the **Investigator** — a
bounded ReAct loop over read-only tools. The loop is a single generator
consumed two ways: `execute()` returns the finished trace, and an SSE endpoint
streams each step live to the UI.

## Command safety

Unchanged and deliberate: suggestions are templates; proposals record command,
cwd, reason, risk, and policy; execution requires explicit approval plus an
auto-executable policy; destructive/compound commands are blocked;
`FakeCommandRunner` is the default and the real runner (opt-in) uses
`shell=False`, timeouts, output limits, and workspace-rooted cwd. API routes
contain no subprocess logic.

## Model management

A core-owned catalog (static + user JSON + detected installs) drives
deterministic, advisory model recommendations; workspace-scoped selections are
persisted preferences that never restart services or download anything by
themselves. Explicit model experiments run candidates against identical
retrieved context and are scored by transparent observable signals, with
append-only user ratings as a separate feedback loop. After a workspace reset
the engine returns to the recommended model rather than resurrecting the last
one that happened to be loaded.

## Evaluation

`backend/eval/` is a golden-set benchmark that runs the real retrieval path
(and optionally real generation through the full corrective pipeline) against
a labelled 40-question set: retrieval hit@k, wrongly-refused project questions
(overblock), correctly-refused off-topic questions, and grounding-warning rate
raw → after correction. Reports (JSON + Markdown, with the calibrated floor
and threshold) land in `build/notes/eval/`. Its deterministic classifiers are
pinned by fast CI tests; model runs are executed manually. The benchmark
excludes its own files from the corpus — a self-eval lesson learned twice.

## Testing boundaries

Normal tests use fake providers, in-memory or temporary-SQLite storage, and
mocked optional-runtime calls; live engine contract tests are opt-in through
environment variables. The suite (1,000+ tests) mirrors production limits —
including the raised file-descriptor ceiling — so tests fail the way the
packaged app would, not in artificial ways.
