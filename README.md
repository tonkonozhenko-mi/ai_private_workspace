# AI Private Workspace

**AI Private Workspace** is a local-first AI workspace for understanding private projects without sending source code to external AI services by default.

It combines project scanning, local context indexing, Ollama-based models, report generation, safe agent planning, MCP readiness, and desktop packaging foundations for macOS and Windows.

![AI Private Workspace product flow](docs/assets/product-flow.svg)

## What it does

- Creates local workspaces from project folders.
- Detects technologies such as Terraform, Kubernetes, Docker, Python, Helm, GitHub/GitLab CI, and documentation.
- Builds local searchable context for RAG-style answers.
- Uses local Ollama models when configured.
- Keeps conversations, reports, model preferences, and workspace status locally.
- Provides safe Agent + MCP planning foundations without automatic tool execution.
- Includes macOS and Windows packaging foundations for future two-click desktop releases.

## Current release status

This repository is a **v0.1 source release candidate**.

It is ready for local development, demo, review, and GitHub publication. It is not yet a signed commercial desktop installer. The real installer-grade roadmap is documented in [`docs/V1_PRODUCT_COMPLETION_ROADMAP.md`](docs/V1_PRODUCT_COMPLETION_ROADMAP.md).

## Safety principles

AI Private Workspace is designed around explicit user control:

- The frontend never executes shell commands.
- Scan, index, rebuild, model download, MCP, and agent execution are explicit user actions.
- Model download execution is backend-side, opt-in, allowlisted, and disabled by default.
- MCP servers and tools do not start automatically.
- Agent workflows are planning/manual-tracking first.
- Project claims in Ask responses should be based on retrieved local sources.

## Repository layout

```text
backend/      FastAPI backend, clean architecture, tests
frontend/     React/Vite UI and Tauri scaffold
scripts/      local start, audit, source release, packaging foundation scripts
docs/         architecture, roadmap, release, model, MCP, packaging docs
.github/      CI, desktop checks, issue templates, PR template
```

## Quick start for local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Then open the Vite URL shown in the terminal.

## Recommended demo flow

1. Create a workspace from a local project folder.
2. Scan the project.
3. Open **Models** and choose local AI/search models.
4. Build context with the selected search model.
5. Ask a grounded question about the workspace.
6. Generate a report.
7. Review Agent/MCP planning screens without enabling execution.
8. Run the release audit before publishing.

More detail: [`docs/V01_DEMO_HANDOFF.md`](docs/V01_DEMO_HANDOFF.md).

## Validation

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q

cd ../frontend
npm ci
npm run build
```

Create a clean source archive:

```bash
./scripts/prepare_source_release_archive.sh
```

The archive is written under `build/release/` and should not be committed.

## Desktop packaging direction

The final target is:

```text
download package → double click → local backend starts → UI opens → work locally
```

Current repository status:

- macOS `.app` foundation exists.
- Tauri shell scaffold exists.
- Windows packaging foundation exists.
- Backend runtime bundle readiness exists.
- Signed `.dmg` / `.msi` installers and frozen backend binaries are future v1 work.

Start here for packaging details:

- [`docs/DESKTOP_PACKAGING_DESIGN_LOCK.md`](docs/DESKTOP_PACKAGING_DESIGN_LOCK.md)
- [`docs/MACOS_APP_PACKAGE_FOUNDATION.md`](docs/MACOS_APP_PACKAGE_FOUNDATION.md)
- [`docs/WINDOWS_PACKAGING_FOUNDATION.md`](docs/WINDOWS_PACKAGING_FOUNDATION.md)

## GitHub publication

Before pushing publicly, run:

```bash
git status --short
./scripts/audit_release_candidate.sh
./scripts/prepare_source_release_archive.sh
```

Do not commit runtime/build data:

- `backend/.ai-workbench/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `.pytest_cache/`

See [`docs/GITHUB_PUBLICATION_CHECKLIST.md`](docs/GITHUB_PUBLICATION_CHECKLIST.md).
