# macOS app package next steps

After Task 215, the packaging path should move in larger steps:

## Task 216 — app supervisor contract implementation

Implement the real app supervisor layer for macOS packaging:

- structured app lifecycle states
- backend port selection
- backend readiness polling
- logs path reporting
- friendly startup error model
- no process killing by port alone

## Task 217 — Tauri shell foundation

Add the first Tauri project structure after the supervisor contract is stable.
The shell should consume `frontend/dist` and use backend supervisor APIs/commands only from trusted shell code.

## Task 218 — release candidate packaging audit

Verify:

- no runtime data in archives
- packaging scripts are copy/build only
- frontend does not run shell commands
- model downloads are still backend-approved jobs
- MCP execution remains disabled
- docs explain the difference between developer bridge and final app

## Windows direction

Windows packaging should follow after macOS foundation stabilizes:

- app-owned backend process
- localhost-only API
- local app data path
- logs directory
- `.exe`/`.msi` packaging direction
- same safety boundaries as macOS
