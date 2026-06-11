# Contributing

AI Private Workspace is built around a local-first and safety-first product model. Contributions should keep the interface calm, explicit, and easy to understand.

## Development checks

Backend:

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

Release audit:

```bash
./scripts/audit_release_candidate.sh
```

## UX principles

- Prefer one clear primary action per screen.
- Put advanced or risky details behind disclosure sections.
- Use short, human-readable copy instead of internal implementation names.
- Keep dark mode readable and calm.
- Do not make the frontend execute shell commands.

## Safety principles

- Scans, indexing, rebuilds, model downloads, MCP tools, and agent actions must be explicit user-click actions.
- Risky execution belongs to backend-owned, allowlisted, auditable flows.
- Do not commit runtime data, local databases, dependency folders, build output, or package artifacts.
