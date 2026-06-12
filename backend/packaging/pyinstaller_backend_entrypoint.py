"""PyInstaller entrypoint for the AI Private Workspace backend runtime.

The file is intentionally small, but it is more defensive than the normal
``uvicorn app.main:app`` development command. Frozen binaries fail differently
from source runs, so this entrypoint performs an explicit import preflight and
prints actionable startup diagnostics to stderr before Uvicorn starts.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import uvicorn


def _configure_frozen_environment() -> None:
    """Set safe desktop defaults for the frozen backend runtime."""

    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        os.environ.setdefault("APP_ENV", "desktop")
        os.environ.setdefault(
            "APP_DATA_DIR",
            str(executable_dir / "app-data"),
        )
        os.environ.setdefault(
            "WORKSPACE_DB_PATH",
            str(executable_dir / "app-data" / "workspaces.db"),
        )
    else:
        os.environ.setdefault("APP_ENV", "desktop")


def _import_app() -> object:
    """Import the FastAPI app eagerly so frozen startup errors are logged."""

    try:
        from app.main import app
    except Exception:  # noqa: BLE001 - startup diagnostics must preserve traceback
        print("AI Private Workspace frozen backend failed during app import", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
    return app


def main() -> None:
    _configure_frozen_environment()
    host = os.getenv("AI_PRIVATE_WORKSPACE_HOST", os.getenv("HOST", "127.0.0.1"))
    port = int(os.getenv("AI_PRIVATE_WORKSPACE_PORT", os.getenv("PORT", "8000")))
    log_level = os.getenv("LOG_LEVEL", "info")

    app = _import_app()
    if "--runtime-self-check" in sys.argv:
        print("AI Private Workspace frozen backend import preflight: ok")
        return

    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
