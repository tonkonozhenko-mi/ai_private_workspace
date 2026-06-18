from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi import APIRouter

from app.api.schemas.local_data_safety_schemas import (
    DesktopStartupCommandResponse,
    FirstLaunchChecklistItemResponse,
    FirstLaunchReadinessResponse,
)
from app.config.settings import get_settings

# This router exposes a single read-only post-launch readiness checklist used by
# the desktop first-launch screen. (It previously held ~50 internal
# documentation/packaging endpoints that no UI consumed; those were removed.)
router = APIRouter(prefix="/runtime", tags=["runtime"])


def _read_counts(
    db_path: Path,
    table_names: object,
    warnings: list[str],
) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    try:
        with sqlite3.connect(db_path) as connection:
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "select name from sqlite_master where type = 'table'"
                ).fetchall()
            }
            for table_name in table_names:
                name = str(table_name)
                if name not in existing_tables:
                    counts[name] = None
                    continue
                counts[name] = int(connection.execute(f"select count(*) from {name}").fetchone()[0])
    except sqlite3.Error as exc:
        warnings.append(f"Could not read workspace database diagnostics: {exc}")
        for table_name in table_names:
            counts[str(table_name)] = None
    return counts


def _display_path(path: Path) -> str:
    return str(path.expanduser())


@router.get("/first-launch-readiness", response_model=FirstLaunchReadinessResponse)
def get_first_launch_readiness() -> FirstLaunchReadinessResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    db_exists = db_path.exists()
    counts: dict[str, int | None] = {"workspaces": None}
    warnings: list[str] = []
    if db_exists:
        counts = _read_counts(db_path, counts.keys(), warnings)

    has_workspace = (counts.get("workspaces") or 0) > 0
    backend_ready = sys.version_info >= (3, 10)
    ollama_selected = (
        settings.llm_provider.lower() == "ollama"
        and settings.embedding_provider.lower() == "ollama"
    )
    qdrant_selected = settings.vector_store.lower() == "qdrant"
    launcher_exists = (
        Path("../scripts/launch_macos.command").exists()
        or Path("scripts/launch_macos.command").exists()
    )

    checklist = [
        FirstLaunchChecklistItemResponse(
            id="backend-runtime",
            title="Backend runtime",
            status="ok" if backend_ready else "blocked",
            summary=f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            detail="The local API can run with Python 3.10+; Python 3.12 is preferred.",
            user_action=None if backend_ready else "Recreate backend/.venv with Python 3.12.",
        ),
        FirstLaunchChecklistItemResponse(
            id="workspace-data",
            title="Workspace data",
            status="ok" if has_workspace else "review",
            summary=f"{counts.get('workspaces') or 0} workspace(s) found",
            detail=f"Runtime database path: {_display_path(db_path)}",
            user_action=None
            if has_workspace
            else "Create or reopen a workspace after the app starts.",
        ),
        FirstLaunchChecklistItemResponse(
            id="local-ai-models",
            title="Local AI models",
            status="ok" if ollama_selected else "review",
            summary=f"LLM={settings.llm_provider}/{settings.ollama_llm_model}; embeddings={settings.embedding_provider}/{settings.ollama_embedding_model}",
            detail="This check only validates selected providers and model names. It does not pull or start models.",
            user_action=None
            if ollama_selected
            else "Use the guided model setup and start backend with Ollama providers when ready.",
        ),
        FirstLaunchChecklistItemResponse(
            id="search-context-store",
            title="Search context store",
            status="ok" if qdrant_selected else "review",
            summary=f"Vector store: {settings.vector_store}",
            detail="Persistent search context is expected to use Qdrant for packaging-ready local use.",
            user_action=None
            if qdrant_selected
            else "Use Qdrant before depending on persistent RAG answers.",
        ),
        FirstLaunchChecklistItemResponse(
            id="macos-launcher",
            title="macOS launcher",
            status="ok" if launcher_exists else "review",
            summary="launch_macos.command found"
            if launcher_exists
            else "Launcher script not found from current working directory",
            detail="The launcher is a user-started helper for backend/frontend only.",
            user_action=None
            if launcher_exists
            else "Run from the project root or verify scripts/launch_macos.command is packaged.",
        ),
        FirstLaunchChecklistItemResponse(
            id="desktop-shortcut",
            title="Desktop shortcut",
            status="review",
            summary="Optional Finder/Dock shortcut is user-created",
            detail="Use scripts/create_macos_shortcut.sh to create a local .app wrapper when you want a normal macOS app icon.",
            user_action="Run the shortcut creation command only when you want a Dock/Application shortcut.",
        ),
    ]

    blocked = any(item.status == "blocked" for item in checklist)
    review = any(item.status == "review" for item in checklist) or bool(warnings)
    status = "blocked" if blocked else "review" if review else "ok"

    return FirstLaunchReadinessResponse(
        status=status,
        title="Post-launch workspace setup",
        summary="Ready after launch"
        if status == "ok"
        else "Review post-launch checklist before daily use",
        checklist=checklist,
        recommended_flow=[
            "Open the last workspace or create a new local workspace.",
            "Review guided model setup and save preferences only when needed.",
            "Run scan and build search context only by explicit user click.",
            "Create a local backup before applying generated updates.",
        ],
        copy_commands=[
            DesktopStartupCommandResponse(
                label="macOS launcher",
                command="cd ~/Documents/ai_workspace && ./scripts/launch_macos.command",
                description="Starts the local app after explicit terminal confirmation.",
            ),
            DesktopStartupCommandResponse(
                label="Create macOS app shortcut",
                command="cd ~/Documents/ai_workspace && ./scripts/create_macos_shortcut.sh",
                description="Creates ~/Applications/AI Private Workspace.app. It does not start services or run model/index actions.",
            ),
            DesktopStartupCommandResponse(
                label="Runtime check",
                command="cd ~/Documents/ai_workspace && scripts/check_runtime.sh",
                description="Read-only runtime preflight check.",
            ),
        ],
        safety_note="This post-launch checklist is read-only. It never installs models, starts scans, rebuilds indexes, executes MCP tools, or runs shell commands from the frontend. Startup instructions live outside the UI in docs/START_HERE.md until the real desktop package exists.",
    )

