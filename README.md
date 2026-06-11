# AI Private Workspace

**AI Private Workspace** is a local-first AI workbench for project onboarding, codebase understanding, private RAG, local model management, documentation reports, and safe Agent/MCP planning.

The product goal is simple:

> Download the app, open it, choose a local project, build private context, and ask questions without uploading project data.

This repository currently contains the **v0.1 release candidate source handoff**. macOS and Windows desktop packaging foundations are present, but the final signed installers are still future work.

## What it does

- Creates local workspaces for project folders.
- Scans files and detects technologies such as Terraform, Python, Docker, Kubernetes, Helm, GitHub/GitLab CI, and documentation.
- Builds local search context for RAG-style answers.
- Lets the user ask questions grounded in local retrieved sources.
- Generates project reports and documentation drafts.
- Manages local Ollama models with safe backend-owned download jobs.
- Provides Agent/MCP planning flows without automatic tool execution.
- Includes macOS and Windows desktop packaging foundations.

## Safety model

- The frontend never executes shell commands.
- Scans, indexing, rebuilds, model downloads, MCP, and Agent workflows never start automatically.
- Model download execution is disabled by default and must be explicitly enabled in a trusted local runtime.
- MCP and Agent execution remain planning/manual tracking only until sandboxed execution exists.
- Runtime data is excluded from source archives.

## Repository layout

```text
backend/     FastAPI backend, core services, tests
frontend/    React UI and Tauri scaffold
docs/        Product, architecture, packaging, safety, and release docs
scripts/     Local startup, packaging foundation, audit, and safety scripts
```

## Start here

Read these first:

- [Start here](docs/START_HERE.md)
- [v0.1 demo handoff](docs/V01_DEMO_HANDOFF.md)
- [v0.1 release notes](docs/V01_RELEASE_NOTES.md)
- [Roadmap](docs/ROADMAP.md)
- [Release candidate audit](docs/RELEASE_CANDIDATE_AUDIT.md)

## Developer run

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Release audit:

```bash
./scripts/audit_release_candidate.sh
```

## Desktop packaging status

The target is not “clone repo and run scripts”. The target is:

```text
download package -> double click -> local backend starts -> UI opens
```

Current foundation:

- macOS `.app` foundation script exists.
- Windows packaging foundation exists.
- Tauri shell scaffold exists.
- Backend runtime bundling/freeze is planned but not final.
- Signed installers are not part of v0.1 yet.

## v0.1 status

This is a **local MVP release candidate**. It is ready for source review, GitHub publication, demos, and the next packaging milestone.
