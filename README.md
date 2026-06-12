# AI Private Workspace

**AI Private Workspace** is a local-first desktop-oriented workspace for private project onboarding, local RAG, model management, project reports, and safe Agent/MCP planning.

The v0.1 release candidate is a source handoff for developers and reviewers. It is not yet a signed installer-grade product.

![AI Private Workspace flow](docs/assets/product-flow.svg)

## What it does

- Creates local workspaces for private projects.
- Scans source folders and detects skills such as Terraform, Terragrunt, Kubernetes, Helm, Docker, Python, GitLab CI, and documentation.
- Builds local search context only after explicit user action.
- Answers questions from retrieved project sources instead of unsupported guesses.
- Keeps conversations, answer history, model choices, reports, and timeline state locally.
- Guides local Ollama/model setup and detects installed local models.
- Provides safe model download drafts and backend-owned download jobs behind explicit approval.
- Provides Agent and MCP planning UX without automatic tool execution.
- Includes macOS, Windows, and Tauri packaging foundations for future installer-grade releases.

## Safety model

AI Private Workspace is designed around explicit user control:

- The frontend never executes shell commands.
- App launch never starts scans, indexing, rebuilds, MCP servers, Agent workflows, or model downloads.
- Model download execution is disabled by default and must be enabled backend-side in trusted local runtime only.
- Agent workflows are planning/manual tracking only in v0.1.
- Approval gates record user intent; they do not execute tools automatically.
- Runtime data, local databases, caches, and build artifacts are excluded from source archives.

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

## License

License has not been finalized yet. Add a `LICENSE` file before public production distribution.
