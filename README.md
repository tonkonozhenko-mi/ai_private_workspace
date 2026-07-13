<p align="center">
  <img src="assets/brand/logos/pigeon-mark.png" alt="AI Private Workspace" width="160">
</p>

<h1 align="center">AI Private Workspace</h1>

<p align="center"><b>Understand a project you've just inherited — in an hour, fully offline.</b><br>
Point it at a folder — code, Terraform, an exported wiki, documents — and ask anything.<br>
Every answer cites your real files. When it doesn't know, it says so. Nothing leaves your computer.</p>

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

## The day you inherit a project

Someone hands you a repository, a Terraform monorepo, or a 200-page Confluence
export — and expects you to be useful this week. This app is built for that day:

- **Ask in your own words** — "How is this deployed, and to which environments?",
  "Where is the orders table defined?", "What did we decide about storage, and
  where is it implemented?" — and get an answer with the files it came from.
- **See the map** — what the project is made of, how code reaches production,
  how environments differ, where the risks sit — every statement backed by a
  file, none of it written by a model.
- **Trust the "I don't know"** — when your files don't contain the answer, it
  says so instead of inventing one. That property is measured, not promised
  (see the numbers below).

It works on a code repository, a wiki export, a folder of documents — or a
**group of them together**: ask "what did we decide, and where is it
implemented?" and the answer carries the decision from the wiki and the
implementation from the repo, each source labelled.

## Why it's safe for work projects

- **Private by construction.** No cloud, no accounts, no telemetry. After the
  one-time model download it runs fully offline — usable on NDA and client
  projects where cloud AI tools are off the table.
- **Read-only by design.** It reads and explains; it never changes your project,
  never runs commands on its own, and never writes a file without your explicit
  confirmation.
- **Verifiable.** Every reply cites sources; a deterministic groundedness check
  flags unsupported claims in the UI instead of hiding them.

## Measured, not promised

A 40-question golden-set benchmark runs the real pipeline end to end
([`backend/eval/`](backend/eval/README.md)); its deterministic parts are gated
in CI. Current numbers with the default models (temperature 0, this repository
as the corpus):

| What is measured | Result |
|---|---:|
| The right file is in the sources (hit@5, questions with a known answer file) | **95%** |
| Project questions wrongly refused | **0%** |
| Off-topic questions correctly get no project sources | **100%** |
| Answers carrying grounding warnings — raw model → after self-correction | **6.7% → 3.3%** |

The last row is the one to read twice: when the deterministic grounding check
flags a fresh answer, one corrective pass halves the failure rate — the safety
net is a measured mechanism, not a claim. Reproduce it yourself:
`python -m eval.golden --embedder nomic --with-generation` (from `backend/`).

## Install and first run

1. **[Download the installer](https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/latest)** and open it (drag to Applications on macOS).
2. **Open a project folder** — create a workspace, say who you are on this project (developer, DevOps, tester, manager, BA, DBA — it shapes what leads, never what is true), and run the quick local scan.
3. **Pick an engine** — built-in llama.cpp (nothing to install) or Ollama — and let it fetch two small local models (a few GB, then fully offline).
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

## What it reads

Everything a real project is made of — not only the files a compiler would
accept. A local scan recognizes Terraform, Kubernetes, CI, 30+ programming
languages, exported wikis, Word/PDF/Excel documents, diagrams, notebooks and
data files; a wiki's diagram is cited by the page it illustrates, and a
project is described by what it contains, never scolded for what it lacks.

<details>
<summary><b>Full format table</b></summary>

| Kind | Read as | Extensions |
| --- | --- | --- |
| Documents | text, section by section | `.docx` · `.pdf` · `.html` `.htm` · `.md` `.rst` `.txt` |
| Spreadsheets | sheet by sheet, cell values | `.xlsx` |
| Slide decks | one section per slide | `.pptx` |
| Diagrams | the labels on the boxes and arrows — the architecture, without a single pixel | `.drawio` |
| Tabular data | rows, with the header row kept on every chunk | `.csv` · `.tsv` |
| Notebooks | cell by cell, with cell numbers | `.ipynb` |
| Code | 30+ languages by extension (TypeScript, Go, Rust, Java, C/C++, C#, Ruby, PHP, Swift, Kotlin, Scala, Python…) | see [`source_files.py`](backend/app/core/domain/source_files.py) |
| Infrastructure & config | `.tf` `.hcl` · `.yaml` `.yml` · `.json` · `.toml` `.ini` `.cfg` · `Dockerfile` · `Makefile` · SQL |  |

**Images are recognised and honestly left unindexed** — a PNG of an architecture
diagram has no text to read without OCR, so the app tells you it exists and
attributes it to its page rather than pretending to have read it. Legacy `.doc`,
`.xls` and `.vsdx` are not read. Documents up to 20 MB; nothing is sent anywhere.
The index is built on an explicit action and respects your `.gitignore`, so
virtualenvs, build output, caches, and `.env` secrets never enter it.
</details>

## What you can do with it

- **Ask and verify.** Answers come with sources from your files; starter
  questions are built from your project's own map, so the first click already
  asks something useful.
- **Walk the map.** An adaptive dashboard leads with what matters for *your*
  role; every fact carries the question it raises — one click asks it. CI/CD
  flow, environment comparison, security review, git activity, per-file
  inspector, a dated "what changed since I last looked" journal.
- **Work across a portfolio.** Groups treat several projects as one — including
  mixed code + wiki, with environments compared in a repo×environment matrix
  and risks grouped by pattern.
- **Let it investigate.** The Investigator is a bounded agent over read-only
  tools whose steps stream live — you watch it think instead of waiting for a
  verdict.
- **Teach it your project.** Project memory keeps your corrections and feeds
  them into future answers — stored locally, always editable, never retraining
  anything.
- **Move fast.** Cmd/Ctrl-K palette jumps to any repo, section, or file; Ask
  can draft a file from an answer, written only after you confirm the path and
  content.

Full detail: [`docs/PROJECT_INTELLIGENCE.md`](docs/PROJECT_INTELLIGENCE.md).

## How it stays honest

This is the part that makes the answers trustworthy, so it stays visible:

- the relevance threshold is **calibrated per index** against the embedding
  model's own noise floor — below it, the app abstains instead of guessing;
- small talk is routed away from your files entirely; a small project that
  fits the model's window is read whole, so nothing relevant is missed;
- every answer passes a deterministic groundedness check; failures surface as
  visible warnings, and one **corrective pass** re-searches and regenerates —
  kept only if it's provably better.

<details>
<summary><b>Under the hood: the retrieval pipeline</b></summary>

Hybrid retrieval running fully on your machine: dense vector search for
meaning, BM25 keyword search (SQLite FTS5) over chunk text *and* file paths for
exact identifiers, a domain-synonym bridge (asking about
"Content-Security-Policy" finds the file that spells it `csp`), Reciprocal Rank
Fusion to merge the rankings, a path/environment boost so `dev`-specific
questions land on `dev` files, per-file diversity so one file can't fill the
whole answer, and an optional cross-encoder reranker ("Sharper search"). It
degrades gracefully to vector-only search if keyword indexing is unavailable.
Prompts are budgeted in tokens against the model's real context window — with
script-aware estimates, so a Ukrainian conversation is counted as honestly as
an English one.
</details>

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
The backend is covered by a deterministic suite of 1,000+ tests run on every push.
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
