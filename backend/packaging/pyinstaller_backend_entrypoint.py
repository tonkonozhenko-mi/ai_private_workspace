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


def _default_desktop_app_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AI Private Workspace"
    if sys.platform == "win32":
        return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AI Private Workspace"
    return Path.home() / ".local" / "share" / "AI Private Workspace"


def _first_non_empty_env(*names: str, default: Path) -> Path:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return Path(value.strip()).expanduser()
    return default


def _configure_frozen_environment() -> None:
    """Set safe desktop defaults for the frozen backend runtime."""

    if getattr(sys, "frozen", False):
        os.environ.setdefault("APP_ENV", "desktop")
        app_data_dir = _first_non_empty_env(
            "APP_DATA_DIR",
            "AI_WORKSPACE_APP_DATA_DIR",
            default=_default_desktop_app_data_dir(),
        )
        workspace_db_path = _first_non_empty_env(
            "WORKSPACE_DB_PATH",
            "AI_WORKBENCH_DB_PATH",
            default=app_data_dir / "data" / "workspaces.db",
        )
        workspace_db_path.parent.mkdir(parents=True, exist_ok=True)
        (app_data_dir / "logs").mkdir(parents=True, exist_ok=True)
        os.environ["APP_DATA_DIR"] = str(app_data_dir)
        os.environ["WORKSPACE_DB_PATH"] = str(workspace_db_path)
        os.environ.setdefault("AI_WORKSPACE_APP_DATA_DIR", str(app_data_dir))
        os.environ.setdefault("AI_WORKBENCH_DB_PATH", str(workspace_db_path))
        print(f"AI Private Workspace app data directory: {app_data_dir}", file=sys.stderr)
        print(f"AI Private Workspace workspace database: {workspace_db_path}", file=sys.stderr)
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
