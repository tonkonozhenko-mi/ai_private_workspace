# GitHub Repository Guide

This project is intended to look clean and understandable when published to GitHub.

## Recommended repository entry points

- `README.md` — public landing page.
- `docs/START_HERE.md` — first run and orientation.
- `docs/V01_DEMO_HANDOFF.md` — demo flow.
- `docs/V01_RELEASE_NOTES.md` — v0.1 release notes.
- `docs/ROADMAP.md` — product direction.
- `docs/ARCHITECTURE.md` — architecture overview.
- `docs/RELEASE_CANDIDATE_AUDIT.md` — release checklist.

## Keep out of GitHub

Do not commit:

- `backend/.ai-workbench/`
- `*.db`, `*.sqlite`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `__pycache__/`
- `.pytest_cache/`
- generated `.app`, `.exe`, `.msi`, `.dmg` artifacts

## Before pushing

```bash
./scripts/audit_release_candidate.sh
cd frontend && npm ci && npm run build
cd backend && pytest -q tests/test_v01_handoff.py tests/test_release_candidate_audit.py tests/test_api_inventory.py
```

## Suggested GitHub description

Local-first AI workspace for private project onboarding, local RAG, model management, reports, and safe Agent/MCP planning.
## Task 224 final product-quality pass

- Repository now includes GitHub-ready README, contribution guide, security policy, issue templates, PR template, and CI workflows.
- Frontend received a final Apple-style normalization layer for spacing, typography, controls, card rhythm, and dark mode.
- Product-facing copy now consistently uses AI Private Workspace.
- `docs/assets/product-flow.svg` explains the local-first flow on the GitHub landing page.

