# AI Private Workspace

[![CI](https://github.com/tonkonozhenko-mi/ai_private_workspace/actions/workflows/ci.yml/badge.svg)](https://github.com/tonkonozhenko-mi/ai_private_workspace/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#installing-on-macos-first-launch)
[![Local-first](https://img.shields.io/badge/local--first-no%20cloud-2ea44f.svg)](#safety-model)

**AI Private Workspace** is a local-first desktop-oriented workspace for private project onboarding, local RAG, model management, project reports, and safe Agent/MCP planning.

The v0.1 release candidate is a source handoff for developers and reviewers. It is not yet a signed installer-grade product.

![AI Private Workspace flow](docs/assets/product-flow.svg)

## Contents

- [Installing on macOS](#installing-on-macos-first-launch)
- [What it does](#what-it-does)
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

## What it does

- Creates local workspaces for private projects.
- Scans source folders and detects skills such as Terraform, Terragrunt, Kubernetes, Helm, Docker, Python, GitLab CI, and documentation.
- Builds local search context only after explicit user action.
- Answers questions from retrieved project sources instead of unsupported guesses.
- Keeps conversations, answer history, model choices, reports, and timeline state locally.
- Guides local Ollama/model setup and detects installed local models.
- Remembers custom Ollama model tags and enriches them from the local Ollama
  installation with size, parameter, quantization, and capability metadata.
- Provides safe model download drafts and backend-owned download jobs behind explicit approval.
- Provides working workspace model presets, comparisons, and an MCP registry with explicit approval planning.
- Lets Ask turn an answer into a reviewed project-file draft; a file is written only after the user confirms its relative path, exact content, and overwrite intent.
- Provides Agent and MCP planning UX without automatic tool execution.
- Includes macOS, Windows, and Tauri packaging foundations for future installer-grade releases.

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
