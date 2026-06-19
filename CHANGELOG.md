# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.100] - 2026-06-19

### Added

- **Project Intelligence (M1).** A new block on the workspace Home builds a
  deterministic, role-aware map of an unfamiliar project from its own files —
  no LLM is required for the facts, and nothing runs or is modified.
  - A role-neutral *evidence graph* (services, environments, CI/CD pipelines and
    jobs, infrastructure tools, container images, important config files, and
    risks) is assembled from the existing Terraform, Terragrunt, GitLab CI and
    GitHub Actions analyzers. Every entity carries its confidence and evidence
    status (confirmed / inferred / needs confirmation), so inferred facts (e.g.
    environments guessed from directory naming) are labelled honestly.
  - A **role lens** re-orders and prioritises the same facts for the selected
    assistant mode (Developer, DevOps, Tester/QA, Business analyst) without ever
    changing them. The view defaults to the workspace's own mode and can be
    switched in place.
  - The Home block presents Summary / Infrastructure / Deployment / Environments
    / Risks, with sources collapsed by default, gap-based questions for the team,
    a "where to start reading" file list, and honest empty / building / stale
    states. An optional plain-language overview is the only LLM-written piece and
    is constrained strictly to the graph's facts.
  - The graph is persisted as a snapshot (SQLite) and is only (re)built on an
    explicit request. New endpoints: `POST /workspaces/{id}/intelligence/build`,
    `GET /workspaces/{id}/intelligence`, and
    `GET /workspaces/{id}/intelligence/overview-text`.

## [0.1.99] - 2026-06-19

### Added

- **Windows support.** The app now ships a Windows x64 installer (NSIS `.exe`),
  built on a `windows-latest` runner alongside the macOS DMGs, with both local
  engines:
  - The bundled llama.cpp `llama-server.exe` (CPU x64/arm64) is fetched and
    staged at build time, so the built-in engine works with nothing to install.
  - Backend process management is cross-platform: orphaned `llama-server`
    processes are reaped via PowerShell CIM matched by the exact binary path
    (the same "only ever our own process" guarantee as `pgrep` on Unix), DLLs are
    resolved via `PATH`, and `uvloop` (Unix-only) is skipped on Windows so the
    frozen backend builds.
  - The desktop shell gained a native Windows folder picker, Windows-correct
    `PATH` handling, and resolves the bundled backend manifest and `llama-server`
    from the Windows installer layout (`resources/_up_/_up_/…`) with a recursive
    fallback across the install tree.

### Fixed

- The Windows app no longer opens a console window. The release binary is built
  as a GUI-subsystem app and the frozen backend is launched with
  `CREATE_NO_WINDOW`; previously a terminal appeared on launch, and closing it
  killed the app.

### Changed

- Release automation: GitHub Actions updated to Node-24-compatible majors
  (`checkout`/`setup-node`/`setup-python`/`upload-artifact` v6), and every GitHub
  Release now opens with a platform-grouped **Downloads** section (macOS Apple
  Silicon / Intel, Windows) built from the actually-uploaded installers, so the
  links are always correct.

## [0.1.96] - 2026-06-19

### Added

- **Conversation memory in Ask (multi-turn, like ChatGPT/Claude).** Follow-up
  questions now keep their context — ask "what about ECS for <project name> in dev?" then
  "how do I disable it?" and the model knows "it" means ECS instead of losing the
  thread. On the llama.cpp engine the recent turns are sent as real role-tagged
  chat messages (`user`/`assistant`) ahead of the new question — the native format
  models are trained on — so both the answer and the project-vs-general routing
  stay on topic. Ollama gets the same memory via a compact history preface in its
  prompt. Crucially, retrieval is **context-aware** too: a bare follow-up like
  "disable it" carries no searchable subject, so the RAG query is expanded with
  the last couple of user questions (which hold the real terms — "ecs", "<project name>",
  "dev") before dense + keyword search runs. Without that, the right files would
  never be retrieved no matter how good the prompt is. Best-effort and bounded
  (last few turns): a fresh chat or missing history changes nothing.

- **"Sharper search" reranker (opt-in).** A cross-encoder reranker precision pass:
  hybrid retrieval pulls a wider candidate set, a reranker model re-scores each
  (question, snippet) pair, and the best are kept — noticeably more relevant
  sources on tricky questions. A Settings toggle downloads a small reranker model
  (~370 MB) on first enable and runs it on the built-in llama.cpp engine
  (separate `llama-server --reranking` process). Fully gated and graceful: off by
  default, and if the model/engine isn't available Ask falls back to plain hybrid
  retrieval, so it can never break answering.

- **Syntax highlighting in answers (offline).** Fenced code blocks are now
  colorized with highlight.js using a curated, bundled language set (Python, Java,
  JS/TS, Go, Rust, SQL, JSON, YAML, Bash, Dockerfile, HTML/XML, INI/TOML,
  Markdown) — no network needed. Token colors are theme variables, so code reads
  well in both light and dark. Unknown languages fall back to safe plain text.

### Changed

- Code blocks in answers got a proper redesign: their own surface, a header strip
  naming the language, monospace body with horizontal scroll, and inline code as a
  subtle chip — and a markdown vertical-rhythm fix so a code block can no longer
  visually overlap the paragraph beneath it.
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
  names like `<project name>_allowed_cidr` — are matched lexically instead of being missed by
  pure semantic search. Two further signals sharpen results: a **path/env boost**
  (chunks whose file path segments match query terms like `dev` or `<project name>` are
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

[Unreleased]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.99...HEAD
[0.1.99]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.96...v0.1.99
[0.1.96]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.95...v0.1.96
[0.1.95]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.0...v0.1.95
[0.1.0]: https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/tag/v0.1.0
