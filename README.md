# AI Private Workspace

AI Private Workspace is a local-first assistant workspace for understanding private projects without sending source code to external services by default.

It combines project scanning, local context indexing, Ollama-based model setup, source-grounded Ask, reports, and safe Agent/MCP planning foundations.

> Status: **v0.1 source release candidate**. This repository is ready for local demos and GitHub publication checks. It is not yet a signed macOS/Windows installer.

![AI Private Workspace product flow](docs/assets/product-flow.svg)

## What it does

- Creates local workspaces for project folders.
- Scans files and detects skills such as Terraform, Python, Docker, Kubernetes, Helm, CI, and documentation.
- Builds local context for source-grounded answers.
- Lets you choose local LLM and embedding/search models.
- Supports safe Ollama model download drafts and backend-owned jobs.
- Generates reports and keeps conversation history.
- Provides Agent and MCP planning foundations without automatic tool execution.
- Includes macOS and Windows packaging foundations for the future desktop app.

## Safety principles

- Frontend never executes shell commands.
- Scan, index, rebuild, model downloads, MCP, and Agent execution require explicit user action.
- Model downloads are backend-owned, opt-in, and allowlisted.
- MCP servers and tools are not started automatically.
- Runtime data and build outputs are excluded from source release archives.

## Quick start for local development

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

Open the local frontend URL shown by Vite.

## Recommended validation

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q tests/test_health.py tests/test_release_candidate_audit.py tests/test_api_inventory.py

cd ../frontend
npm ci
npm run build
```

## Source release archive

```bash
./scripts/prepare_source_release_archive.sh
```

The archive is written under `build/release/` and excludes runtime/build/cache data.

## Documentation map

- `docs/START_HERE.md` — first entry point.
- `docs/V01_DEMO_HANDOFF.md` — v0.1 demo flow.
- `docs/V01_RELEASE_NOTES.md` — v0.1 release notes.
- `docs/V1_PRODUCT_COMPLETION_ROADMAP.md` — honest path from source RC to v1.0.
- `docs/GITHUB_PUBLICATION_CHECKLIST.md` — first push checklist.
- `docs/RELEASE_CANDIDATE_AUDIT.md` — release audit policy.

## Current roadmap position

AI Private Workspace is currently a polished **v0.1 source release candidate**. A full v1.0 product still needs a frozen backend runtime, signed installers, persistent jobs, and sandboxed Agent/MCP execution.
