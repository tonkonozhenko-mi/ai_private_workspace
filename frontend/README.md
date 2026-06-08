# Frontend

Minimal Vite, React, and TypeScript prototype for the Private Project AI
Workbench.

The frontend currently reads:

- workspace overview
- selected workspace dashboard
- workspace UI action catalog
- workspace Models dashboard summary

It does not execute action-catalog routes or call LLM providers directly.

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
