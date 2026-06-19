# AI Private Workspace

[![CI](https://github.com/tonkonozhenko-mi/ai_private_workspace/actions/workflows/ci.yml/badge.svg)](https://github.com/tonkonozhenko-mi/ai_private_workspace/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#installing-on-macos-first-launch)
[![Local-first](https://img.shields.io/badge/local--first-no%20cloud-2ea44f.svg)](#safety-model)

**AI Private Workspace** is a local-first desktop-oriented workspace for private project onboarding, local RAG, model management, project reports, and safe Agent/MCP planning.

The v0.1 release candidate is a source handoff for developers and reviewers. It is not yet a signed installer-grade product.

<p align="center">
  <img src="docs/assets/screenshots/01-ask.png" alt="Ask a question about your project and get an answer grounded in local sources" width="820">
</p>

## Contents

- [Installing on macOS](#installing-on-macos-first-launch)
- [Install and first run](#install-and-first-run)
- [What it does](#what-it-does)
- [Local engines](#local-engines)
- [How search works](#how-search-works)
- [Safety model](#safety-model)
- [Main product flows](#main-product-flows)
- [Current status](#current-status)
- [Repository layout](#repository-layout)
- [Developer startup](#developer-startup)
- [Validation](#validation)
- [Contributing](#contributing)
- [License](#license)

## Installing on macOS (first launch)

The app is not signed with a paid Apple certificate yet, so on first launch macOS
may say the app "is damaged and can't be opened." It is not damaged — that is
just macOS blocking unsigned downloaded apps. After dragging the app into
**Applications**, run this once in Terminal to clear the download quarantine,
then open it normally:

```bash
xattr -cr "/Applications/AI Private Workspace.app"
```

On a managed/work Mac (one with a configuration profile), this may be blocked by
IT policy; in that case the app needs to be signed/notarized or deployed through
your organization's device management.

## Install and first run

From the download to your first answer — eight steps, every one of them on your
own Mac (no cloud, no accounts):

<table>
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/step-1-install.png" alt="Drag the app into the Applications folder" width="100%"><br><sub><b>1 · Install</b> — open the downloaded <code>.dmg</code> and drag <b>AI Private Workspace</b> into <b>Applications</b>.</sub></td>
    <td width="50%"><img src="docs/assets/screenshots/step-2-welcome.png" alt="Local-first welcome screen" width="100%"><br><sub><b>2 · Welcome</b> — launch it and click <b>Open a project folder</b>. It runs entirely offline.</sub></td>
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

## What it does

- Creates local workspaces for private projects.
- Scans source folders and detects skills such as Terraform, Terragrunt, Kubernetes, Helm, Docker, Python, GitLab CI, and documentation.
- Builds local search context only after explicit user action.
- Respects the project's own `.gitignore` when indexing, so virtualenvs, `node_modules`, build output, caches, and local `.env` secrets stay out of the local index — the same files you would not commit to git.
- Answers questions from retrieved project sources instead of unsupported guesses.
- Keeps conversations, answer history, model choices, reports, and timeline state locally.
- Runs entirely on one of two local engines — the **built-in llama.cpp** engine (nothing to install) or **Ollama** — and lets you switch between them per project. See [Local engines](#local-engines).
- Guides local model setup and detects installed local models.
- Remembers custom Ollama model tags and enriches them from the local Ollama
  installation with size, parameter, quantization, and capability metadata.
- Provides safe model download drafts and backend-owned download jobs behind explicit approval.
- Provides working workspace model presets, comparisons, and an MCP registry with explicit approval planning.
- Lets Ask turn an answer into a reviewed project-file draft; a file is written only after the user confirms its relative path, exact content, and overwrite intent.
- Provides Agent and MCP planning UX without automatic tool execution.
- Includes macOS, Windows, and Tauri packaging foundations for future installer-grade releases.

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
- App launch never starts scans, indexing, rebuilds, MCP servers, Agent workflows, or model downloads.
- Model download execution is disabled by default and must be enabled backend-side in trusted local runtime only.
- Agent workflows are planning/manual tracking only in v0.1.
- Approval gates record user intent; they do not execute tools automatically.
- Ask never writes a generated file automatically. The user must open the review panel and explicitly create it.
- Runtime data, local databases, caches, and build artifacts are excluded from source archives.

## Main product flows

The frontend keeps the common workflows focused and progressively reveals technical detail:

- **Ask** answers from workspace context and can prepare a safe, editable file draft.
- **Models** separates Overview, Choose & install, Skills, Compare, MCP tools, and Advanced configuration.
- **Choose & install** uses backend-provided recommendations and accepts custom
  Ollama model tags. A desktop-owned backend can safely run the exact approved
  `ollama pull <model>` job, while browser development keeps downloads disabled
  unless explicitly configured.
- **Skills** saves workspace model presets, while **Compare** runs explicit model comparisons.
- **MCP tools** provides an approval-first registry for creating, editing, enabling, disabling, and inspecting MCP server definitions. MCP tools are not executed automatically.
- **Settings** shows a plain-language readiness checklist for the local backend, project scan, search context, and local AI.

## Current status

- **v0.1 source release candidate:** nearly ready for GitHub publication after local verification.
- **v1.0 installer-grade product:** future stage. It still needs frozen backend runtime, signed macOS package, Windows installer, persistent jobs, sandboxed Agent/MCP execution, update flow, and final QA.

See:

- [Start here](docs/START_HERE.md)
- [v0.1 demo handoff](docs/V01_DEMO_HANDOFF.md)
- [v0.1 release notes](docs/V01_RELEASE_NOTES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [GitHub publication checklist](docs/GITHUB_PUBLICATION_CHECKLIST.md)
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

### Use a custom Ollama model

1. Open **Models → Choose & install**.
2. Choose **Custom Ollama model** and enter the exact Ollama tag, for example
   `deepseek-r1:1.5b`.
3. Select **Use this AI answer model**.

The app saves the workspace selection and custom model metadata. If Ollama
already has the model, the read-only Installed Models check marks it ready. If
it is missing and the packaged desktop download worker is enabled, the app
creates and starts a narrowly validated `ollama pull` job. Download history and
custom catalog metadata survive app restarts.
Models pulled directly in Terminal are shown separately as recent detected
Ollama installs, so the UI does not falsely claim that the app downloaded them.

The guided LLM choice also pairs the workspace with `nomic-embed-text` when no
embedding model has been selected yet. Changing the embedding model still
requires an explicit context rebuild because it creates a different vector
space.

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
