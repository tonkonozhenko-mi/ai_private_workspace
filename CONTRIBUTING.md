# Contributing

Thanks for helping improve AI Private Workspace.

## Development checks

Run these before opening a pull request:

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q tests/test_health.py tests/test_api_inventory.py

cd ../frontend
npm ci
npm run build
```

## Safety rules

- Do not add frontend shell execution.
- Do not start scan/index/rebuild/model downloads/MCP/Agent automatically.
- Keep runtime data out of source archives and commits.
- Keep risky actions explicit, user-approved, and backend-owned.

## Repository hygiene

Do not commit:

- `backend/.ai-workbench/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- caches such as `.pytest_cache/` and `__pycache__/`
