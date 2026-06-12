# macOS app supervisor wiring

Task 217 wires the macOS `.app` foundation to the desktop supervisor contract.

The goal is no longer just a shortcut or documentation bridge. The generated app bundle now contains a launcher that follows the same lifecycle rules as the future Tauri shell:

1. validate packaged backend and frontend resources;
2. create app-owned data and logs directories outside the `.app` bundle;
3. check whether the backend health endpoint is already ready;
4. refuse to kill unknown processes if the target port is busy;
5. start only the app-owned backend on `127.0.0.1`;
6. poll `/health` before opening the UI;
7. write readable launcher/backend logs.

## Build

```bash
cd ~/Documents/ai_workspace
cd frontend && npm ci && npm run build
cd ..
./scripts/package_macos_app_foundation.sh
```

Expected output:

```text
build/macos/AI Private Workspace.app
```

Open it:

```bash
open "build/macos/AI Private Workspace.app"
```

## Logs

The wired launcher writes logs outside the bundle:

```text
~/Library/Application Support/AI Private Workspace/logs/macos-app-launcher.log
~/Library/Application Support/AI Private Workspace/logs/backend.log
~/Library/Application Support/AI Private Workspace/logs/backend.pid
```

Logs are intentionally outside the `.app` bundle so package rebuilds and future updates do not erase runtime diagnostics.

## Safety boundaries

- The frontend still does not execute shell commands.
- App launch does not start scan, index, rebuild, MCP, agent workflows, or model downloads.
- The launcher starts only the app-owned backend.
- The backend binds to localhost by default.
- If the port is busy with an unknown process, the launcher exits with a friendly error.
- Runtime data is not copied into the generated app bundle.

## Current limitation

This is still a foundation package, not the final signed `.dmg` or installer-grade Tauri app. It still depends on local `python3` and installed backend dependencies. The next packaging tasks should freeze the backend runtime and replace this shell launcher with a real desktop shell supervisor.
