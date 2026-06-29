# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Settings persist on the backend.** App-level preferences (theme, default Ask options, branding, accent, …) are now stored on the local backend (`GET`/`PUT /preferences`) instead of only the browser, so they survive a cache clear and are shared across the desktop window and any browser tab. localStorage is kept only as an instant first-paint cache; on first run the existing local settings are migrated up automatically. Fully local — nothing leaves the machine.
- **Retrieval-quality eval harness.** A small, deterministic "golden questions" evaluator (`core.domain.answer_eval` + `RunRetrievalEvalUseCase`): each case declares the file(s) its answer should be grounded in, and scoring measures whether retrieval surfaced them (recall) — no LLM, no flakiness. A stable regression guard for RAG tuning, in the same spirit as the existing deterministic test suite.

### Changed

- **Instant "Check now" when nothing changed.** The Project Intelligence graph build now skips the whole analyzer pass when the files (by content hash) and app version are unchanged since the last snapshot — the graph would be identical. The Watcher's check and any rebuild become near-instant on an unchanged project; a real change (or an app update) rebuilds as before. A forced rebuild is still available.
- **Faster indexing.** Both the full index and the incremental re-index now embed chunks in **batches** — one request per batch instead of one per chunk — where the engine supports it (the bundled llama.cpp embedding server takes a list of inputs). This markedly cuts the time to build or update context on larger projects. Engines without batch embedding (e.g. Ollama) transparently fall back to per-chunk.

## [0.2.3] - 2026-06-26

A **change-aware** release. The app now keeps track of what changed in your
project and keeps the local model's knowledge fresh — without re-indexing the
whole repository. A dated **change history** (git-based, cheap), an **incremental
re-index** of only the files whose content changed, and an Ask that can answer
"what changed today / since yesterday" from that journal. The bundled llama.cpp
engine is also faster and more reliable, and the read-only Investigator agent
uses schema-constrained output where the engine supports it. Everything stays
local, and no new model downloads are required.

### Added

- **Faster, more reliable bundled llama.cpp engine.** The answer server now starts with **Flash Attention** (quicker generation, smaller KV cache) and a **KV-slot save path** so a warm prompt prefix can persist to disk. Both are best-effort: if a particular build rejects a flag, the server automatically retries on the known-good baseline, so startup can never break. New env knobs: `AI_WORKSPACE_LLAMA_FLASH_ATTN` (default on) and `AI_WORKSPACE_LLAMA_PARALLEL` (default `1`; raise for concurrent request slots, at the cost of per-request context). GPU offload was deliberately left out to stay safe on the CPU-only Windows/Linux builds.
- **Structured (JSON-Schema) output** for the llama.cpp provider. Generation can be constrained to a JSON Schema so the model cannot emit invalid JSON (`core.domain.structured_output`) — the foundation for more reliable agents and structured features. (Ollama accepts the option but ignores it for now.)
- **Exact token budgeting.** When the engine exposes a tokenizer (llama.cpp `/tokenize`), the Ask context-window budget now uses real token counts instead of the ~4-chars-per-token estimate, and falls back to the estimate otherwise.
- **More reliable Investigator steps.** When the engine supports structured output (llama.cpp), the read-only Investigator agent now asks for each ReAct step as a schema-constrained JSON object, so the chosen tool-call can't be malformed. Engines without it (Ollama) keep the lenient text protocol, and a non-JSON reply degrades gracefully back to text parsing — no behaviour change for them.
- **Incremental re-index (changed files only).** When the project changes, you can update the AI's knowledge without re-indexing the whole repo: a new "Update index (changed files)" action (Settings) re-embeds only the files whose **content hash** changed and drops chunks for changed/removed files, leaving the rest untouched. Tracked by a per-file content-hash manifest (no reliance on mtime). New `POST /workspaces/{id}/index/changed`; the vector stores gained delete-by-source-path. The Settings section shows a **stale-index hint** ("N files changed since the AI last indexed them", from a cheap embed-free `…/index/changed/preview`) and an **optional auto-update** (off by default) that runs the incremental update once a day when you open the workspace. Then just ask in **Ask** — questions like "what changed today?" or "what changed since yesterday?" now pull the dated git change journal into the answer's context automatically.
- **Change history timeline.** A new **History** tab under Project Intelligence keeps a durable, **date-grouped** journal of what changed in the project — summary, risk/structural counts, changed areas (hover a chip for the files) and commit subjects — so the "what changed since last time" digest no longer vanishes when you leave the view. It fills **automatically**: opening the app on a new day records a dated entry from **git alone** (a cheap path — no file rescan, no graph rebuild, no re-indexing). "Check now" additionally re-scans to capture structural changes. A generated one-tap summary is saved onto its entry too.

### Changed

- **New app icon.** Redesigned the macOS/Windows app icon as a proper rounded-tile icon: a deep-forest gradient background with the pigeon-and-shield mark filling the tile and the home outline glowing as a frame — far more legible at dock/taskbar sizes than the previous white-background version. Regenerated the full set (`.png`, `.ico`, `.icns`). The brand mark also gets brighter, livelier eyes.
- **Bundled llama.cpp updated to `b9789`** (from `b9777`) for `scripts/fetch_llama_server.sh` and the release / Windows build workflows.

## [0.2.2] - 2026-06-25

A focused **Ask quality** release: the same local, private RAG, but the answers
are better grounded and the model's context window is used more deliberately. All
improvements are deterministic or best-effort, require **no new model downloads**,
and keep the default fast-start experience (the reranker stays off). The new
source-aware chunks take effect after a reindex (scan, then build).

### Added

- **Source-aware chunks.** Every indexed chunk now carries a deterministic one-line header — `[source: path › section · part N/M]` — derived from its own structure (a heading or a definition name). The header is stored and shown with the chunk so the model grounds and cites more reliably and the path is keyword-searchable, while the dense embedding is computed on the clean body so similarity is unaffected. No LLM call at index time; takes effect after a reindex.
- **Hallucinated-citation guard.** When an answer cites a file in backticks that wasn't in the retrieved context, Ask attaches a non-blocking "verify these" note instead of silently trusting it.
- **Optional query rewrite.** Ask can distil a question into a compact search query with the loaded model before retrieval, so pronoun- or intent-phrased questions still find the right files. Off by default (one extra call per ask); opt in via `AI_WORKSPACE_ASK_QUERY_REWRITE`. Reuses the loaded model — no new download.

### Changed

- **Smarter use of the model's context window in Ask.** The grounded prompt is now token-budgeted to the model's real context window — retrieved chunks are sized to what actually fits after reserving room for project memory, conversation history and the answer, so the engine never silently truncates an overflowing prompt. The prompt is also reordered (stable instructions/context first, the question last) and llama.cpp prompt caching is enabled, so multi-turn answers start faster.
- **Semantic project memory.** Recalled memory is re-ranked by embedding similarity (when a local embedder is available), so a question about "production" surfaces a note that says "prod is called prd" even with no shared words. Best-effort, with the deterministic keyword + pin + recency selection as the fallback.
- **Conversation history fits the window, with rolling summarization.** Recent turns are kept by token budget (not a fixed count), and older evicted turns are folded into a short running summary — so a long chat no longer forgets its earlier context after a handful of exchanges. Best-effort; falls back to just the recent turns.
- **More, more diverse context per answer.** With the reranker off (the default), Ask now pulls a wider candidate pool and selects a relevant-but-diverse subset with Maximal Marginal Relevance, so a fixed context budget covers more of the codebase instead of near-duplicate top hits.

## [0.2.1] - 2026-06-24

### Added

- **Build provenance & dependency scanning.** Release installers now carry a cryptographic [GitHub Artifact Attestation](https://docs.github.com/actions/security-guides/using-artifact-attestations-to-establish-provenance-for-builds) (verifiable with `gh attestation verify <file> --repo …`), and a weekly **OSV-Scanner** workflow reports known-vulnerable dependencies to Security › Code scanning. Both actions are pinned by commit SHA.

### Changed

- **Docs:** the deep Project Intelligence / Watcher / Investigator / Memory detail moved to `docs/PROJECT_INTELLIGENCE.md`; the README keeps a short overview with a link. The Project Intelligence **Security** tab is renamed **Security review**.

## [0.2.0] - 2026-06-24

First minor release since `0.1.99`. It turns AI Private Workspace from a local RAG
chat into a full **read-only project-intelligence** tool — still entirely local,
private, and grounded in your own files — and hardens the project's open-source
security posture. Headline themes (the detailed `0.1.100`–`0.1.178` history is
preserved below):

### Added

- **Project Intelligence.** A deterministic, role-neutral evidence graph with an interactive **Map**; **role lenses** (Developer / DevOps / Tester / Business analyst) and an **adaptive role dashboard**; a visual **CI/CD flow**; **Cloud** and **References** tabs; environment comparison and deployment flow; and a read-only **Security lens**. Findings everywhere read as human leads ("what was found, why it may matter, what to check"), not verdicts.
- **Read-only agents & analysis.** The **Investigator** — a bounded ReAct loop over read-only tools (`search_code`, `read_file`, `graph_query`, `list_files`, `git_history`, `ci_triggers`) with a transparent trace and collected sources — and the deterministic **Watcher** ("what changed since I last looked?", with an optional one-tap LLM recap of the commits).
- **Project groups.** Treat several repositories as one project: group **Ask** (repo-tagged sources), a portfolio **Home**, and group **Intelligence** that *compares rather than merges* (repo×environment matrix, shared-vs-unique tech, risks grouped by pattern).
- **Memory & profile.** Local, fully-editable **project memory** + handbook, and a cross-project **"About you"** profile applied to every project — with **review-first** suggestion (nothing saved until you keep it).
- **Navigation.** A **Cmd/Ctrl-K command palette** and a **file inspector** (owner, change-coupling, blast radius, the risks touching a file).
- **Answer feedback that teaches the project** (👍/👎 → corrections fed back into prompts) and much richer **git intelligence** (activity over time, branch strategy, change coupling, merge/PR activity).
- **Embedders & models.** BGE-M3 / Qwen3-Embedding installable on both engines; Qwen3 4B as the default answer model; conversation memory and an opt-in reranker in Ask.

### Security & supply chain

- **OpenSSF Best Practices: passing**, plus OpenSSF **Scorecard**, **CodeQL** SAST, **REUSE**-compliant licensing, and a **CodeFactor** grade. All GitHub Actions are pinned to commit SHAs; workflow tokens follow least privilege; the backend Docker image is pinned by digest. Releases are signed and ship **SHA256SUMS**, an **SPDX SBOM**, and an **automated-test report**. Contact routes through GitHub (no email in the repo).

### Changed

- The **Skills** library is now a single editor in **Settings**; the Models tab gains **Tuning**. Bundled **llama.cpp** updated to `b9777`.

## [0.1.178] - 2026-06-24

### Added

- **OpenSSF Best Practices: passing.** Earned the OpenSSF Best Practices *passing* badge (project 13357) and added it to the README alongside the other compliance badges. README badges are grouped into two centered rows (release/status and quality/compliance) with REUSE and CodeFactor using their native badges.

### Changed

- **Tighter Scorecard posture.** `release.yml` now uses top-level `contents: read` with `contents: write` only on the jobs that touch the GitHub Release (Token-Permissions). `SECURITY.md` links to GitHub private vulnerability reporting and issues (Security-Policy). The backend Docker base image is `python:3.14-slim` pinned by digest, tracked by a new Dependabot `docker` ecosystem (Pinned-Dependencies).
- **Privacy.** Contact routes through GitHub (no email in `REUSE.toml` or `SECURITY.md`); copyright is dated 2026.

### Fixed

- **Builds green after dependency bumps.** Vite `manualChunks` switched to the function form (type-compatible after the Vite/Rollup major bump); resolved two `ruff` F821 errors by declaring the `GitChangeBrief` forward-reference annotations under `TYPE_CHECKING`.

## [0.1.177] - 2026-06-24

### Added

- **Open-source compliance badges & supply-chain hardening.** Set the project up for the recognized free badges: an OpenSSF Scorecard workflow (publishes results for the live badge), CodeQL static analysis for the Python backend and the TS/JS frontend, REUSE compliance (`REUSE.toml` + `LICENSES/Apache-2.0.txt` + lint workflow) so every file has machine-readable copyright/licensing, a CodeFactor badge, and `.github/CODEOWNERS`. All GitHub Actions are now pinned to commit SHAs (kept current by Dependabot). `docs/CERTIFICATION_AND_BADGES.md` documents the one-time account steps and includes an OpenSSF Best Practices answer sheet mapped to this repo.

### Changed

- **Bundled llama.cpp updated to `b9777`** (from `b9675`) for the release/Windows build workflows and the `fetch_llama_server.sh` default.

### Added

- **One-tap recap of what the team did.** The "What changed since last time" card now has a *Summarise the changes* action: the local model reads the commit messages from the latest check and writes 2-3 plain-language sentences about what the work accomplished. It is grounded only in the commit subjects already in the digest (no extra git query, nothing invented), and the prompt is trimmed to fit the answer window so even a busy day with hundreds of commits never overflows. Read-only and entirely on-device.

## [0.1.139] - 2026-06-23

### Changed

- **Environments read as a matrix.** The Environments tab now has a labelled header row (Environment · Detected by · Evidence · Defined in), so the per-environment comparison reads as an at-a-glance table.
- **Read-only message leads.** The README hero now states plainly that the app reads, explains, and helps you understand — it does not change your project — with the optional, consent-gated file draft kept secondary. README also documents the adaptive role dashboard, the human-readable risk framing, and the CI/CD flow view.

## [0.1.138] - 2026-06-23

### Added

- **CI/CD flow view.** A new **CI/CD flow** tab in Project Intelligence lays the pipelines out visually: each trigger (push to a feature branch, push to the default branch, pull request, tag/release, schedule, manual) flows into the workflows it fires and the jobs inside them, with schedules and clickable workflow files. Security/scan jobs are flagged using the same generic scanner vocabulary the Security lens uses, and the environments the project defines are listed below with an honest note that the workflow-to-environment mapping isn't always explicit. Built entirely from the CI data already extracted from the project's own workflow files.

## [0.1.137] - 2026-06-23

### Added

- **Adaptive role dashboard.** Project Intelligence now opens with a role-framed brief band — "DevOps dashboard", "Developer dashboard", and so on — that leads with the facts that matter to your role (counts of environments, pipelines, modules… whatever the project actually has), the risks worth your attention, and a row of **suggested questions** you can click to open straight in Ask. It is one adaptive view, not six bespoke screens: the same facts, re-composed for whoever is looking, all decided on the backend from the project's own evidence. Switching role re-frames it instantly.

## [0.1.136] - 2026-06-23

### Added

- **Role-shaped answers in Ask.** The same question now produces an answer framed for your role — "Explain this project" leads with deployment and environments for DevOps, architecture and entry points for a Developer, the main flows to test for QA, an executive summary for a Manager, and what the system does for users for a Business analyst.
- **Role brief + suggested questions (backend).** A deterministic, role-focused brief — the facts that matter to your role, the top risks for it, and a handful of questions worth asking — derived from the project graph. Suggested questions only offer what the project's own evidence can actually answer (no cloud question without cloud services, etc.), ordered by what is central to the role. Wired into the intelligence endpoint; the adaptive dashboard renders it next. No LLM, no hardcoded technologies. New `app.core.domain.role_brief` module with pure tests.

## [0.1.135] - 2026-06-23

### Added

- **Human-readable risk explanations.** Every finding in the Risks tab (and the Security lens) now reads as a lead for a human, not a verdict: what was found, **why it may matter**, where (a clickable file that opens the inspector), how confident we are in plain language, and **what to check yourself** — plus the recommendation reframed as "an idea to consider, review, don't auto-apply". The framing is derived deterministically from each finding's category, severity, and confidence (no LLM, no hardcoded technology names), so it stays honest. New `app.core.domain.risk_explanation` module with pure tests.

## [0.1.134] - 2026-06-23

### Documentation

- **Reframed the README around private, read-only project intelligence.** The "Project intelligence and agents" section is now "Project intelligence and read-only analysis"; the Watcher and Investigator are described as read-only analysis tools (deterministic change tracking and evidence-backed investigation) rather than "agents", with the read-only-by-construction guarantee stated up front. No product behaviour changed.
- **Removed MCP from the public README.** The MCP-tools registry is no longer surfaced in the product-flow, safety, and roadmap copy until its direction is decided. The capability stays in the codebase; only the user-facing documentation was trimmed.

## [0.1.133] - 2026-06-23

### Documentation

- **Updated the install and welcome screenshots** to the new pigeon logo.
## [0.1.132] - 2026-06-23

### Documentation

- **Refreshed README screenshots** with the current UI (pigeon brand, new tabs): a new Ask hero, the create-workspace / engine / build-context onboarding steps, and a small "A few more screens" gallery (command palette, security lens). All screenshots are redacted — workspace/project names, local file paths, and contributor details are blurred — and the raw, unredacted captures are git-ignored so they can never be committed.
## [0.1.131] - 2026-06-23

### Changed

- **Pigeon avatar in Ask.** Your message avatar is now the app's pigeon brand mark instead of the placeholder cat.
- **Sources toggle matches the "Answer style" link.** The per-answer "N sources from your project" row now expands via a small down-caret (⌄ that rotates) instead of a "Show" label — quieter and consistent with the rest of Ask.
## [0.1.130] - 2026-06-23

### Fixed

- **Groups no longer show empty on launch (and no more duplicate group on drag).** The groups list was loaded at mount, which could fire before the desktop backend was reachable and fail silently — leaving the sidebar empty. It now loads once the backend is ready (right after workspaces). Drag-to-group also re-checks against a fresh group list before creating, so a stale/empty list can never produce a duplicate of an existing group.
## [0.1.129] - 2026-06-23

### Changed

- **Simpler Ask screen.** The "Answer style and sources" panel is no longer a full bordered box that looks empty when collapsed — it's now a quiet inline link with a small caret. The per-answer "N sources from your project" bar is smaller and quieter, so the answer itself leads.
## [0.1.128] - 2026-06-23

### Changed

- **Visual consistency pass (one look across the app).** Unified the small primitives that had drifted apart: section labels ("eyebrows") and neutral chips now share one quiet treatment everywhere, cards share one padding rhythm, and the accent / success green is driven from a single token (so it's one hue, not three). Primary buttons share one ink colour.
- **A calmer, clearer Ask front door.** The empty Ask view now invites a question in plain language with concrete starters ("How does deployment work?", "What are the main risks here?", "Where should I start reading?") instead of describing internals.
## [0.1.127] - 2026-06-23

### Changed

- **Home reads as a brief, not a wall.** It now opens with one plain-language lead line ("Built with X, Y, Z. N commits by M people, K this week.") and a single clear next step — "Ask anything about it →". Secondary cards (How to run, TODOs, Files by area, Sources) are collapsed by default and expand on intent, so the page leads with one thing instead of a dozen stacked panels.

## [0.1.126] - 2026-06-23

### Documentation

- **README refreshed** to cover the capabilities added recently: multi-repo project groups (portfolio Ask/Home/Intelligence), the Cmd/Ctrl-K command palette, the file inspector, the read-from-git project activity card with change coupling, and the security lens.

## [0.1.125] - 2026-06-23

### Changed

- **Files in Project Intelligence's "Where to start reading" are now clickable** and open the file inspector — consistent with Home, so the inspector is reachable wherever a file path appears.
- **Honest empty state for sparse projects.** When the analyzers find little to map (small, docs-only or single-purpose repos), Project Intelligence now says so plainly — "Not much to map here yet" with a short explanation that it's expected, not an error — instead of looking broken. Clarifies why role profiles look the same on such repos.

## [0.1.124] - 2026-06-23

### Changed

- **The project handbook is labelled clearly.** It now explains that, once generated, it's automatically fed into every Ask and Investigate as background to keep answers grounded — it's working memory, not a document to read — with an "In use" badge when one exists. Same clarification for the group handbook.

## [0.1.123] - 2026-06-23

### Changed

- **The file inspector is now discoverable.** Files in Home's "Where to start" and the git "Where the work is going" hotspots are clickable and open the inspector (in addition to Cmd/Ctrl-K file search). Clarified that the Project Intelligence role/profile applies instantly (a tooltip on "Viewed as") — Rebuild only re-scans the project files.

## [0.1.122] - 2026-06-23

### Added

- **Security posture lens.** A new "Security" tab in Project Intelligence (shown when there's something to say) reads what security gates already exist and where the gaps are: which scan/audit steps run in CI (secret, dependency, IaC scanning, etc., detected from the pipeline graph) and which deterministic findings are security-relevant (permissions, secrets, public exposure, encryption, IAM/access, remote state) with their recommendation and source file. Read-only — it reports on scanners, it never runs one.

## [0.1.121] - 2026-06-23

### Added

- **File inspector.** Open any file (via Cmd/Ctrl-K search) to get a read-only lens on it: who owns it (top git authors — the person to ask), what it changes together with (temporal coupling), what it connects to in the project map (its blast radius — what it depends on and what it affects), which risks touch it, and its recent commits. New read-only `GET /workspaces/{id}/file-activity` endpoint; everything else is composed from data the app already computed. No hardcoded technologies.
- **File search in the command palette.** Once you type, the palette also searches the current project's files and opens the inspector on selection.

## [0.1.120] - 2026-06-23

### Changed

- **"What changed since last time" now shows a counts row** (added / removed entities, new / resolved risks) above the highlights, so the volume of change since your last check reads at a glance.

## [0.1.119] - 2026-06-23

### Added

- **Command palette (Cmd/Ctrl-K).** One fast, keyboard-first entry point to jump to any repository, group, or section without reaching for the mouse. Fuzzy-filter as you type; arrows + Enter to go. (File search joins it with the file inspector.)

## [0.1.118] - 2026-06-23

### Fixed

- **Group view now uses the full width** instead of hugging the left edge with a 920px cap, matching the single-project layout.
- **Group repo cards show the default branch** (e.g. `main`) instead of whichever feature branch happens to be checked out — consistent with the single-project Project activity card.

### Fixed

- **Group Ask answers are now formatted.** They render markdown (bullet lists, inline `code`, **bold**, fenced code blocks with offline highlighting) using the same renderer as the single-repo Ask, instead of showing raw `*` and backticks as plain text.

## [0.1.116] - 2026-06-23

### Changed

- **Group Intelligence now compares repos instead of merging them into one pile.** A group is treated as a portfolio: environments are shown as a repo×environment matrix (who deploys where), technologies are split into common-to-all / shared-by-some / unique-to-each-repo, and risks are grouped by finding type with a per-repo breakdown (so you fix the pattern, not 20 identical rows). A repo filter at the top keeps the repository a first-class dimension — isolate one repo or compare any subset. Scales cleanly from 2 to many repos.
- **Group Ask is less primitive.** The answer sits in a proper card with a per-repo contribution bar (how many chunks each repo gave), and sources are grouped under per-repository headings instead of a flat list.

### Changed

- **Drag-to-group is smarter.** A group created by dropping one project on another now opens straight in rename mode so you can name it immediately (and the group title shows a hover ✎ to rename any time). Dropping the same two projects again no longer makes a duplicate — if a group already contains both, it just opens that group. Dropping a project onto a group it's already in is a no-op too.

### Added

- **Change coupling ("Changes together").** The Project activity card now surfaces file pairs that keep changing in the same commits, computed deterministically from git history. Pairs that live in different folders are flagged "cross-module" — a tell of a hidden dependency the import graph misses. Helps you see what really moves together before touching a file.

### Changed

- **The git activity card now adapts to the role chosen at project creation.** Same deterministic data, reordered and framed for the role: DevOps leads with how it ships and what's entangled; a developer with where to work and who to ask; a tester with where change concentrates (the risk surface); an analyst/manager with delivery pace and the team. No hardcoded technologies — purely a presentation lens.

### Changed

- **Richer "How they ship" in the Project activity card.** It now names the repo's long-lived branches and the kinds of branches that actually get merged (e.g. feature/, fix/), derived from git history already collected. No hardcoded assumptions.

## [0.1.112] - 2026-06-22

### Added

- **Project memory entries are now editable.** Each note/correction has an inline edit (✎) — fix wording in place; the kind and pin state are preserved.
- **Add a project to a group from its Manage menu.** If no groups exist yet, it offers to create one with this project; if groups exist, it lists them to pick from (or start a new one).
- **Drag-and-drop grouping.** Drag one project onto another to create a group with both, or drag a project onto an existing group in the sidebar to add it there.
- **Map blast radius.** Click any node on the project map to see its full impact: everything it depends on (upstream) and everything it affects (downstream), computed transitively over the graph. Unrelated nodes dim, and a panel summarizes the reach so you can judge what a change touches before making it.

### Changed

- **Manage actions are now compact icon buttons** (add-to-group, clear index, archive, delete, close) with tooltips, instead of a row of wide text buttons.
- **"Where to start reading" no longer dumps near-identical files.** It keeps one representative per filename (the most root-level), so infra repos show a short, varied set of real entry points instead of ten copies of `terragrunt.hcl`.
- **Removed the "Ask about this" button on Home** — it duplicated the Ask tab already in the top nav.
- **Removed the "Ask the map" sub-tab** from Project Intelligence; the quick graph-only answer added little over the main Ask.

### Fixed

- **Creating and deleting a project group now works in the desktop app.** Native `window.prompt`/`confirm` are disabled inside the Tauri webview (they silently return null), so group creation now uses an inline name input and deletion uses an inline two-step confirm.

## [0.1.111] - 2026-06-22

### Added

- **Rate an answer to teach the project (not the model).** Every answer in Ask,
  "Ask the map"/Investigate and group Ask now has a quiet 👍/👎. A thumbs-down
  opens a small "what's the correct answer?" field and saves it as a Correction;
  a thumbs-up saves the Q&A — both are fed back into future prompts by the app, so
  answers get better over time. The copy is honest that this doesn't retrain the
  local model — the app just remembers and re-injects what you confirmed.
- **Ratings turn into nudges.** The thumbs are logged locally (with the model and
  how much context each answer had), and from the recent history the Ask tab
  surfaces at most two calm, dismissible suggestions: "answers are getting
  thumbs-down a lot — try a larger model" (opens Models) and "low-rated answers
  had little project context — rebuild the search context" (opens Home). Pure,
  deterministic heuristics over a local log; nothing is uploaded or used to train.
- **Project groups — treat several repositories as one project.** A group owns an
  ordered list of member workspaces; each repo stays a normal, independently
  scannable workspace underneath, and the group aggregates over them:
  - **Ask the group** — one question fans out to every member's search index, the
    candidates are merged by score with a per-repo cap so a large repo can't crowd
    out the others, and the answer's sources are each labelled with the repo they
    came from.
  - **Group Home** — rolled-up totals (repositories, services, environments,
    commits this week) plus a per-repo card with its own git activity.
  - **Group Intelligence** — environments and technologies unioned across repos,
    and risks listed with the repository that raised them.
  - Sidebar "Groups" section to create a group and switch into its view; add or
    remove member repositories inline. Member workspaces are only referenced —
    never created or deleted by group actions. Everything stays on this computer.
  - **Group Ask is at parity with single-repo Ask:** answers stream token by token
    over SSE, can be grounded with project context (handbook + memory + map facts)
    composed across the members — with a "used N memory + M facts" note — and honour
    a reasoning (think) toggle.
  - **Group UX:** rename a group inline, delete a group (repositories untouched),
    member add/remove shows a busy state, and a live typing caret while the answer
    streams.
  - **Group-level memory + handbook:** notes/decisions/corrections recorded on the
    group itself (separate from each repo's own memory) and a deterministic group
    handbook generated from the overview. Both are fed into group answers — group
    context is composed first, then each member's — so the AI improves at the whole
    project over time. New "Notes & handbook" card on the group's Home.

### Changed

- **Intelligence tab: merges and the quick Ask box are clearer** (carried from the
  Home/Intelligence readability pass) — and the same evidence-backed, repo-attributed
  approach now extends across a whole group.
- **New app icon and in-app logo: a friendly messenger pigeon.** A chubby pigeon
  guarding a green shield-lock inside a house outline — the postal bird as the
  channel between you and the local AI, with the home + lock signalling "private,
  on your machine". Replaced the OS app icons (`src-tauri/icons/*`) and the in-app
  mark (`public/app-icon.png`); light/dark source sets live under
  `assets/brand/app-icons/` with `.ico`/`.icns` in `assets/brand/tauri-icons/`.

### Fixed

- **Project memory no longer piles up duplicate Q&A.** Re-asking the Investigator
  the same question now replaces its previous auto-captured answer instead of
  adding a new copy each time (pinned Q&A are kept).
- **Project memory card is calmer.** The list of remembered items (including the
  auto-captured Q&A) is collapsed by default behind "Show my entries (N)"; adding a
  note shows a brief "Remembered: …" confirmation that fades, instead of dumping the
  whole list inline. Editing/deleting still lives one click away in the expanded list.
- **Project memory is simpler:** only two types to choose from — Note and
  Correction (Correction overrides a wrong assumption) — since the type only
  changes the label the model sees, not how memory is matched. Existing
  decision/fact items still display. An in-app hint explains it, and that pinning
  is what forces an item to always be considered.
- **Intelligence sub-tabs are polished to match the rest.** Cloud services show a
  relative-footprint bar and a "most used" summary per provider; Environments
  become a clean list with a production highlight, an evidence bar and a truncated
  source path (no more redundant chips + raw table); References truncate long
  ARNs/URLs to one line with a count pill and a per-group "Show all"; Deployment's
  CI and Pipelines blocks gained headers and one-line descriptions.
- **Cloud services now read as real AWS names.** The catalog maps the common AWS
  resource prefixes to human service names (e.g. `aws_ssoadmin_*` → IAM Identity
  Center, `aws_mskconnect_*` → MSK Connect, `aws_service_discovery_*` → Service
  Discovery, `aws_wafv2_*`/`aws_sesv2_*` collapse into WAF/SES) instead of
  title-casing a raw token into "Ssoadmin", "Wafv2", "Service".
- **"No remote state" is no longer reported when Terragrunt manages the backend.**
  Terragrunt keeps `remote_state` in `terragrunt.hcl`, so a Terraform stack with no
  `backend` block in `.tf` is expected — the map now marks Terraform's state as
  managed (shown as "remote state · Terragrunt") and drops the false finding.
- **Infrastructure tools no longer pin a meaningless representative file** (an
  aggregate over hundreds of files had no single useful source).
- **Environments show their root directory** (e.g. `accounts/dev/`) instead of an
  arbitrary deep file.
- **References hide the noise.** Provider/AWS documentation links
  (`registry.terraform.io`, `docs.aws.amazon.com`, …) and unresolved templates
  (`${var.region}`, `:TBD:`) are filtered out, so References shows real external
  dependencies — cross-account ARNs, external APIs, S3 buckets, module sources.
- **The Map is no longer a hairball.** The legend is now an interactive filter —
  click any layer (Environment, Pipeline, Cloud service, …) to show or hide it,
  each with a node count — and the noisiest layer, Jobs, is hidden by default.
  Hover still traces a node's connections and clicking opens its details.
- **Home's Project activity is more honest.** It shows the project's default
  branch (e.g. `main`) instead of whatever long feature branch happens to be
  checked out; the Momentum trend ignores the current, still-incomplete week so it
  no longer falsely reads "slowing down" mid-week; and JS/TS files in the Config
  card get real labels ("JS module", "ESLint config", …) instead of a bare
  "Config".

### Added

- **Project memory — the app learns about your project over time.** A new local,
  private knowledge layer that improves answers without touching model weights:
  - **Memory items.** Record notes, decisions, corrections ("production is called
    `prd` here") and facts. They are stored locally, are always editable, and can
    be pinned. The Investigator also auto-captures its answered questions.
  - **Project handbook.** A deterministic, human-readable summary of the project
    (assembled from the evidence graph) that doubles as durable model context.
  - **Shared context layer.** A single `compose_project_context` combines the
    handbook, the most relevant memory, and matching graph facts — and is injected
    into **both** the Ask tab and the Investigator (which also gains a
    `recall_memory` tool), so every answer benefits. Entirely local and
    deterministic in what it selects; backward-compatible (off when no memory).
  - **Visible indicator.** Answers now show, in plain text, how much durable
    context they drew on — e.g. "Used 2 memory note(s) and 3 map fact(s)" — in
    both the Ask tab and the Investigator, so you can see the memory working
    without an experiment.



### Added

- **CI "what runs when" explainer.** The Deployment tab now explains, in plain
  language, which workflows run for each event — push to a feature branch, push or
  merge to the default branch, opening a pull request, pushing a tag / release, on
  a schedule, or manually — derived deterministically from GitHub Actions triggers
  (`on:` with branch/tag filters). The Investigator gains a matching `ci_triggers`
  tool so it can answer "what runs when I push to my branch?" with the same facts.
- **Merge & PR activity (from history).** The Git activity card now surfaces
  approximate pull/merge-request activity inferred from merge-commit messages and
  `(#N)` / `!N` references: how many PRs/MRs landed, the source-branch types
  (`feature/`, `hotfix/`, …) and which branches they merged into. Clearly labelled
  as approximate, since squash- and rebase-merged PRs are only partly visible.

### Changed

- **Project Intelligence is now its own top-level tab** (Home · Intelligence ·
  Ask · Models · Settings), instead of a block stacked on an already-long Home.
  Home becomes a calmer overview (project summary, watcher, git activity, memory,
  sources) and the full map/agents live on their own screen.
- **Home's heaviest cards collapse by default.** The full git-activity panel and
  the optional AI deep-analysis card are now expandable sections (a one-line
  summary with a teaser), so the overview is scannable instead of a long scroll.
- **Project activity reads like a briefing, not a dashboard.** Seven cryptic stat
  boxes become three "at a glance" numbers (commits this week, active
  contributors, how work ships); contributors get a "Who knows this code" section
  with initials avatars, clean share bars and an active/last-seen dot; merges and
  branching merge into one "How they ship" block; hotspots become "Where the work
  is going"; and the 12-week chart gains a plain trend caption (picking up /
  steady / slowing down).
- **Intelligence tab speaks plain language.** The Overview's four bare counters
  become metric cards that name what they count (the actual environments,
  pipelines and infra tools found); every section gets a one-line description of
  what it's showing; Risks opens with a "N things worth a look · X high" summary;
  and tabs are friendlier ("Overview", "Ask the map").
- **One way to ask inside Intelligence.** The always-present quick "Ask" box and
  the separate "Investigate" tab merged into a single "Ask the map" panel: one
  question, two buttons — Ask (a quick answer from the map) or Investigate (the
  read-only step-by-step agent). No more two question boxes on screen at once.

### Fixed

- **Project Watcher no longer prints a wall of changes** — the digest caps at the
  top changes with a "Show all N changes" toggle.
- **Deep analysis no longer dumps raw JSON** — when a local model wraps its answer
  in a ```json block (even a truncated one), the human summary is salvaged instead
  of shown verbatim.
- **Home is more legible** — file columns now show meaning (module names, pipeline
  names, config purpose) instead of raw paths; the project summary no longer
  contradicts the detected stack while loading; Sources shows search coverage and a
  local-only trust line; Project activity opens with a plain-language sentence; and
  the confusing weekday chart was removed.

### Docs

- **README: what the Investigator can reason about.** The agents section now lists
  the agent's knowledge areas and example questions it answers well, and makes the
  design intent explicit: one capable read-only agent with a small toolbox, not a
  separate agent per tool.



### Added

- **Investigator gains a `git_history` tool.** The read-only agent can now answer
  ownership and recency questions — "who should I ask about this module?", "when
  did this file last change and why?" — by reading a file's top authors and recent
  commits (read-only `git log` / author counts, repo-level when no path is given).
- **README: "Project intelligence and agents" section.** Documents the project
  map, the deterministic Watcher and the read-only Investigator — including the
  agent's tool list, how the ReAct loop works, and the trust guarantees
  (read-only, local, evidence-backed, transparent, bounded).



### Added

- **Investigator (read-only agent).** A new "Investigate" tab in Project
  Intelligence answers harder, multi-step questions ("How does a request reach
  the database?") by running a bounded agent loop over **read-only tools** — it
  searches the indexed code, reads files, queries the project map and lists
  files, one step at a time, until it can answer. The reply shows a **transparent
  trace** (every tool call, its input and what it returned) and the **sources it
  consulted**, collected deterministically so the answer is always backed by real
  evidence. Built for local models with a strict, self-parsed ReAct protocol
  (validation, retry and a graceful "out of steps" fallback rather than guessing).
  Read-only by construction: no tool writes files or runs commands; everything is
  local. This is the flagship companion to the deterministic Project Watcher.



### Added

- **Project Watcher (first agent).** A new card on the workspace Home answers
  "what changed since I last looked?" On demand it re-scans the project, rebuilds
  the Project Intelligence graph, and **diffs it against the previous snapshot** —
  reporting new environments, newly detected technologies, new/resolved risks,
  new cloud services, services and pipelines, plus counts for the noisier kinds
  (modules, dependencies, images, references). The first run records a baseline;
  later runs show a concise, ordered digest with severity-tagged risks. Entirely
  deterministic (the facts come from comparing two graphs, no LLM), read-only with
  respect to the project, and the digest is persisted so it survives restarts.
  This is the foundation for scheduled, hands-off drift detection.



This release introduces **Project Intelligence** — a deterministic, evidence-backed
map of an unfamiliar project built entirely from its own files (no code leaves the
machine) — and a much richer **Git intelligence** view. Highlights across the work
rolled into this release:

- **Project Intelligence (M1–M5):** a role-neutral evidence graph assembled from
  Terraform, Terragrunt, GitLab CI, GitHub Actions, Kubernetes, Helm and Python
  analyzers; **role lenses** (Developer / DevOps / Tester / Business analyst) that
  re-prioritise the same facts without changing them; an interactive **Map**; a
  **deployment-flow** view with honest gaps; **environment comparison**; an
  **ask-the-graph** Q&A constrained strictly to the facts; a **Cloud** tab listing
  the AWS/GCP/Azure services the IaC provisions; and a **References** tab (URLs,
  module sources, ARNs, S3 URIs).
- **Python application analysis:** framework detection, entrypoints, internal
  module-dependency graph, and notable third-party dependencies.
- **Git intelligence:** branch-strategy inference plus the live-activity additions
  detailed below.
- **Accuracy fixes:** reliable Terragrunt detection, more environment-name tokens
  (incl. `prd`→production), meaningful Infrastructure context, GitHub Actions jobs,
  and a tightened plain-language overview.

### Added

- **Richer, live Git intelligence.** The project-activity card now reads much
  more from the repository's history (all read-only `git` queries):
  - **Activity over time** — a 12-week commit sparkline and a "when the team
    commits" weekday distribution, so you can see the project's pulse at a glance.
  - **Who commits** — top contributors now show each person's share of all
    commits, whether they're currently active (commits in the last 90 days) or
    when they were last active, with a share bar.
  - **Recent commits feed** — the latest commits (subject, author, relative time).
  - **More headline stats** — commits in the last 7 / 30 days, contributors,
    how many are active now, and the share of work that lands via merge commits
    (a PR-based-workflow signal), alongside the existing branch-strategy block.



### Added

- **Project Intelligence: Cloud tab.** A new tab lists the managed cloud
  services the infrastructure-as-code provisions, grouped by provider
  (AWS / Google Cloud / Azure / …), with a resource count and source file for
  each. Derived deterministically from Terraform `provider` and `resource`
  declarations, with a curated catalog of friendly service names (Lambda, S3,
  EventBridge, RDS, GKE, AKS, …) and a sensible fallback for the rest.
- **Project Intelligence: References tab.** A new tab surfaces the external
  things the project points at — URLs, Terraform/Git module sources, AWS ARNs
  and S3 URIs — de-duplicated, counted and grouped by kind, with sources.
- **A more connected Map.** Terraform now links to the environments it manages
  and to the cloud services it provisions, GitHub Actions workflows expose their
  individual jobs, so the Map reads as a flow instead of disconnected columns.

### Fixed

- **Terragrunt now detected reliably.** Detection recognises named includes
  (`include "root" {`) and Terragrunt-only functions
  (`find_in_parent_folders`, `read_terragrunt_config`, `path_relative_to_include`,
  …), so Terragrunt-driven repositories are no longer misreported as
  "not detected".
- **Production environments no longer missed.** The environment-name vocabulary
  now includes `prd` / `prn` / `live` (→ production) plus `perf`, `demo` and
  `integration`, so common naming like `accounts/prd/...` is inferred correctly.
- **Infrastructure shows meaningful context, not a random file.** The Terraform
  entry now points at a representative root (`main`/`backend`/`providers.tf`) and
  shows file count, providers, and remote-state status instead of an arbitrary
  module file.
- **Deployment lists real pipeline jobs** for GitHub Actions workflows.
- **The plain-language overview no longer mislabels tools** — it is explicitly
  instructed not to assign roles the facts don't support (e.g. calling an
  infrastructure-as-code tool an "application framework").

## [0.1.103] - 2026-06-19

### Added

- **Project Intelligence (M4): Python application analysis.** For projects that
  are mostly Python, the build now understands the code itself, not just the
  infrastructure around it. Using only the standard library's `ast` (parse,
  never execute), it detects the **framework(s)** in use (FastAPI / Flask /
  Django / Celery / …), likely **entrypoints**, the project's top-level
  **modules** and the **import edges between them** (its internal architecture),
  and **notable third-party dependencies** from the manifests (a curated set, so
  the list stays meaningful). The application, its modules and dependencies join
  the same evidence graph — modules and their dependency edges are drawn on the
  interactive **Map**, and the framework and key libraries appear as technology
  chips in the Summary.
- **Branch strategy in Git insights.** The Git activity card now infers the
  repository's **branching model** — GitFlow, GitHub Flow, Trunk-based or
  Unknown — deterministically from branch names (`git for-each-ref`, read-only),
  showing the detected long-lived branches and prefixes (`feature/`, `release/`,
  `hotfix/`, …) with a plain-language rationale. It is always labelled as
  *inferred from branch names*, never asserted.

## [0.1.102] - 2026-06-19

### Added

- **Project Intelligence (M3): deployment flow, environment comparison, and
  ask-the-graph.**
  - The Deployment tab now opens with a **deployment-flow rail** — Source & CI →
    Build artifacts → Deploy → Environments — derived deterministically from the
    graph's relations, with honest **gaps** called out (CI with no image build,
    services deployed without a detected pipeline, an image a service runs that
    no CI job builds, or no environments inferred at all).
  - The Environments tab gains a **comparison table**: each inferred environment
    with the analyzer that detected it, how much evidence backs it, and its
    source file, plus a one-line coverage summary (e.g. production present but no
    pre-production environment found).
  - A new **Ask about this project** box answers free-text questions using the
    local model **constrained strictly to the graph facts** — when the answer
    isn't in the analyzed files, it says so instead of guessing. New endpoint:
    `POST /workspaces/{id}/intelligence/ask`.

## [0.1.101] - 2026-06-19

### Added

- **Project Intelligence (M2): Kubernetes & Helm + an interactive map.**
  - A deterministic **Kubernetes analyzer** parses manifests (multi-document
    YAML): workloads (Deployment / StatefulSet / DaemonSet / Job / CronJob /
    Pod), their container images, replicas, resource limits and health probes,
    plus Service / Ingress counts and namespaces. It flags mutable image tags
    (`:latest`), missing resource limits, missing liveness/readiness probes and
    single-replica Deployments — each finding cites its file.
  - A deterministic **Helm analyzer** groups files by their owning `Chart.yaml`,
    reporting each chart's name/version/appVersion, template count, values files
    (including per-environment `values-<env>.yaml`) and dependencies, and flags
    charts missing `values.yaml`, a version, or templates.
  - Both feed the same role-neutral graph: Kubernetes workloads and Helm charts
    become **services**, their images become **container images**, and
    environments are inferred from namespaces and `values-<env>` filenames
    (labelled "inferred", never asserted).
  - A new **Map** tab renders the graph as an interactive, dependency-free
    node-link diagram (infrastructure → pipelines → jobs → services → images,
    with environments). Hovering a node traces its connections; clicking shows
    its type, source file, evidence and relationships.

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

[Unreleased]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.99...v0.2.0
[0.1.99]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.96...v0.1.99
[0.1.96]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.95...v0.1.96
[0.1.95]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.0...v0.1.95
[0.1.0]: https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/tag/v0.1.0
