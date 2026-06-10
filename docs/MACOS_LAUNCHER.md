# macOS launcher and desktop shortcut

This project uses a conservative desktop-like launcher before introducing a real packaged app.

The goal is simple: open AI Private Workspace like a normal local app while keeping all risky actions explicit.

## What is included

- `scripts/launch_macos.command` — starts backend and frontend after terminal confirmation.
- `scripts/create_macos_shortcut.sh` — creates a local `.app` wrapper in `~/Applications`.
- First-launch checklist in the Models tab — shows readiness and copy-only commands.

## Safety model

The launcher and shortcut are intentionally limited.

They do not:

- install or pull Ollama models; it does not pull Ollama models automatically;
- scan projects;
- index files;
- scan or index projects automatically; it does not scan or index projects automatically;
- rebuild search context;
- restart models;
- execute MCP tools;
- execute agent workflow steps;
- change workspace runtime data.

They only help the user start the already configured local backend/frontend servers.

## One-time preparation

From the project root:

```bash
chmod +x scripts/start_backend.sh scripts/start_frontend.sh scripts/launch_macos.command scripts/create_macos_shortcut.sh

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm ci
```

## Launch from Terminal

```bash
cd ~/Documents/ai_workspace
./scripts/launch_macos.command
```

The launcher asks for confirmation before starting anything.

## Create a macOS app shortcut

Run this once from the project root:

```bash
cd ~/Documents/ai_workspace
./scripts/create_macos_shortcut.sh
```

By default it creates:

```text
~/Applications/AI Private Workspace.app
```

The generated app is only a wrapper around `scripts/launch_macos.command`. It still asks for confirmation before starting local servers.

## Add to Dock

1. Open Finder.
2. Go to `~/Applications`.
3. Find `AI Private Workspace.app`.
4. Drag it to the Dock.

You can also run:

```bash
open ~/Applications
```

## Custom app name or output folder

```bash
APP_NAME="AI Workbench" OUTPUT_DIR="$HOME/Desktop" ./scripts/create_macos_shortcut.sh
```

This creates:

```text
~/Desktop/AI Workbench.app
```

## Updating the project

Generated archives should not include runtime data. Before applying generated updates:

```bash
cd ~/Documents/ai_workspace
./scripts/backup_workspace_db.sh
```

Then apply the updated root-preserving archive and rerun tests.

## Troubleshooting

If macOS blocks the app because it was locally generated:

1. Right-click the app.
2. Choose **Open**.
3. Confirm that you want to open it.

If dependencies are missing, the launcher exits and prints the exact setup command. It does not start partial services.
