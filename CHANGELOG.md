# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Conversation memory in Ask (multi-turn, like ChatGPT/Claude).** Follow-up
  questions now keep their context — ask "what about ECS for cif in dev?" then
  "how do I disable it?" and the model knows "it" means ECS instead of losing the
  thread. On the llama.cpp engine the recent turns are sent as real role-tagged
  chat messages (`user`/`assistant`) ahead of the new question — the native format
  models are trained on — so both the answer and the project-vs-general routing
  stay on topic. Ollama gets the same memory via a compact history preface in its
  prompt. Best-effort and bounded (last few turns): a fresh chat or missing
  history changes nothing.

- **"Sharper search" reranker (opt-in).** A cross-encoder reranker precision pass:
  hybrid retrieval pulls a wider candidate set, a reranker model re-scores each
  (question, snippet) pair, and the best are kept — noticeably more relevant
  sources on tricky questions. A Settings toggle downloads a small reranker model
  (~370 MB) on first enable and runs it on the built-in llama.cpp engine
  (separate `llama-server --reranking` process). Fully gated and graceful: off by
  default, and if the model/engine isn't available Ask falls back to plain hybrid
  retrieval, so it can never break answering.

### Changed

- Stronger path/env signal in the answer prompt: it now leads with "answer from
  the project files and cite the source_path", and the model-identity note is a
  low-priority end clause — so small models stop replying to a project question
  with just their model name.

## [0.1.95] - 2026-06-18

Everything built on top of the initial `0.1.0` release candidate: a second local
engine (bundled llama.cpp), custom Hugging Face models, an adaptive project-aware
home, a much calmer Ask flow, honest answer metrics, a simpler Settings/Models
experience, faster startup, and signed per-architecture macOS builds.

### Added

- **Hybrid search (much more accurate retrieval).** The SQLite store now combines
  dense vector similarity with a BM25 keyword index (SQLite FTS5) and fuses the
  rankings with Reciprocal Rank Fusion. File and folder paths are indexed
  alongside the text, so exact identifiers — folder names like `dev`, variable
  names like `cif_allowed_cidr` — are matched lexically instead of being missed by
  pure semantic search. Two further signals sharpen results: a **path/env boost**
  (chunks whose file path segments match query terms like `dev` or `cif` are
  lifted, so environment-specific questions land on the right file) and a
  **per-file diversity cap** (one big file can't fill the whole answer). Falls
  back to vector-only if FTS5 is unavailable.
- **Built-in llama.cpp engine — fully Ollama-free path.** The app can bundle
  `llama-server` and run GGUF models with no external install: pick the engine at
  setup, auto-launch the runtime, switchable embeddings, and a live RAM (RSS) bar
  during generation.
- **Custom Hugging Face GGUF models by repo.** Add a model by its HF repo and the
  app auto-resolves a good quant (no manual filename), then lets you switch or
  delete it from the manager; the choice is persisted across restarts.
- **Answer-model switcher** with on-disk install state; **Compare / face-off**
  lists only installed models of the project's own backend (no Ollama vs
  llama.cpp mixing) and never offers embedding models as answer models.
- **Local model manager redesign:** installed models lead as compact
  click-to-expand rows with real metadata (params, quantization, context,
  capabilities), Answer and Search models split by a divider, with an "Add or
  change a model" section below.
- **Adaptive Project Understanding home:**
  - Role-aware deep analysis written through the workspace's selected lens
    (Tester, DevOps, Developer, Business analyst, …).
  - "Project activity" card from read-only git history (last commit, counts,
    contributors, project age, 90-day most-changed files).
  - Grounded guide cards — Architecture at a glance, Where to start, How to run
    (commands read from the project's own files).
  - "TODOs & loose ends" — a deterministic TODO/FIXME/HACK/XXX/BUG inventory.
  - A calm banner when on-disk files changed since the last scan (one click
    re-scans, rebuilds context, and re-analyzes).
- **Ask flow:**
  - Streaming answers (SSE).
  - Reasoning on/off toggle (sent only when on, never breaks non-thinking models).
  - Model-decides routing: the model itself chooses between answering from the
    project and general chat, with a real model identity.
  - Per-question "Answer style" picker overriding the skill profile.
  - File attachments via drag-and-drop with smart, relevant excerpts; removable
    file chips; files-only questions.
  - Save note / Copy / Create file as compact actions.
  - **Honest answer metrics** (developer mode): real token counts (in / out /
    total) read from the engine, generation speed, latency, retrieved-context
    count, and **context-window usage** ("used / window · %"). The window is the
    engine's real running window — a fixed, memory-safe size used consistently by
    both llama.cpp (`-c`) and Ollama (`num_ctx`), not the model's theoretical max.
- **Settings:**
  - One unified Skills editor — edit any built-in skill or create your own,
    picked per question in Ask.
  - Text size, default reasoning/streaming, theme (System / Light / Dark),
    Apple-style toggles, and an About section.
  - Two clearly scoped resets — Reset settings and Reset projects & data.
- **Onboarding:** full-window setup takeover, live scan/index progress (X of Y
  files + percent), inline model-download progress with a status checklist, a
  Stop control during scan/index, and an explicit engine-choice step (the engine
  can still be switched on the Models step before the index is built).
- **Downloads:** a global active-downloads indicator (with per-job Stop) and a
  live model-memory indicator in the sidebar.
- **Tester** and **Business analyst** assistant modes.
- **`.gitignore`-aware indexing** — virtualenvs, `node_modules`, build output,
  caches, and local `.env` files stay out of the local index.
- **Packaging & release:** per-architecture macOS DMGs (Apple Silicon + Intel),
  a signing/release GitHub workflow, and in-app self-update.
- Open-external-URL support so in-app links (e.g. "Get Ollama") open the browser.
- Repository hygiene: README hero + screenshots gallery, CI hardening,
  Dependabot, ruff lint/format, `CODE_OF_CONDUCT.md`, and this changelog.

### Changed

- **Faster cold start:** the frozen backend is built with PyInstaller **onedir**
  instead of onefile, so the runtime no longer unpacks to a temp dir on every
  launch (startup dropped from ~5–10s to near-instant).
- **Persistent search index:** the default vector store is now SQLite, so the
  index survives a backend restart (was in-memory → "no chunks" after restart).
- **Stable readiness:** workspace readiness is a per-project fact
  (scanned + indexed + models chosen), not tied to the global active runtime —
  no more setup/ready flip-flop when switching projects; opening a workspace goes
  straight into the working view.
- The active engine is persisted and restored on launch; status reflects the
  real live provider; Ask errors are backend-neutral.
- Routing is decided by the model rather than keyword heuristics.
- Settings is preferences only (dropped the readiness/hero panels); the Models
  tab was decluttered (dropped Product goal, Download history, manual install).
- The Ask context panel is quiet by default (a single line when collapsed,
  key/value sources when expanded) and the answer metrics are labelled.
- Text size scales the whole UI; setup screens are vertically centered.
- A single clean stylesheet replaced the legacy one.
- The backend reports its version in the FastAPI/OpenAPI schema.

### Fixed

- llama-server "exited during startup" — bundle all required dylibs (including
  dereferenced symlink aliases) and surface the server's real stderr.
- llama.cpp engine failing to start its servers ("couldn't bind HTTP server
  socket") and embeddings returning HTTP 500. A previous app run could leave an
  orphaned `llama-server` holding ports 8080/8081 (macOS doesn't kill children
  with the parent), so the new servers couldn't bind and requests hit the stale
  one. The engine now clears its own orphaned llama-server processes (matched by
  the exact bundled binary path) before a fresh start.
- llama.cpp embedding API returning HTTP 500 on `/v1/embeddings`. The embedding
  (and reranker) server now sets its physical batch size to the full context, so
  a whole chunk fits in one batch — fixing the "input is too large to process,
  increase the physical batch size" 500. It also starts with mean pooling (no
  chat-template flag needed), sends the input as a single-item list (some
  llama-server versions reject a bare string), and indexing retries any remaining
  transient errors with a short backoff — so "Build context" stops failing.
- False "selected embedding not active" warning when running on llama.cpp.
- Answer creativity is observable — "Precise" sends temperature `0.0`.
- Ollama "Install & continue" no longer stalls (the backend is re-activated so
  the embedding matches the active runtime).
- The Reasoning toggle no longer breaks models that can't think.
- Empty/stale index answers normally with a non-blocking rebuild warning instead
  of a hard "no chunks" error.
- The macOS folder-access prompt is tied to deliberate use — no project-folder
  walk on a cold launch.
- Reduced a polling storm during onboarding (lightweight polls, refresh only on
  real transitions).
- Files can be dropped into the webview (native drag-drop disabled).
- The setup "Scan project" button could get stuck (no reaction) after installing
  Ollama, because a stalled refresh left the step busy — the re-check now never
  freezes the next action.
- Small models sometimes answered a clear project question with just their model
  name ("I am …"). The answer prompt now leads with "answer from the project
  files and cite the source_path" and demotes the model-identity note to a
  low-priority end clause, so the retrieved context is actually used.
- "Get Ollama" button contrast, plus assorted spacing, font, and button-sizing
  inconsistencies across Home, Models, Ask, and Settings.

### Removed

- The verbose "Answer verification" panel — only a quiet, high-severity honesty
  notice remains (e.g. "you're on the placeholder test model").
- MCP and Advanced tabs from Models; redundant Home headers/panels; and the
  misleading "Confluence / Jira — coming soon" source cards.
- A dead internal documentation/packaging endpoint subsystem, the legacy
  stylesheet, and assorted dead code and types.

## [0.1.0] - 2026-06-05

Initial local-first release candidate: workspace onboarding, project scan and
skill detection, local RAG Ask flow, persistent conversations, guided local
model setup, safe model-download drafts, Agent/MCP planning UX, and the macOS +
Tauri packaging foundation. See
[docs/V01_RELEASE_NOTES.md](docs/V01_RELEASE_NOTES.md) for the full list.

[Unreleased]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.95...HEAD
[0.1.95]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.0...v0.1.95
[0.1.0]: https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/tag/v0.1.0
