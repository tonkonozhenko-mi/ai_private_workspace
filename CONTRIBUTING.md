# Contributing

Thanks for improving AI Private Workspace.

## Development rules

- Keep the app local-first and privacy-preserving.
- Do not add frontend shell execution.
- Do not make scan/index/rebuild/restart/model download/MCP/Agent actions automatic.
- Keep backend domain/core code free from FastAPI and sqlite-specific concerns where possible.
- Add tests for backend behavior and keep UI changes buildable with `npm run build`.
- Do not commit runtime data, local databases, build output, or caches.

## Local validation

```bash
./scripts/audit_release_candidate.sh

cd backend
pytest -q

cd ../frontend
npm ci
npm run build
```

For large changes, update the relevant docs under `docs/` and `docs/API_INVENTORY.md`.

## Pull requests

A good PR includes:

- clear summary;
- safety impact;
- tests run;
- screenshots for UI changes;
- docs updates when behavior changes.
