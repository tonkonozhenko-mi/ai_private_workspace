<p align="center">
  <img src="assets/brand/logos/pigeon-mark.png" alt="AI Private Workspace" width="200">
</p>

# AI Private Workspace

<p align="center">
  <a href="https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/latest"><img src="https://img.shields.io/github/v/release/tonkonozhenko-mi/ai_private_workspace?label=latest&sort=semver&style=flat-square&color=2ea44f" alt="Latest release"></a>
  <a href="https://github.com/tonkonozhenko-mi/ai_private_workspace/releases"><img src="https://img.shields.io/github/downloads/tonkonozhenko-mi/ai_private_workspace/total?style=flat-square&color=2ea44f" alt="Downloads"></a>
  <a href="https://github.com/tonkonozhenko-mi/ai_private_workspace/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/tonkonozhenko-mi/ai_private_workspace/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <a href="#install-and-first-run"><img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg?style=flat-square" alt="Platform: macOS | Windows"></a>
  <a href="#safety-model"><img src="https://img.shields.io/badge/local--first-no%20cloud-2ea44f.svg?style=flat-square" alt="Local-first, no cloud"></a>
</p>

<p align="center">
  <a href="https://www.bestpractices.dev/projects/13357"><img src="https://www.bestpractices.dev/projects/13357/badge" alt="OpenSSF Best Practices"></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/tonkonozhenko-mi/ai_private_workspace"><img src="https://img.shields.io/ossf-scorecard/github.com/tonkonozhenko-mi/ai_private_workspace?style=flat-square&label=OpenSSF%20Scorecard" alt="OpenSSF Scorecard"></a>
  <a href="https://www.codefactor.io/repository/github/tonkonozhenko-mi/ai_private_workspace"><img src="https://www.codefactor.io/repository/github/tonkonozhenko-mi/ai_private_workspace/badge" alt="CodeFactor"></a>
  <a href="https://api.reuse.software/info/github.com/tonkonozhenko-mi/ai_private_workspace"><img src="https://api.reuse.software/badge/github.com/tonkonozhenko-mi/ai_private_workspace" alt="REUSE compliance"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache_2.0-blue.svg?style=flat-square" alt="License: Apache 2.0"></a>
</p>

**AI Private Workspace** is a local-first desktop app (macOS and Windows) for
understanding your own projects. Point it at a folder and ask anything — about
your code, infrastructure, CI/CD, or docs. **It reads, explains, and helps you
understand; it does not change your project.** Once the local model is downloaded
it runs fully offline and grounds every answer in your real files. Nothing leaves
your computer.

### ⬇️ [Download the latest release](https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/latest)

macOS (Apple Silicon / Intel) and Windows x64 installers are on the
[releases page](https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/latest).

> This README and [CHANGELOG](CHANGELOG.md) track the `main` branch, which is
> usually ahead of the latest tagged release. For a stable build, download from
> the releases page; to try the newest work, build from source.

<p align="center">
  <img src="docs/assets/screenshots/01-ask.png" alt="Ask a question about your project and get an answer grounded in local sources" width="820">
</p>

## Contents

- [First launch (unsigned app)](#first-launch-unsigned-app)
- [Install and first run](#install-and-first-run)
- [What it does](#what-it-does)
- [Project intelligence and read-only analysis](#project-intelligence-and-read-only-analysis)
- [Local engines](#local-engines)
- [How search works](#how-search-works)
- [Safety model](#safety-model)
- [Main product flows](#main-product-flows)
- [Troubleshooting](#troubleshooting)
- [Current status](#current-status)
- [Repository layout](#repository-layout)
- [Developer startup](#developer-startup)
- [Validation](#validation)
- [Contributing](#contributing)
- [License](#license)

## First launch (unsigned app)

The app isn't code-signed with a paid certificate yet, so both systems show a
one-time warning for unsigned downloaded apps. It's the standard prompt, not a
problem with the app.

**Windows.** SmartScreen may say "Windows protected your PC." Click **More info →
Run anyway**.

**macOS.** It may say the app "is damaged and can't be opened." It is not
damaged — macOS just blocks unsigned downloaded apps. After dragging it into
**Applications**, run this once in Terminal, then open it normally:

```bash
xattr -cr "/Applications/AI Private Workspace.app"
```

On a managed/work machine (configuration profile / MDM), this may be blocked by
IT policy; there the app needs to be signed/notarized or deployed through your
organization's device management.

## Install and first run

From the download to your first answer — eight steps, every one of them on your
own Mac (no cloud, no accounts):

<table>
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/step-1-install.png" alt="Drag the app into the Applications folder" width="100%"><br><sub><b>1 · Install</b> — open the downloaded <code>.dmg</code> and drag <b>AI Private Workspace</b> into <b>Applications</b>.</sub></td>
    <td width="50%"><img src="docs/assets/screenshots/step-2-welcome.png" alt="Local-first welcome screen" width="100%"><br><sub><b>2 · Welcome</b> — launch it and click <b>Open a project folder</b>. Your files stay on your computer.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/step-3-create-workspace.png" alt="Create a local workspace and choose a role lens" width="100%"><br><sub><b>3 · Create a workspace</b> — name it, pick the folder, choose a role lens (DevOps, Developer, Tester, BA…) and whether the project is remembered.</sub></td>
    <td width="50%"><img src="docs/assets/screenshots/step-4-scan.png" alt="Scan your project files locally" width="100%"><br><sub><b>4 · Scan</b> — a quick local pass lists your files so the AI knows what it can search. Nothing leaves the Mac.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/step-5-engine.png" alt="Choose a local engine and download models" width="100%"><br><sub><b>5 · Choose an engine</b> — built-in <b>llama.cpp</b> (nothing to install) or <b>Ollama</b>. Downloads two small local models (answer + search), then <b>Start engine</b>.</sub></td>
    <td width="50%"><img src="docs/assets/screenshots/step-6-build-context.png" alt="Build local search context (RAG index)" width="100%"><br><sub><b>6 · Build context</b> — turn the scanned files into a searchable local index so answers come from your real project.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/step-7-folder-access.png" alt="macOS folder access permission prompt" width="100%"><br><sub><b>7 · Grant folder access</b> — macOS asks once before the app reads your folder. Click <b>Allow</b>.</sub></td>
    <td width="50%"><img src="docs/assets/screenshots/step-8-ask.png" alt="Ask questions and get answers grounded in your project" width="100%"><br><sub><b>8 · Ask</b> — ask about your code, infra, CI/CD, or setup. Answers cite sources from your project and stay on your computer.</sub></td>
  </tr>
</table>

The app also follows your system light/dark preference:

<p align="center">
  <img src="docs/assets/screenshots/06-dark-ask.png" alt="Ask screen in dark theme" width="720">
</p>

## A few more screens

<table>
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/14-command-palette.png" alt="Command palette: jump to any repo, group, section or file" width="100%"><br><sub><b>Command palette</b> — <code>Cmd/Ctrl-K</code> to jump to any repository, group, section, or file.</sub></td>
    <td width="50%"><img src="docs/assets/screenshots/13-security.png" alt="Security lens: scanners in CI and security-relevant findings" width="100%"><br><sub><b>Security lens</b> — which scan/audit steps run in CI, plus the security-relevant findings, each backed by a file.</sub></td>
  </tr>
</table>

> Screenshots are taken on a demo project and any project names, file paths, and contributor details are redacted.

## What it does

- **Understands your project.** Point it at a folder; a local scan recognizes what's there — Terraform, Terragrunt, Kubernetes, Helm, Docker, Python, GitLab CI, docs, and more.
- **Searches only when you ask.** The local index is built on an explicit action and respects your `.gitignore`, so virtualenvs, build output, caches, and `.env` secrets never enter it.
- **Answers from your files.** Responses are grounded in retrieved sources with citations — not guesses — and your conversations, history, model choices, and reports stay on your computer.
- **Groups several repositories into one project.** Real systems span more than one repo. A group lets Ask, Home, and Intelligence work across a whole portfolio at once — environments compared in a repo×environment matrix, technologies split into shared-vs-unique, and risks grouped by pattern — while each repo stays an independent workspace underneath.
- **Built to navigate.** A **Cmd/Ctrl-K command palette** jumps to any repository, group, section, or file. Click a file anywhere and a **file inspector** opens its owner, what it changes together with, what it connects to in the map, and the risks touching it.
- **Runs on two local engines.** Built-in **llama.cpp** (nothing to install) or **Ollama**, switchable per project, with the answer and search models managed separately. See [Local engines](#local-engines).
- **Writes nothing without consent.** Ask can turn an answer into a file draft, written only after you confirm the path and exact content. Nothing else runs on its own — the app reads and explains, it never executes commands or changes your machine.

## Project intelligence and read-only analysis

Beyond search, the app builds a **map of your project** and gives you several
read-only tools over it. The guiding principle is the same throughout: every
statement is backed by something in your own files, the facts are produced
deterministically wherever possible, and the analysis is **read-only by
construction** — it looks and explains, it never writes files, runs commands, or
changes anything on your computer.

- **Project Intelligence** — a role-neutral evidence graph with an interactive **Map**, **role lenses** (Developer / DevOps / Tester / Business analyst) and an adaptive role dashboard, a **CI/CD flow** view, **Cloud** & **References** tabs, environment comparison and deployment flow.
- **Security review** — which scan/audit steps already run in CI and which findings are security-relevant, each with a recommendation and its source file. It reports on scanners; it never runs one.
- **Project activity & file inspector** — a read-only briefing from git history (activity, ownership, branch strategy, change coupling) and a per-file lens (owner, what it changes together with, its blast radius, the risks touching it).
- **Project groups** — treat several repositories as one project: group **Ask**, a portfolio **Home**, and group **Intelligence** that *compares rather than merges*.
- **Memory & profile** — local, fully-editable project memory + handbook and a cross-project **"About you"** profile, with **review-first** capture.
- **The Watcher & change history** — deterministic *"what changed since I last looked?"*, kept as a dated, date-grouped **History** journal you can revisit (filled cheaply from git), with an optional one-tap LLM recap of the commits.
- **Stays current** — when files change, refresh the model's knowledge with an **incremental re-index** that re-embeds only the files whose content changed (by hash, not the whole repo). Then just ask *"what changed today?"* in **Ask** — it pulls the dated change journal into the answer.
- **The Investigator** — a bounded **ReAct** loop over read-only tools that answers multi-step questions with a transparent trace and the sources it consulted.

Every finding reads as a lead for a human, not a verdict: what was found, **why it
may matter**, where (one click to the inspector), and **what to check yourself**.

**Full detail** — each tool, the Investigator's toolbox and ReAct protocol, the
trust guarantees, and example questions — lives in
[`docs/PROJECT_INTELLIGENCE.md`](docs/PROJECT_INTELLIGENCE.md).

## Local engines

Everything runs locally — no cloud, no accounts — on whichever engine you prefer,
chosen per project and switchable at any time before indexing:

- **Built-in llama.cpp** — the app bundles `llama-server` and runs GGUF models
  with **nothing to install**. Add any model straight from a Hugging Face repo
  and the app resolves a sensible quant for you. Best for a zero-setup start.
- **Ollama** — if you already use Ollama, point the app at it and keep your
  existing models and tags. Best if you live in the Ollama ecosystem.

Both paths are first-class: the same setup flow, model manager, answer metrics
(real token counts, generation speed, and context-window usage), and a live RAM
indicator work identically. The answer model and the search (embedding) model are
managed separately, so you can mix a strong answer model with a small, fast
embedder.

The **bundled llama.cpp** path also unlocks engine features Ollama doesn't expose
to us: it starts with **Flash Attention** (faster generation, smaller KV cache),
keeps a **warm prompt-prefix cache on disk**, can constrain answers to a
**JSON Schema** (guaranteed-parseable output for agents), and reports **exact
token counts** so the context-window budget is precise rather than estimated.
These are best-effort and degrade gracefully — startup falls back to safe
defaults if a build doesn't support a flag. Tunables: `AI_WORKSPACE_LLAMA_FLASH_ATTN`
(default on) and `AI_WORKSPACE_LLAMA_PARALLEL` (default `1`).

## How search works

Answers are grounded in your project through a **hybrid retrieval** pipeline —
the same approach used by strong production RAG systems, running fully on your
machine:

- **Dense vector search** — your question and every chunk are embedded; the
  closest chunks by cosine similarity are retrieved. Great for meaning and
  paraphrase, but weak at exact names.
- **Keyword search (BM25)** — a full-text index (SQLite FTS5) over the chunk text
  **and its file path**, so exact identifiers — folder names like `dev`, variable
  names like `<project name>_allowed_cidr` — are matched literally, which pure vector search
  misses.
- **Reciprocal Rank Fusion (RRF)** — merges the vector and keyword rankings
  without having to normalize their very different score scales.
- **Path / environment boost** — chunks whose file-path segments match query
  terms (e.g. `dev`, `<project name>`) are lifted, so environment-specific questions land on
  the file under that path instead of a similarly-worded one elsewhere.
- **Per-file diversity** — one large file can't fill the whole answer, so results
  span more of the codebase.

It degrades gracefully: if keyword indexing is unavailable it falls back to
vector-only search. On the roadmap: a cross-encoder **reranker** for an extra
precision pass.

## How it all connects

The end-to-end flow at a glance:

![AI Private Workspace flow](docs/assets/product-flow.svg)

> Capturing the screenshots above? See [`docs/assets/screenshots/CAPTURE_GUIDE.md`](docs/assets/screenshots/CAPTURE_GUIDE.md) for the exact shots and file names.

## Safety model

AI Private Workspace is designed around explicit user control:

- The frontend never executes shell commands.
- App launch never starts scans, indexing, rebuilds, or model downloads.
- Model download execution is disabled by default and must be enabled backend-side in trusted local runtime only.
- The local analysis is read-only — it never executes commands or modifies files.
- Approval gates record user intent; they do not execute anything automatically.
- Ask never writes a generated file automatically. The user must open the review panel and explicitly create it.
- Runtime data, local databases, caches, and build artifacts are excluded from source archives.

## Main product flows

The frontend keeps the common workflows focused and progressively reveals technical detail:

- **Ask** answers from workspace context and can prepare a safe, editable file draft.
- **Models** separates Overview, Choose & install, Compare, and Tuning.
- **Choose & install** uses backend-provided recommendations and accepts custom
  Ollama model tags. A desktop-owned backend can safely run the exact approved
  `ollama pull <model>` job, while browser development keeps downloads disabled
  unless explicitly configured.
- **Tuning** holds per-model answer settings, while **Compare** runs explicit model comparisons. The single editable **Skills** library lives in **Settings** (one place to edit or create skills, picked per question in Ask).
- **Settings** shows a plain-language readiness checklist for the local backend, project scan, search context, and local AI.

## Troubleshooting

**Windows — "Windows protected your PC" (SmartScreen).** The app isn't
code-signed yet, so Windows warns on first launch. Click **More info → Run
anyway**. It's the standard prompt for unsigned apps, not a problem with the app.

**macOS — "AI Private Workspace is damaged and can't be opened".** Not damaged —
macOS blocks unsigned downloaded apps. After dragging it into **Applications**,
run this once in Terminal, then open it normally:

```bash
xattr -cr "/Applications/AI Private Workspace.app"
```

**The app won't start / "backend startup failed".** Check the logs and attach
them to a bug report:

- macOS: `~/Library/Application Support/AI Private Workspace/logs/`
- Windows: `%LOCALAPPDATA%\AI Private Workspace\logs\`

`backend.log` has the engine's own output; `desktop-supervisor.log` shows what the
launcher searched for.

**Which engine should I pick?** Use **built-in llama.cpp** for a zero-setup start
(nothing to install). Choose **Ollama** if you already use it and want your
existing models. You can switch per project before the index is built.

**Answers ignore my files.** Make sure you ran **Build context** after scanning —
answers are grounded only once the local index exists. Changing the embedding
(search) model requires rebuilding the index, since it creates a different vector
space.

## Current status

Pre-1.0 and actively developed. Each tagged release builds from CI into
signed-per-architecture macOS DMGs (Apple Silicon + Intel) and a Windows x64
installer, with in-app auto-update. The app is usable day to day on both local
engines; the road to 1.0 focuses on code signing (so there's no SmartScreen /
Gatekeeper warning) and broader QA.

Every release also publishes **SHA256 checksums** (`SHA256SUMS.txt`), an **SPDX
SBOM** (`sbom.spdx.json`) of the bundled dependencies, and an **automated-test
report** (`TEST-REPORT.md`) of what actually ran — so you can verify what you
download.

The backend is covered by a deterministic test suite (600+ tests over the domain,
use cases, and API), run on every push and pull request. Each CI run renders a
pass/fail summary on its page and attaches the JUnit results, so the test state is
visible at a glance rather than buried in logs.

See:

- [Roadmap](docs/ROADMAP.md)
- [Start here](docs/START_HERE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [v1 product completion roadmap](docs/V1_PRODUCT_COMPLETION_ROADMAP.md)

## Repository layout

```text
backend/     FastAPI backend, domain services, adapters, tests
frontend/    React/Vite UI
docs/        product, architecture, release, and packaging docs
scripts/     local runtime, audit, packaging, and release helper scripts
assets/      brand assets (app icons, logos)
.github/     CI workflows and contribution templates
```

## Developer startup

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

For the current macOS developer-safe launcher:

```bash
chmod +x scripts/launch_macos.command scripts/create_macos_shortcut.sh
./scripts/launch_macos.command
```

For the desktop app bundle, double-click `Open AI Private Workspace.command` in
the repository root. It rebuilds the packaged app when tracked application
sources changed since the last successful build, otherwise it opens the
existing app immediately and brings its window to the front.
When an update is detected while the app is already open, the launcher
smoke-checks the new backend on an isolated port, then asks the known app bundle
to close cleanly before opening the updated build. It never force-kills an
unknown process.

If the launcher cannot build or open the app, it keeps the Terminal window open
and points to `build/desktop/open-ai-private-workspace.log`. The packaged app
backend also writes diagnostics to:

```text
~/Library/Application Support/AI Private Workspace/logs/
```

### Use your own models

Bring a different answer model on either engine. It is managed separately from
the search (embedding) model, so you can pair a strong answer model with a small,
fast embedder.

**Ollama** — open **Models → Choose & install**, pick **Custom Ollama model**,
enter the exact tag (e.g. `deepseek-r1:1.5b`), and choose **Use this AI answer
model**. If Ollama already has it, it is marked ready; if not, and the desktop
download worker is enabled, the app runs a narrowly validated `ollama pull`.
Models you pulled yourself in Terminal appear as detected installs, so the app
never claims it downloaded them.

**Built-in llama.cpp** — open **Models** and, under **Add a model**, paste a
Hugging Face **GGUF** repo (e.g. `bartowski/Qwen2.5-0.5B-Instruct-GGUF`). The app
picks a sensible quant for you, downloads it, and switches the engine — no
filename hunting. Your choice persists across restarts.

Changing the embedding (search) model creates a different vector space, so it
always requires an explicit context rebuild.

## Validation

Run the release audit from the repository root:

```bash
./scripts/audit_release_candidate.sh
```

Run focused backend checks:

```bash
cd backend
pytest -q tests/test_final_product_status.py tests/test_product_completion_roadmap.py tests/test_release_candidate_audit.py tests/test_release_candidate_audit_script.py tests/test_source_release_archive_script.py tests/test_api_inventory.py
```

Run frontend validation:

```bash
cd frontend
npm ci
npm run build
```

Create a clean source archive:

```bash
./scripts/prepare_source_release_archive.sh
```

The generated archive is written to `build/release/` and must not be committed.

## Runtime data policy

Do not commit:

- `backend/.ai-workbench/`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `.pytest_cache/`
- `__pycache__/`
- `*.db`, `*.sqlite`, `*.sqlite3`

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the
product principles, development flow, and source-hygiene rules before opening a
pull request. Security issues should follow [SECURITY.md](SECURITY.md) — please
report them privately rather than in a public issue.

## License

Licensed under the [Apache License 2.0](LICENSE). You are free to use, modify,
and distribute this software, including in commercial and enterprise settings.
Apache-2.0 was chosen so companies can adopt the product without the legal
friction that more restrictive copyleft licenses introduce.
