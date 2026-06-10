# Production Readiness

AI Private Workspace is still a local-first developer app, but it can be used safely for daily work when the local runtime is explicit and protected.

## Recommended current packaging level

Use the script-based local app flow first:

```bash
cd ~/Documents/ai_workspace
scripts/check_runtime.sh
scripts/start_backend.sh
scripts/start_frontend.sh
```

This keeps all runtime behavior visible and avoids hidden shell execution from the UI.

## Before daily use

Check the Settings panels:

- Local data safety
- Startup checklist
- Safe updates
- Backup and restore
- Migration safety
- Troubleshooting assistant
- Production readiness

The frontend only shows and copies commands. It must not execute shell commands.

## Before applying generated updates

Always run dry-run first:

```bash
cd ~/Documents/ai_workspace
scripts/apply_generated_update.sh --dry-run ~/Documents/ai_workspace_taskXXX_work ~/Documents/ai_workspace
```

Then apply only after reviewing the output:

```bash
scripts/apply_generated_update.sh ~/Documents/ai_workspace_taskXXX_work ~/Documents/ai_workspace
```

The update workflow must preserve:

- `backend/.ai-workbench/`
- `*.db`
- `*.sqlite`
- `.venv`
- `node_modules`
- `dist`

## Packaging path

1. Script-based local app — current recommended mode.
2. macOS Shortcut / Automator launcher — later, wrapping only existing scripts.
3. Desktop wrapper such as Tauri/Electron — later, after backup/restore and update safety are stable.

Do not introduce auto-updates or auto-start behavior until local data protection is fully reliable.

## Task 194 macOS launcher foundation

The first packaging-ready launcher is now `scripts/launch_macos.command`.

It is a conservative macOS `.command` file that checks prerequisites, asks for explicit confirmation, starts backend and frontend in Terminal, and opens the local UI. It does not install models, scan projects, rebuild indexes, run MCP tools, or execute agent workflows.

See `docs/MACOS_LAUNCHER.md` for setup and Finder shortcut instructions.
