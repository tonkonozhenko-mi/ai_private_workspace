# Task 265 — Packaged app SQLite workspace smoke

## Goal

Close the macOS packaged-app workspace API failure where `/health` returned
HTTP 200 but `/workspaces/overview` failed with:

```text
sqlite3.OperationalError: unable to open database file
```

The packaged Tauri app must start only its bundled frozen FastAPI backend and
use this writable app-owned database:

```text
~/Library/Application Support/AI Private Workspace/data/workspaces.db
```

## Runtime contract

- Tauri creates the app-owned `logs` and `data` directories before spawning
  the backend.
- Tauri passes canonical environment variables:
  - `APP_DATA_DIR`
  - `WORKSPACE_DB_PATH`
- Tauri also passes the legacy aliases for compatibility:
  - `AI_WORKSPACE_APP_DATA_DIR`
  - `AI_WORKBENCH_DB_PATH`
- The frozen backend entrypoint uses the same app-owned macOS directory as its
  safe fallback. It never defaults to a writable path inside the `.app`
  resources directory.
- Backend settings ignore empty canonical values and can fall back to valid
  legacy aliases.
- The SQLite workspace repository creates the database parent directory before
  initialization and before every connection. Errors include the resolved
  database path in `backend.log`.
- The frozen-runtime smoke checks `/workspaces/overview` and confirms that
  `data/workspaces.db` was created before stopping its own child PID.
- Desktop readiness requires both `/health` and `/workspaces/overview` to
  return HTTP 200.

## Supervisor diagnostics

`desktop-supervisor.log` records:

- resolved app data directory;
- resolved workspace database path;
- resolved frozen backend executable;
- backend child PID;
- `/health` result;
- `/workspaces/overview` result.

`backend.log` is append-only and keeps historical errors. Every new app-owned
launch writes a clear start separator plus the resolved data, database, and
backend executable paths so old tracebacks are not mistaken for current
failures.

If an app-owned child passes `/health` but fails the workspace API check, Tauri
stops only that child PID and returns a clear startup error. If port 8000 is
owned by an unknown process, Tauri never kills it. On desktop app exit, Tauri
requests a graceful stop of only the child stored in the current app session,
allowing the PyInstaller bootloader to stop its internal server child. A hard
stop of that same stored PID is used only as a timeout fallback. It never kills
by port.

## Source-contract check

```bash
./scripts/check_packaged_app_workspace_api_smoke.sh
```

The check verifies SQLite path/bootstrap wiring, packaged-origin CORS, and the
absence of kill-by-port or generic shell execution in the Tauri supervisor.

## Exact macOS packaged smoke flow

```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm ci
npm run build
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

After opening the rebuilt app:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/workspaces/overview
ls -la "$HOME/Library/Application Support/AI Private Workspace/data"
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log"
tail -n 100 "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log"
```

Expected:

- `/health` returns HTTP 200;
- `/workspaces/overview` returns HTTP 200 instead of HTTP 500;
- `workspaces.db` exists in the app-owned `data` directory;
- first-run UI shows `No projects yet`, not a stale backend error;
- **Add project** works without SQLite or CORS errors.

Scan, index, rebuild, MCP, Agent, model downloads, and shell commands remain
explicit user actions and are not triggered by desktop launch.

## Stale listener safety

If an older packaged backend is still listening on port 8000, the rebuilt app
checks both endpoints. It refuses to reuse the process when `/health` is 200
but `/workspaces/overview` fails, logs the condition, and does not kill the
unknown listener. Quit/stop the older app-owned runtime explicitly or restart
the local session before repeating the final port-8000 smoke.

## Completed local smoke

After stopping the exact old app-owned PID recorded by the supervisor and
restarting the rebuilt `.app`:

- `/health` returned HTTP 200;
- `/workspaces/overview` returned HTTP 200;
- packaged-origin `OPTIONS /workspaces` returned HTTP 200;
- `data/workspaces.db` was created;
- `POST /workspaces` returned HTTP 201;
- the created workspace appeared in `/workspaces/overview`.
- after a graceful packaged-app quit, both the PyInstaller bootloader and its
  internal backend server child stopped, port 8000 became free, and no product
  process remained.
