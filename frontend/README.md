# Frontend

Minimal Vite, React, and TypeScript prototype for the Private Project AI
Workbench.

The frontend currently reads:

- workspace overview
- selected workspace dashboard with Overview, Ask, Models, Actions, and Activity tabs
- workspace UI action catalog
- workspace Models dashboard summary
- detailed workspace Models dashboard and local AI activation guide

It does not execute action-catalog routes or call LLM providers directly. Tabs
are local component state only. The Models tab displays selected and active
runtime state, recommendations, performance history, and setup commands as
read-only instructions. Activation commands can be copied to the clipboard, but
they are never executed by the frontend. The Actions tab is inspection-only:
actions can be selected to review their endpoint, status, and safety details,
but no action is invoked. The Activity tab presents the persisted backend
timeline as a read-only event history with compact metadata previews.

The Ask tab sends a question only after the user presses **Ask**, using
`POST /workspaces/{workspace_id}/ask-selected`. Asking may create a persisted
timeline event, but it does not execute commands, reindex automatically, or
change runtime settings. Recent Ask responses are kept as session history only
inside the current browser tab; the frontend does not persist that history.
The composer offers project-question examples and non-blocking guidance for
likely general-chat questions, while still allowing every question to be
submitted explicitly.

## Run

```bash
cd frontend
npm install
npm run dev
```

The backend URL defaults to `http://127.0.0.1:8000`. Override it when needed:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

The backend allows `http://localhost:5173` and `http://127.0.0.1:5173` by
default for local Vite development. If Vite runs on another host or port,
restart the backend with a matching comma-separated origin list:

```bash
CORS_ALLOWED_ORIGINS=http://localhost:4173,http://127.0.0.1:4173 \
uvicorn app.main:app --reload
```

## Checks

```bash
npm run typecheck
npm run build
```
