from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi import APIRouter

from app.api.schemas.local_data_safety_schemas import (
    LocalDataBackupHintResponse,
    LocalDataSafetyResponse,
    StartupChecklistItemResponse,
    StartupChecklistResponse,
)
from app.config.settings import get_settings


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/local-data", response_model=LocalDataSafetyResponse)
def get_local_data_safety() -> LocalDataSafetyResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    app_data_dir = settings.app_data_dir
    db_exists = db_path.exists()
    db_size = db_path.stat().st_size if db_exists else 0
    warnings: list[str] = []

    counts: dict[str, int | None] = {
        "workspaces": None,
        "workspace_conversations": None,
        "workspace_saved_reports": None,
        "workspace_answer_notes": None,
    }
    if db_exists:
        counts = _read_counts(db_path, counts.keys(), warnings)
    else:
        warnings.append("Workspace database does not exist yet. Create a workspace to initialize local state.")

    if settings.workspace_repository.lower() != "sqlite":
        warnings.append("Workspace repository is not sqlite; local state may be disposable for this process.")
    if db_exists and counts.get("workspaces") == 0:
        warnings.append("Workspace database exists but has no workspaces. This usually means a fresh local database is active.")
    if not db_path.is_absolute():
        warnings.append("Database path is relative to the backend process working directory. Start the backend from the project backend directory or set WORKSPACE_DB_PATH explicitly.")

    safe_update_excludes = [
        "backend/.ai-workbench",
        "*.db",
        "*.sqlite",
        "*/.venv/*",
        "*/node_modules/*",
        "*/dist/*",
        "*/__pycache__/*",
        "*/.pytest_cache/*",
    ]
    protected_paths = [
        _display_path(app_data_dir),
        _display_path(db_path),
    ]

    return LocalDataSafetyResponse(
        status="review" if warnings else "ok",
        app_data_dir=_display_path(app_data_dir),
        database_path=_display_path(db_path),
        database_exists=db_exists,
        database_size_bytes=db_size,
        repository=settings.workspace_repository,
        vector_store=settings.vector_store,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        workspaces_count=counts.get("workspaces"),
        conversations_count=counts.get("workspace_conversations"),
        saved_reports_count=counts.get("workspace_saved_reports"),
        answer_notes_count=counts.get("workspace_answer_notes"),
        warnings=warnings,
        protected_paths=protected_paths,
        safe_update_excludes=safe_update_excludes,
        backup_hints=[
            LocalDataBackupHintResponse(
                label="Backup current workspace database",
                command=f"cp {_shell_quote(db_path)} {_shell_quote(db_path.with_suffix(db_path.suffix + '.backup'))}",
            ),
            LocalDataBackupHintResponse(
                label="Find workspace databases before applying an update",
                command="find ~/Documents -path '*ai_workspace*workspaces.db' -print -exec ls -lh {} \\;",
            ),
        ],
    )


@router.get("/startup-checklist", response_model=StartupChecklistResponse)
def get_startup_checklist() -> StartupChecklistResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    db_exists = db_path.exists()
    counts: dict[str, int | None] = {
        "workspaces": None,
        "workspace_conversations": None,
        "workspace_saved_reports": None,
        "workspace_answer_notes": None,
    }
    warnings: list[str] = []
    if db_exists:
        counts = _read_counts(db_path, counts.keys(), warnings)

    python_ok = sys.version_info >= (3, 10)
    database_ok = db_exists and (counts.get("workspaces") or 0) > 0
    local_db_protected = db_path.parent.name == ".ai-workbench"
    model_configured = settings.llm_provider.lower() != "fake" and settings.embedding_provider.lower() != "fake"
    qdrant_configured = settings.vector_store.lower() == "qdrant"

    items = [
        StartupChecklistItemResponse(
            id="python",
            title="Backend Python",
            status="ok" if python_ok else "blocked",
            summary=f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            detail="Python 3.10+ is required because the backend uses modern typing syntax such as str | None.",
            action_label=None if python_ok else "Recreate .venv with Python 3.12",
            copy_command="cd backend && rm -rf .venv && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" if not python_ok else None,
        ),
        StartupChecklistItemResponse(
            id="database",
            title="Workspace database",
            status="ok" if database_ok else "review",
            summary=(
                f"{counts.get('workspaces') or 0} workspace records in {db_path.name}"
                if db_exists
                else "No workspace database yet"
            ),
            detail=f"Active database path: {_display_path(db_path)}",
            action_label="Create or select a workspace" if not database_ok else None,
            copy_command=f"cp {_shell_quote(db_path)} {_shell_quote(db_path.with_suffix(db_path.suffix + '.backup'))}" if db_exists else None,
        ),
        StartupChecklistItemResponse(
            id="local-data-protection",
            title="Local data protection",
            status="ok" if local_db_protected else "review",
            summary="Runtime data is under backend/.ai-workbench" if local_db_protected else "Runtime DB path should be reviewed",
            detail="Generated update archives must never overwrite backend/.ai-workbench, *.db, or *.sqlite.",
            action_label="Use safe update script",
            copy_command="scripts/apply_generated_update.sh /path/to/unzipped/update ~/Documents/ai_workspace",
        ),
        StartupChecklistItemResponse(
            id="models",
            title="Local models",
            status="ok" if model_configured else "review",
            summary=f"LLM={settings.llm_provider}/{settings.ollama_llm_model}; embeddings={settings.embedding_provider}/{settings.ollama_embedding_model}",
            detail="For real local answers use Ollama for LLM and embeddings. Fake providers are useful only for tests/demo.",
            action_label="Start backend with Ollama env",
            copy_command="export LLM_PROVIDER=ollama EMBEDDING_PROVIDER=ollama OLLAMA_LLM_MODEL=llama3.2 OLLAMA_EMBEDDING_MODEL=nomic-embed-text",
        ),
        StartupChecklistItemResponse(
            id="search-context",
            title="Search context runtime",
            status="ok" if qdrant_configured else "review",
            summary=f"Vector store: {settings.vector_store}",
            detail="Use Qdrant for persistent local search context. Memory vector store is temporary and resets with the backend process.",
            action_label="Start backend with Qdrant",
            copy_command="export VECTOR_STORE=qdrant",
        ),
    ]
    if warnings:
        items.append(
            StartupChecklistItemResponse(
                id="diagnostics",
                title="Diagnostics warnings",
                status="review",
                summary=f"{len(warnings)} warning(s)",
                detail="; ".join(warnings),
            )
        )

    if any(item.status == "blocked" for item in items):
        status = "blocked"
    elif any(item.status == "review" for item in items):
        status = "review"
    else:
        status = "ok"

    return StartupChecklistResponse(
        status=status,
        summary="Ready for local work" if status == "ok" else "Review local runtime before relying on this workspace",
        items=items,
        safe_to_continue=status != "blocked",
        safety_note="This checklist is read-only. The frontend only displays/copies commands; it never executes shell commands.",
    )


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
                counts[name] = int(
                    connection.execute(f"select count(*) from {name}").fetchone()[0]
                )
    except sqlite3.Error as exc:
        warnings.append(f"Could not read workspace database diagnostics: {exc}")
        for table_name in table_names:
            counts[str(table_name)] = None
    return counts


def _display_path(path: Path) -> str:
    return str(path.expanduser())


def _shell_quote(path: Path) -> str:
    value = str(path)
    if not value:
        return "''"
    return "'" + value.replace("'", "'\\''") + "'"
