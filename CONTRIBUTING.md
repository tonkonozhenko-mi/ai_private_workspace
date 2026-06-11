# Contributing

Thanks for helping improve AI Private Workspace.

## Development principles

- Keep the product local-first and privacy-preserving.
- Keep frontend actions explicit and safe.
- Do not add frontend shell execution.
- Keep backend domain/core code independent from FastAPI, SQLite, or local process details.
- Prefer small reusable services over duplicated endpoint logic.
- Add tests for backend behavior and scripts when behavior changes.
- Keep UI calm, readable, and human-friendly.

## Local checks

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q

cd ../frontend
npm ci
npm run build
```

## Runtime data policy

Do not commit local runtime/build data:

- `backend/.ai-workbench/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `.pytest_cache/`

## Pull requests

A good pull request should include:

- a short product-oriented summary;
- safety impact, especially if touching models, MCP, agents, packaging, or local processes;
- test commands that were run;
- screenshots for UI changes when possible.
