# macOS launcher

Task 194 adds a first desktop-like launcher for local development and future packaging.

## What it does

`scripts/launch_macos.command` starts the existing local backend and frontend scripts in separate Terminal windows and opens the app URL.

It is intentionally conservative:

- it starts only the local backend and frontend servers after an explicit user confirmation;
- it does not pull Ollama models;
- it does not scan or index projects;
- it does not rebuild search context;
- it does not run MCP tools or agent execution steps;
- it does not modify workspace runtime data.

## One-time preparation

From the project root:

```bash
chmod +x scripts/start_backend.sh scripts/start_frontend.sh scripts/launch_macos.command

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm ci
```

## Launch

Double-click:

```text
scripts/launch_macos.command
```

Or run from Terminal:

```bash
./scripts/launch_macos.command
```

The launcher checks that `backend/.venv` and `frontend/node_modules` already exist. If they are missing, it prints the exact setup command and exits without starting anything.

## Optional Finder shortcut

In Finder, create an alias for `scripts/launch_macos.command` and move the alias to Desktop or Applications.

The alias is only a shortcut to this script. The script still asks for confirmation before starting local servers.
