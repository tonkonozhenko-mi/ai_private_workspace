# AI Private Workspace

AI Private Workspace is a local-first AI workspace for understanding private codebases without uploading project data to external services by default.

It combines project scanning, local context indexing, workspace Q&A, report generation, model management, and safe Agent/MCP planning in one desktop-oriented product foundation.

![AI Private Workspace product flow](docs/assets/product-flow.svg)

## What this repository contains

This repository is a **v0.1 source release candidate**. It is ready for local development, demos, and GitHub review. It is not yet a signed commercial `.dmg`, `.msi`, or fully frozen desktop installer.

| Area | Status |
| --- | --- |
| Backend + frontend MVP | Ready |
| Local workspace scan/index/Ask/report flow | Ready |
| Ollama model manager foundation | Ready |
| Safe Agent + MCP planning foundation | Ready |
| macOS/Windows packaging foundation | Ready |
| Signed desktop installers | Future |
| Sandboxed Agent/MCP execution | Future |

## Quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Then open the frontend URL shown by Vite.

## Local model flow

1. Start Ollama locally.
2. Open **Models**.
3. Choose the AI answer model and the search context model.
4. Download missing models with copy-only commands or trusted backend-approved jobs.
5. Verify installed models.
6. Build workspace context with the selected search model.
7. Ask questions using local project context.

Risky actions stay explicit. The browser frontend never executes shell commands.

## Safety boundaries

- Frontend never runs shell commands.
- App startup does not scan, index, rebuild, download models, start MCP servers, or run Agent tools.
- Model downloads are backend-owned, opt-in, allowlisted jobs.
- MCP and Agent workflows are planning/manual tracking until sandboxed execution is implemented.
- Runtime data is excluded from Git and release archives.

## Repository map

```text
backend/    FastAPI backend, domain/use-cases/adapters, tests
frontend/   React UI and Tauri scaffold
docs/       Product, architecture, runtime, packaging, and release docs
scripts/    Safe local helper scripts and release audit tools
.github/    CI, packaging checks, issue templates, and PR template
```

## Important docs

- [Start here](docs/START_HERE.md)
- [v0.1 demo handoff](docs/V01_DEMO_HANDOFF.md)
- [v0.1 release notes](docs/V01_RELEASE_NOTES.md)
- [Roadmap](docs/ROADMAP.md)
- [v1 product completion roadmap](docs/V1_PRODUCT_COMPLETION_ROADMAP.md)
- [GitHub publication checklist](docs/GITHUB_PUBLICATION_CHECKLIST.md)
- [Release candidate audit](docs/RELEASE_CANDIDATE_AUDIT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API inventory](docs/API_INVENTORY.md)

## Validate before pushing

```bash
./scripts/audit_release_candidate.sh
cd backend && pytest -q tests/test_health.py tests/test_api_inventory.py
cd ../frontend && npm ci && npm run build
```

Create a clean source archive:

```bash
./scripts/prepare_source_release_archive.sh
```

Generated archives are written under `build/release/` and must not be committed.

## Do not commit

- `backend/.ai-workbench/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- caches and virtual environments

## License

Add a license before public distribution if this repository will be shared outside private/internal use.
