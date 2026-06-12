# Contributing

Thanks for helping improve AI Private Workspace.

## Product principles

- Local-first by default.
- Private project data must stay under user control.
- Frontend must never execute shell commands.
- Scans, indexing, rebuilds, model downloads, MCP setup, and Agent workflows must require explicit user action.
- Backend core must stay independent from FastAPI, SQLite, and other infrastructure details.
- Project claims in answers must be grounded in retrieved sources.

## Development flow

1. Create a focused branch.
2. Keep changes grouped by product flow, not by tiny UI/button-only patches.
3. Add or update tests for backend behavior.
4. Run local validation before opening a PR.

```bash
./scripts/audit_release_candidate.sh
cd backend && pytest -q
cd ../frontend && npm ci && npm run build
```

## Source hygiene

Do not commit runtime or build data:

- `backend/.ai-workbench/`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `.pytest_cache/`
- `__pycache__/`
- `*.db`, `*.sqlite`, `*.sqlite3`

## Pull requests

A good PR should include:

- clear product reason;
- summary of user-visible changes;
- safety impact;
- tests or validation commands;
- screenshots for UI changes when useful.
