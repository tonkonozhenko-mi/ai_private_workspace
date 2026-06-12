"""PyInstaller entrypoint for the AI Private Workspace backend runtime.

This file is intentionally tiny: it imports and runs Uvicorn against the existing
FastAPI application without changing application code. The desktop supervisor is
responsible for setting host/port/app-data environment variables before starting
this executable.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("AI_PRIVATE_WORKSPACE_HOST", os.getenv("HOST", "127.0.0.1"))
    port = int(os.getenv("AI_PRIVATE_WORKSPACE_PORT", os.getenv("PORT", "8000")))
    os.environ.setdefault("APP_ENV", "desktop")
    uvicorn.run("app.main:app", host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info"))


if __name__ == "__main__":
    main()
