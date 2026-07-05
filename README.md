<p align="center">
  <img src="assets/brand/logos/pigeon-mark.png" alt="AI Private Workspace" width="160">
</p>

<h1 align="center">AI Private Workspace</h1>

<p align="center"><b>Understand any project in an hour — privately.</b><br>
Point it at a folder and ask anything about the code, infrastructure, CI/CD, or docs.<br>
Runs fully offline on a local model. Every answer cites your real files. Nothing leaves your computer.</p>

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

<p align="center">
  <a href="https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/latest"><b>⬇️ Download for macOS (Apple Silicon / Intel) and Windows x64</b></a>
</p>

<p align="center">
  <img src="docs/assets/demo.gif" alt="From an empty folder to a grounded answer in 35 seconds: create a workspace, scan, build context, ask — and get an answer with sources from your own files" width="820">
</p>

<p align="center"><sub>Real recording on a demo project: folder → scan → local engine → index → first answer with sources. ~35s, fully offline.</sub></p>

## Why

- **Private by construction.** No cloud, no accounts, no telemetry. Once the local
  model is downloaded it runs fully offline — safe for NDA and client projects
  where cloud AI tools are off the table.
- **Understands the project, not just the files.** A local scan recognizes
  Terraform, Kubernetes, Helm, Docker, CI pipelines, docs and more, then builds an
  evidence-backed map with role lenses for developers, DevOps, testers, BAs, and
  managers — not only engineers.
- **Answers you can verify.** Every reply is grounded in retrieved sources with
  citations, a deterministic groundedness check flags unsupported claims, and the
  model abstains honestly instead of inventing details. It reads and explains —
  it never changes your project.

## Install and first run

1. **[Download the installer](https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/latest)** and open it (drag to Applications on macOS).
2. **Open a project folder** — create a workspace and run the quick local scan.
3. **Pick an engine** — built-in llama.cpp (nothing to install) or Ollama — and let it fetch two small local models (~2.5 GB, then fully offline).
4. **Build context** and ask your first question.

The full illustrated walkthrough lives in
[`docs/INSTALL_WALKTHROUGH.md`](docs/INSTALL_WALKTHROUGH.md).

<details>
<summary><b>First launch on an unsigned build (one-time warning)</b></summary>

The app isn't code-signed with a paid certificate yet, so both systems show the
standard warning for unsigned downloaded apps — it's not a problem with the app.

**Windows.** SmartScreen may say "Windows protected your PC." Click **More info →
Run anyway**.

**macOS.** It may say the app "is damaged and can't be opened." It is not
damaged — macOS blocks unsigned downloaded apps. After dragging it into
**Applications**, run this once in Terminal, then open it normally:

```bash
xattr -cr "/Applications/AI Private Workspace.app"
```

On a managed/work machine (MDM), this may be blocked by IT policy; there the app
needs to be signed/notarized or deployed through your organization's device
management.
</details>

## What it does

- **Understands your project.** Point it at a folder; a local scan recognizes what's there — Terraform, Terragrunt, Kubernetes, Helm, Docker, Python, GitLab CI, docs, and more.
- **Searches only when you ask.** The local index is built on an explicit action and respects your `.gitignore`, so virtualenvs, build output, caches, and `.env` secrets never enter it.
- **Answers from your files.** Responses are grounded in retrieved sources with citations — and your conversations, history, model choices, and reports stay on your computer.
- **Groups several repositories into one project.** Ask, Home, and Intelligence work across a whole portfolio — environments compared in a repo×environment matrix, technologies split into shared-vs-unique, risks grouped by pattern.
- **Built to navigate.** A **Cmd/Ctrl-K command palette** jumps to any repository, group, section, or file; a **file inspector** shows each file's owner, change coupling, connections, and risks.
- **Runs on two local engines.** Built-in **llama.cpp** or **Ollama**, switchable per project, with the answer and search models managed separately.
- **Writes nothing without consent.** Ask can turn an answer into a file draft, written only after you confirm the path and exact content. Nothing else runs on its own.

## Project intelligence

Beyond search, the app builds a **map of your project** with read-only tools over
it: role lenses and an adaptive dashboard, a CI/CD flow view, environment
comparison, a security review (which scanners already run in CI and which
findings matter, each backed by a file), git activity and per-file inspection,
provable self-maintaining **project memory** with guardrails, **answer modes**
that control how strictly a reply sticks to your files, a deterministic
groundedness check, a dated change journal ("what changed since I last
looked?"), incremental re-indexing by content hash, and **the Investigator** — a
bounded ReAct loop over read-only tools with a transparent trace.

Every finding reads as a lead for a human, not a verdict: what was found, why it
may matter, where, and what to check yourself. Full detail:
[`docs/PROJECT_INTELLIGENCE.md`](docs/PROJECT_INTELLIGENCE.md).

## How search works

Answers are grounded through **hybrid retrieval** running fully on your machine:
dense vector search for meaning, BM25 keyword search (SQLite FTS5) over chunk
text *and* file paths for exact identifiers, Reciprocal Rank Fusion to merge the
rankings, a path/environment boost so `dev`-specific questions land on `dev`
files, per-file diversity so one file can't fill the whole answer, and an
optional cross-encoder reranker ("Sharper search"). It degrades gracefully to
vector-only search if keyword indexing is unavailable.

## Local engines

Everything runs locally on whichever engine you prefer, chosen per project:

- **Built-in llama.cpp** — bundled `llama-server`, zero setup. Paste any Hugging
  Face **GGUF** repo under **Models → Add a model** and the app resolves a
  sensible quant, downloads it, and switches the engine. Unlocks Flash
  Attention, a warm prompt-prefix cache, JSON-Schema-constrained output, and
  exact token counts.
- **Ollama** — point the app at your existing Ollama and keep your models and
  tags. Models you pulled yourself appear as detected installs.

Both paths share the same setup flow, model manager, answer metrics, and RAM
indicator. The answer model and the search (embedding) model are managed
separately; changing the embedding model always requires an explicit context
rebuild.

## Safety model

- The frontend never executes shell commands.
- App launch never starts scans, indexing, rebuilds, or model downloads.
- Model download execution is disabled by default and must be enabled backend-side in trusted local runtime only.
- The local analysis is read-only — it never executes commands or modifies files.
- Ask never writes a generated file automatically; the user must explicitly create it from the review panel.
- Runtime data, local databases, caches, and build artifacts are excluded from source archives.

## Troubleshooting

**"Windows protected your PC" / "app is damaged"** — see
[First launch on an unsigned build](#install-and-first-run) above.

**The app won't start / "backend startup failed".** Check the logs and attach
them to a bug report: macOS
`~/Library/Application Support/AI Private Workspace/logs/`, Windows
`%LOCALAPPDATA%\AI Private Workspace\logs\`.

**Which engine should I pick?** Built-in **llama.cpp** for a zero-setup start;
**Ollama** if you already use it. You can switch per project before the index is
built.

**Answers ignore my files.** Run **Build context** after scanning — answers are
grounded only once the local index exists.

## Current status

Pre-1.0 and actively developed; usable day to day on both engines. Each tagged
release builds from CI into macOS DMGs (Apple Silicon + Intel) and a Windows x64
installer with in-app auto-update, and publishes **SHA256 checksums**, an **SPDX
SBOM**, and an **automated-test report** so you can verify what you download.
The backend is covered by a deterministic suite of 600+ tests run on every push.
The road to 1.0 focuses on code signing and broader QA.

- [Roadmap](docs/ROADMAP.md) · [Start here](docs/START_HERE.md) · [Architecture](docs/ARCHITECTURE.md) · [v1 completion roadmap](docs/V1_PRODUCT_COMPLETION_ROADMAP.md)

## Repository layout

```text
backend/     FastAPI backend, domain services, adapters, tests
frontend/    React/Vite UI
docs/        product, architecture, release, and packaging docs
scripts/     local runtime, audit, packaging, and release helper scripts
assets/      brand assets (app icons, logos)
.github/     CI workflows and contribution templates
```

Developer setup, validation commands, and source-hygiene rules:
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Contributing

Contributions are welcome — read [CONTRIBUTING.md](CONTRIBUTING.md) for the
product principles and development flow. Security issues should follow
[SECURITY.md](SECURITY.md): please report them privately rather than in a
public issue.

## License

Licensed under the [Apache License 2.0](LICENSE). You are free to use, modify,
and distribute this software, including in commercial and enterprise settings —
Apache-2.0 was chosen so companies can adopt the product without legal friction.
