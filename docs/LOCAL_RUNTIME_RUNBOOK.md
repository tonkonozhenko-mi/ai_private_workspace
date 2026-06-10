# Local runtime runbook

AI Private Workspace is local-first. The frontend must never execute shell commands. The scripts in `scripts/` are optional terminal helpers for the user to run explicitly.

## Start backend

```bash
cd ~/Documents/ai_workspace
scripts/start_backend.sh
```

The backend script:

- activates `backend/.venv`;
- verifies Python 3.10+;
- starts uvicorn via `python -m uvicorn`;
- defaults to Ollama + Qdrant environment variables;
- does not delete or modify workspace data beyond normal backend startup.

## Start frontend

```bash
cd ~/Documents/ai_workspace
scripts/start_frontend.sh
```

## Check runtime

```bash
cd ~/Documents/ai_workspace
scripts/check_runtime.sh
```

This reads `/health`, `/runtime/health`, `/runtime/local-data`, and `/runtime/startup-checklist`.

## Apply generated updates safely

Always preserve runtime data:

```bash
cd ~/Documents/ai_workspace
scripts/apply_generated_update.sh --dry-run ~/Documents/ai_workspace_taskXXX_work ~/Documents/ai_workspace
scripts/apply_generated_update.sh ~/Documents/ai_workspace_taskXXX_work ~/Documents/ai_workspace
```

The apply script creates a pre-update DB backup when `backend/.ai-workbench/workspaces.db` exists.

Protected paths and files:

- `backend/.ai-workbench/`
- `*.db`
- `*.sqlite`
- `backend/.venv/`
- `frontend/node_modules/`
- frontend build output

## Important safety rule

The UI can display and copy commands, but it must not run them. Setup, updates, scan, index, rebuild, and model changes remain explicit user actions.

## Desktop-like startup helper

Task 180 adds a copy-only helper script:

```bash
scripts/start_local_workspace.sh
```

It prints the backend, frontend, and runtime-check commands without executing them. Keep backend and frontend in separate terminals so logs stay visible.

The browser UI stores the last selected workspace id in localStorage and restores it on startup when the workspace still exists in SQLite. This is convenience state only; project data remains in `backend/.ai-workbench/workspaces.db`.
