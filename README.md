# AI Private Workspace

![AI Private Workspace local-first flow](docs/assets/product-flow.svg)

AI Private Workspace is a local-first assistant for understanding private codebases and project folders. It helps you scan a workspace, build local context, ask questions with source-grounded answers, generate project reports, and prepare safe agent plans without sending your project data to external services.

> v0.1 is a source release candidate. Desktop packaging foundations for macOS and Windows are included, but final signed installers are still a roadmap item.

## Why it exists

Many teams want AI assistance for onboarding, documentation, DevOps analysis, and project understanding, but cannot upload private repositories to external tools. This project is designed around explicit user actions, local runtime data, and safe boundaries.

## Current capabilities

- Workspace onboarding for local folders.
- File scanning and indexing only after explicit user action.
- Local AI flow with Ollama/Qdrant integration foundations.
- Persistent conversations and answer history.
- Project reports and documentation generation.
- Model manager with install drafts, allowlisted downloads, jobs, history, and safe cancel semantics.
- Safe Agent + MCP readiness flow: planning and manual tracking first, execution later.
- macOS and Windows desktop packaging foundations.
- Release candidate audit script for GitHub/source hygiene.

## Safety model

AI Private Workspace keeps the frontend as a UI only. It does not execute shell commands, start scans, rebuild indexes, launch MCP tools, or download models automatically.

Risky operations are designed to be explicit, backend-owned, allowlisted, and auditable. Model download execution is disabled by default.

## Quick start for developers

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

```bash
cd frontend
npm ci
npm run build
```

Run the release audit before pushing a release candidate:

```bash
./scripts/audit_release_candidate.sh
```

## Desktop direction

The final target is:

```text
download package -> double click -> local backend starts -> UI opens -> work locally
```

Current packaging status:

- Tauri-first direction is locked.
- macOS `.app` foundation exists.
- Windows packaging foundation exists.
- Backend supervisor contract exists.
- Final signed `.app`, `.dmg`, `.exe`, and `.msi` installers are not finished yet.

## Repository guide

Start here:

- [Start here](docs/START_HERE.md)
- [Roadmap](docs/ROADMAP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Release candidate audit](docs/RELEASE_CANDIDATE_AUDIT.md)
- [v0.1 demo handoff](docs/V01_DEMO_HANDOFF.md)
- [GitHub repository guide](docs/GITHUB_REPOSITORY_GUIDE.md)

## Do not commit

Keep local runtime and build data out of Git:

- `backend/.ai-workbench/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `.pytest_cache/`
- `__pycache__/`

The `.ai-workbench` directory is a legacy internal runtime path. The product name is AI Private Workspace.
