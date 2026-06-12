# Task 258 — Frozen backend startup diagnostics

## Why this task exists

Local macOS testing showed that `scripts/smoke_frozen_backend_runtime.sh` could start the generated PyInstaller executable, but `/health` stayed unavailable:

```text
started frozen backend PID ...
health check failed for http://127.0.0.1:8000/health: <urlopen error [Errno 61] Connection refused>
```

The previous smoke script only reported the final connection error, so the real frozen-runtime startup error was hidden in the log file.

## What changed

- `backend/packaging/pyinstaller_backend_entrypoint.py`
  - imports `app.main` eagerly before starting Uvicorn;
  - supports `--runtime-self-check`;
  - prints startup tracebacks to stderr;
  - sets safe desktop defaults for `APP_DATA_DIR` and `WORKSPACE_DB_PATH` when running frozen.

- `backend/packaging/ai_private_workspace_backend.spec`
  - collects hidden imports for `app`, `uvicorn`, `fastapi`, `starlette`, `pydantic`, `pydantic_core`, and `yaml`;
  - includes package data collection for `app`.

- `scripts/smoke_frozen_backend_runtime.sh`
  - runs the frozen executable with `--runtime-self-check` before starting the server;
  - stores smoke app data under `build/desktop/smoke-logs/app-data`;
  - detects early process exit while waiting for `/health`;
  - prints the frozen backend log tail on import/startup/health failure.

- `scripts/check_frozen_backend_startup_diagnostics.sh`
  - verifies that the diagnostics guardrails stay present.

## Local validation path

```bash
scripts/check_frozen_backend_startup_diagnostics.sh
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
```

If the smoke still fails, the script now prints the backend log tail directly in the terminal. Fix the printed import/runtime error, rebuild, and rerun the smoke.

## Safety

- The smoke script refuses to run if the target port is already used.
- It stops only the PID it started.
- It does not kill by port.
- It does not start scan, index, rebuild, MCP, Agent, or model downloads.
- Generated logs/data stay under ignored `build/desktop` paths.
