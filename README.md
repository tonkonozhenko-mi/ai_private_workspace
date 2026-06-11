# AI Private Workspace

**AI Private Workspace** is a local-first assistant workspace for understanding private projects without sending source code to external AI services.

It combines a FastAPI backend, a React desktop-style frontend, local model support through Ollama, project scanning, local context indexing, model management, reports, and a safe Agent/MCP foundation.

![AI Private Workspace product flow](docs/assets/product-flow.svg)

## Why this exists

Teams often want AI help with project onboarding, DevOps analysis, documentation, and codebase understanding, but cannot upload private repositories to external tools. AI Private Workspace is designed around a simple rule:

> Your project stays local. The app only uses explicit user actions, local services, and safety gates.

## Current status

This repository is a **v0.1 source release candidate**.

It is ready for local development, demos, and continued product work. It is **not yet** a signed commercial desktop installer.

| Area | Status |
|---|---|
| Backend foundation | Ready |
| Frontend MVP | Ready |
| Local RAG / context flow | Ready foundation |
| Ollama model manager | Ready foundation |
| Agent + MCP workflow | Safe planning foundation |
| macOS/Windows packaging | Foundation ready |
| Signed `.dmg` / `.msi` installers | Future v1 work |
| Sandboxed Agent execution | Future v1 work |

## Product flow

1. Create or select a workspace.
2. Scan local project files.
3. Choose AI and search-context models.
4. Build local context.
5. Ask questions, generate summaries, and create reports.
6. Use Agent/MCP planning safely before future controlled execution.

## Safety principles

- The frontend never runs shell commands.
- Scan, index, rebuild, restart, model download, MCP, and Agent execution never start automatically.
- Risky operations require explicit user intent.
- Model downloads are backend-side, opt-in, allowlisted, and approval-based.
- Agent workflows are currently planning/manual tracking only.
- MCP servers/tools are not started automatically.
- Runtime data must not be committed.

## Repository layout

```text
backend/     FastAPI backend, domain services, adapters, tests
frontend/    React + Vite UI, Tauri scaffold foundation
docs/        Architecture, release, packaging, model, Agent/MCP documentation
scripts/     Local run, audit, packaging, backup, and release helper scripts
.github/     CI, desktop packaging checks, issue and PR templates
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

Then open the URL printed by Vite.

## Recommended validation

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q tests/test_health.py tests/test_api_inventory.py tests/test_release_candidate_audit.py

cd ../frontend
npm ci
npm run build
```

## Create a clean source archive

```bash
./scripts/prepare_source_release_archive.sh
```

The archive is written to `build/release/`. Do not commit generated release archives.

## Important docs

- [Start here](docs/START_HERE.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.1 demo handoff](docs/V01_DEMO_HANDOFF.md)
- [v0.1 release notes](docs/V01_RELEASE_NOTES.md)
- [GitHub publication checklist](docs/GITHUB_PUBLICATION_CHECKLIST.md)
- [v1 product completion roadmap](docs/V1_PRODUCT_COMPLETION_ROADMAP.md)
- [Release candidate audit](docs/RELEASE_CANDIDATE_AUDIT.md)
- [Desktop packaging design lock](docs/DESKTOP_PACKAGING_DESIGN_LOCK.md)

## Runtime data policy

Do not commit runtime or generated data:

```text
backend/.ai-workbench/
*.db
*.sqlite
*.sqlite3
frontend/node_modules/
frontend/dist/
build/
.pytest_cache/
__pycache__/
```

## License

No license has been selected yet. Add one before public/open-source distribution.
