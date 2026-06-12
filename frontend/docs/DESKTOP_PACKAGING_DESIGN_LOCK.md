# Desktop packaging design lock

Task 214 locks the direction for the real desktop version of AI Private Workspace.

The final user experience is not “download the repo and run scripts”. The target is:

1. Download an app package.
2. Double-click AI Private Workspace.
3. The desktop shell starts a local backend.
4. The UI opens after backend health is ready.
5. The last workspace is restored when possible.
6. Model downloads remain explicit user-approved backend jobs.

## Decision

Use Tauri first, with Electron as a fallback if Python/backend bundling becomes simpler there.

Tauri is preferred because it is lighter and closer to native desktop expectations. The existing scripts remain a development bridge only.

## Runtime shape

- Frontend: Vite build served inside the desktop shell.
- Backend: FastAPI process supervised by the desktop shell.
- API binding: localhost only by default.
- Data: app-owned local data directory; never overwrite runtime DBs in updates.
- Logs: backend, shell, and model-download logs go to local troubleshooting logs.
- Models: downloads remain opt-in, allowlisted, backend-side jobs.
- MCP: registry/config readiness only until sandbox/allowlist execution exists.

## Safety boundaries

- Frontend never executes shell commands.
- Desktop shell can start only app-owned local processes.
- Runtime data is protected from generated updates.
- No silent model downloads during startup.
- No automatic MCP server/tool execution.
- No remote/cloud sync in the v0.1 packaging target.

## Implementation phases

1. Design lock.
2. macOS app foundation.
3. Installer-grade packaging.
4. Windows package foundation.
5. Release candidate audit.
