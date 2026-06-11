# Contributing

AI Private Workspace is local-first and safety-first. Contributions should preserve those boundaries.

## Local checks

```bash
./scripts/audit_release_candidate.sh
cd backend && pytest -q tests/test_health.py tests/test_api_inventory.py
cd ../frontend && npm ci && npm run build
```

## Development principles

- Keep frontend actions explicit and user-triggered.
- Do not add browser-side shell execution.
- Keep backend core/domain code free from FastAPI and SQLite details.
- Put runtime, filesystem, provider, and process integrations behind adapters.
- Prefer calm, human-readable UI flows over dense admin dashboards.
- Document safety boundaries when adding model, MCP, agent, or packaging behavior.

## Pull requests

A good PR should include:

- what changed;
- what safety boundary was preserved;
- how it was tested;
- screenshots for UI changes when useful;
- docs updates for user-facing or operator-facing behavior.
