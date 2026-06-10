from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.api.schemas.local_data_safety_schemas import (
    CreateDatabaseBackupResponse,
    DatabaseBackupListResponse,
    DesktopStartupCommandResponse,
    DesktopStartupExperienceResponse,
    DatabaseBackupResponse,
    DatabaseMigrationSafetyResponse,
    DatabaseMigrationTableResponse,
    DatabaseRestorePlanRequest,
    DatabaseRestorePlanResponse,
    LocalDataBackupHintResponse,
    LocalDataSafetyResponse,
    PackagingOptionResponse,
    ProductionReadinessItemResponse,
    ProductionReadinessResponse,
    SafeUpdateWorkflowResponse,
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

    safe_update_excludes = _safe_update_excludes()
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
            copy_command="scripts/apply_generated_update.sh --dry-run /path/to/unzipped/update ~/Documents/ai_workspace",
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


@router.get("/update-safety", response_model=SafeUpdateWorkflowResponse)
def get_update_safety_workflow() -> SafeUpdateWorkflowResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    app_data_dir = settings.app_data_dir
    warnings: list[str] = []

    if not db_path.exists():
        warnings.append("Active workspace database does not exist yet. Create a workspace before relying on update backups.")
    if not db_path.is_absolute():
        warnings.append("Workspace DB path is relative; run update scripts from the ai_workspace project root or set WORKSPACE_DB_PATH explicitly.")
    if settings.workspace_repository.lower() != "sqlite":
        warnings.append("Workspace repository is not sqlite; backup guardrails may not protect all runtime data for this configuration.")

    required_excludes = _safe_update_excludes()
    target_root = "~/Documents/ai_workspace"
    source_root = "~/Documents/ai_workspace_taskXXX_work"
    return SafeUpdateWorkflowResponse(
        status="review" if warnings else "ok",
        summary="Use the generated update script with dry-run first, then apply with automatic DB backup.",
        script_path="scripts/apply_generated_update.sh",
        dry_run_command=f"scripts/apply_generated_update.sh --dry-run {source_root} {target_root}",
        apply_command=f"scripts/apply_generated_update.sh {source_root} {target_root}",
        required_excludes=required_excludes,
        backup_policy="The script creates a timestamped pre-update backup when backend/.ai-workbench/workspaces.db exists. Restore remains manual.",
        protected_paths=[_display_path(app_data_dir), _display_path(db_path)],
        preflight_checks=[
            "Unzip the generated archive into a temporary folder, not directly over ~/Documents/ai_workspace.",
            "Confirm the unzipped folder contains backend/ and frontend/ directly at its root.",
            "Run the script with --dry-run and review the file list before applying.",
            "Make sure backend/.ai-workbench, *.db, and *.sqlite are excluded from update copy operations.",
            "After applying, restart backend/frontend and check /runtime/local-data plus /runtime/database-migration-safety.",
        ],
        warnings=warnings,
        safety_note="This endpoint is read-only. The UI only displays commands; updates and restores remain explicit terminal actions.",
    )


@router.get("/desktop-startup", response_model=DesktopStartupExperienceResponse)
def get_desktop_startup_experience() -> DesktopStartupExperienceResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    db_exists = db_path.exists()
    warnings: list[str] = []
    counts: dict[str, int | None] = {"workspaces": None}
    if db_exists:
        counts = _read_counts(db_path, counts.keys(), warnings)
    workspaces_count = counts.get("workspaces") or 0
    status = "ok" if db_exists and workspaces_count > 0 and not warnings else "review"
    suggested_next_action = (
        "Open the last workspace from the sidebar or create a new workspace if this is a fresh database."
        if workspaces_count > 0
        else "Create a workspace, then run Preview rules, Scan project, and Build search context by explicit clicks."
    )
    return DesktopStartupExperienceResponse(
        status=status,
        summary=(
            f"Desktop-like startup is ready with {workspaces_count} workspace(s)."
            if status == "ok"
            else "Review local data and runtime readiness before daily work."
        ),
        open_last_workspace_enabled=True,
        last_workspace_storage_key="ai-private-workspace.last-workspace-id.v1",
        suggested_next_action=suggested_next_action,
        startup_commands=[
            DesktopStartupCommandResponse(
                label="Start backend",
                command="cd ~/Documents/ai_workspace/backend && source .venv/bin/activate && export VECTOR_STORE=qdrant EMBEDDING_PROVIDER=ollama OLLAMA_EMBEDDING_MODEL=nomic-embed-text LLM_PROVIDER=ollama OLLAMA_LLM_MODEL=llama3.2 && python -m uvicorn app.main:app --reload",
                description="Starts the local FastAPI backend with explicit local Ollama/Qdrant settings.",
            ),
            DesktopStartupCommandResponse(
                label="Start frontend",
                command="cd ~/Documents/ai_workspace/frontend && npm run dev",
                description="Starts the Vite development UI. The browser UI only calls local backend APIs.",
            ),
            DesktopStartupCommandResponse(
                label="Check runtime",
                command="cd ~/Documents/ai_workspace && scripts/check_runtime.sh",
                description="Runs copy-safe diagnostics for backend, frontend, DB, and local runtime readiness.",
            ),
        ],
        checklist=[
            "Open the UI after backend and frontend are running.",
            "The app restores the last selected workspace from browser localStorage when it still exists.",
            "If the database is fresh, create a workspace first and rebuild context by explicit user action.",
            "Run safe generated updates with dry-run first and keep backend/.ai-workbench excluded.",
        ],
        safety_notes=[
            "This endpoint is read-only and never starts processes.",
            "The frontend only displays or copies commands; it never executes shell commands.",
            "Open-last-workspace state is browser-local convenience only; workspace data remains in SQLite.",
        ],
    )


@router.get("/production-readiness", response_model=ProductionReadinessResponse)
def get_production_readiness() -> ProductionReadinessResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    warnings: list[str] = []
    counts: dict[str, int | None] = {
        "workspaces": None,
        "workspace_conversations": None,
        "workspace_saved_reports": None,
        "workspace_answer_notes": None,
    }
    if db_path.exists():
        counts = _read_counts(db_path, counts.keys(), warnings)

    checks: list[ProductionReadinessItemResponse] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        ProductionReadinessItemResponse(
            id="python-runtime",
            title="Python runtime",
            status="ok" if python_ok else "blocked",
            summary=f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            detail="Backend should run on Python 3.10+; Python 3.12 is preferred for local development.",
            recommended_action=None if python_ok else "Recreate backend/.venv with Python 3.12.",
        )
    )

    has_workspace = (counts.get("workspaces") or 0) > 0
    checks.append(
        ProductionReadinessItemResponse(
            id="workspace-data",
            title="Workspace data",
            status="ok" if has_workspace else "review",
            summary=f"{counts.get('workspaces') or 0} workspace(s) in local DB",
            detail=f"Active database: {_display_path(db_path)}",
            recommended_action="Create a workspace and build context before daily use." if not has_workspace else None,
        )
    )

    local_data_protected = db_path.parent.name == ".ai-workbench" and db_path.exists()
    checks.append(
        ProductionReadinessItemResponse(
            id="local-data-guardrails",
            title="Local data guardrails",
            status="ok" if local_data_protected else "review",
            summary="Runtime DB is under backend/.ai-workbench" if local_data_protected else "Runtime DB path needs review",
            detail="Generated update workflows must preserve backend/.ai-workbench and never copy *.db/*.sqlite from generated archives.",
            recommended_action="Use scripts/apply_generated_update.sh with --dry-run before every generated update.",
        )
    )

    model_ready = settings.llm_provider.lower() != "fake" and settings.embedding_provider.lower() != "fake"
    checks.append(
        ProductionReadinessItemResponse(
            id="local-ai-runtime",
            title="Local AI runtime",
            status="ok" if model_ready else "review",
            summary=f"LLM={settings.llm_provider}/{settings.ollama_llm_model}; embeddings={settings.embedding_provider}/{settings.ollama_embedding_model}",
            detail="Production-like local use should run with Ollama LLM and embedding providers, not fake test providers.",
            recommended_action="Start backend with LLM_PROVIDER=ollama and EMBEDDING_PROVIDER=ollama." if not model_ready else None,
        )
    )

    vector_ready = settings.vector_store.lower() == "qdrant"
    checks.append(
        ProductionReadinessItemResponse(
            id="persistent-vector-store",
            title="Persistent vector store",
            status="ok" if vector_ready else "review",
            summary=f"Vector store: {settings.vector_store}",
            detail="Use Qdrant for persistent local search context. Memory vector store is process-local only.",
            recommended_action="Start backend with VECTOR_STORE=qdrant." if not vector_ready else None,
        )
    )

    docs_ready = Path("../docs").exists() or Path("docs").exists()
    checks.append(
        ProductionReadinessItemResponse(
            id="operator-docs",
            title="Operator docs",
            status="ok" if docs_ready else "review",
            summary="Local runbooks are included" if docs_ready else "Docs directory not found from current working directory",
            detail="Runbooks should explain startup, backup/restore, safe updates, troubleshooting, and packaging choices.",
            recommended_action=None if docs_ready else "Start the backend from the project backend directory or verify docs are packaged.",
        )
    )

    if warnings:
        checks.append(
            ProductionReadinessItemResponse(
                id="diagnostic-warnings",
                title="Diagnostic warnings",
                status="review",
                summary=f"{len(warnings)} warning(s)",
                detail="; ".join(warnings),
                recommended_action="Review /runtime/local-data and /runtime/database-migration-safety.",
            )
        )

    ok_count = sum(1 for item in checks if item.status == "ok")
    blocked = any(item.status == "blocked" for item in checks)
    review = any(item.status == "review" for item in checks)
    status = "blocked" if blocked else "review" if review else "ok"
    score = round((ok_count / len(checks)) * 100) if checks else 0

    packaging_options = [
        PackagingOptionResponse(
            id="dev-scripts",
            title="Script-based local app",
            status="recommended-now",
            summary="Use the included scripts to start backend/frontend and keep updates explicit.",
            steps=[
                "Run scripts/check_runtime.sh before work.",
                "Start backend with scripts/start_backend.sh.",
                "Start frontend with scripts/start_frontend.sh.",
                "Use scripts/apply_generated_update.sh --dry-run before applying generated archives.",
            ],
            copy_commands=[
                "cd ~/Documents/ai_workspace && scripts/check_runtime.sh",
                "cd ~/Documents/ai_workspace && scripts/start_backend.sh",
                "cd ~/Documents/ai_workspace && scripts/start_frontend.sh",
            ],
        ),
        PackagingOptionResponse(
            id="mac-shortcuts",
            title="macOS shortcuts / launcher",
            status="next",
            summary="Create a small local launcher later; it should only call project scripts and never bypass safety checks.",
            steps=[
                "Keep backend/frontend startup in scripts.",
                "Add a macOS Automator/Shortcut wrapper only after scripts are stable.",
                "Show commands to the user before adding any auto-start behavior.",
            ],
            copy_commands=[
                "open ~/Documents/ai_workspace",
            ],
        ),
        PackagingOptionResponse(
            id="desktop-wrapper",
            title="Desktop wrapper",
            status="later",
            summary="A Tauri/Electron wrapper can be considered after local data safety and runtime scripts are stable.",
            steps=[
                "Keep the backend API local-only.",
                "Protect backend/.ai-workbench from app updates.",
                "Make backup/restore explicit before introducing packaged updates.",
            ],
            copy_commands=[],
        ),
    ]

    return ProductionReadinessResponse(
        status=status,
        summary="Ready for daily local use" if status == "ok" else "Production readiness needs review before daily use",
        readiness_score=score,
        items=checks,
        packaging_options=packaging_options,
        recommended_next_steps=[
            "Keep using script-based startup until packaging is stable.",
            "Create a DB backup before every generated update.",
            "Use dry-run apply workflow for generated archives.",
            "Only consider a desktop wrapper after scripts and backup/restore are reliable.",
        ],
        safety_note="This readiness report is read-only. The frontend only displays or copies commands and never executes shell commands.",
    )


@router.get("/database-backups", response_model=DatabaseBackupListResponse)
def list_database_backups() -> DatabaseBackupListResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    return DatabaseBackupListResponse(
        database_path=_display_path(db_path),
        backups=_list_backups(db_path),
        restore_note="Restore is intentionally manual. The UI only shows/copies commands so local data is never overwritten by a browser action.",
    )


@router.post("/database-backups", response_model=CreateDatabaseBackupResponse)
def create_database_backup() -> CreateDatabaseBackupResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Workspace database does not exist yet.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}-{timestamp}.backup{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    return CreateDatabaseBackupResponse(
        status="created",
        backup=_backup_response(backup_path, db_path),
        safety_note="Backup created by explicit user action. Restore remains manual to avoid accidental data loss.",
    )


@router.post("/database-restore-plan", response_model=DatabaseRestorePlanResponse)
def get_database_restore_plan(request: DatabaseRestorePlanRequest) -> DatabaseRestorePlanResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    backup_path = _resolve_backup(db_path, request.backup_filename)
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup file was not found next to the workspace database.")
    if backup_path.resolve() == db_path.resolve():
        raise HTTPException(status_code=400, detail="The current database cannot be used as a restore backup.")

    pre_restore_backup = db_path.with_suffix(db_path.suffix + ".before-restore")
    warnings = [
        "Stop the backend before restoring the database.",
        "Restore is manual by design; the frontend must never overwrite runtime data.",
    ]
    if not db_path.exists():
        warnings.append("Current database does not exist. The restore command will create it from the selected backup.")
    return DatabaseRestorePlanResponse(
        status="ready",
        backup=_backup_response(backup_path, db_path),
        steps=[
            "Stop the backend process.",
            "Create a before-restore copy of the current database if it exists.",
            "Copy the selected backup to the active workspaces.db path.",
            "Restart the backend and check /runtime/local-data.",
        ],
        copy_commands=[
            f"cp {_shell_quote(db_path)} {_shell_quote(pre_restore_backup)}" if db_path.exists() else "# current database does not exist; skip before-restore backup",
            f"cp {_shell_quote(backup_path)} {_shell_quote(db_path)}",
            "python -m uvicorn app.main:app --reload",
        ],
        warnings=warnings,
        safety_note="This endpoint only prepares a restore plan. It does not modify the active database.",
    )


@router.get("/database-migration-safety", response_model=DatabaseMigrationSafetyResponse)
def get_database_migration_safety() -> DatabaseMigrationSafetyResponse:
    settings = get_settings()
    db_path = settings.workspace_db_path
    expected_tables = [
        "workspaces",
        "project_scans",
        "workspace_index_status",
        "workspace_indexing_rules",
        "workspace_skill_profiles",
        "workspace_conversations",
        "workspace_conversation_messages",
        "workspace_answer_notes",
        "workspace_saved_reports",
        "workspace_timeline_events",
        "workspace_model_selections",
    ]
    warnings: list[str] = []
    tables: list[DatabaseMigrationTableResponse] = []
    if not db_path.exists():
        warnings.append("Workspace database does not exist yet.")
        for name in expected_tables:
            tables.append(DatabaseMigrationTableResponse(name=name, exists=False, row_count=None))
    else:
        table_counts = _read_counts(db_path, expected_tables, warnings)
        for name in expected_tables:
            exists = table_counts.get(name) is not None
            tables.append(DatabaseMigrationTableResponse(name=name, exists=exists, row_count=table_counts.get(name)))

    missing = [table.name for table in tables if not table.exists]
    if missing:
        warnings.append("Some known tables are missing. They may be created automatically by SQLite repositories when the feature is first used.")
    status = "review" if warnings else "ok"
    return DatabaseMigrationSafetyResponse(
        status=status,
        database_path=_display_path(db_path),
        schema_version="sqlite-auto-migrations-v1",
        tables=tables,
        missing_tables=missing,
        warnings=warnings,
        recommended_actions=[
            "Create a database backup before applying generated code updates.",
            "Keep backend/.ai-workbench excluded from rsync --delete updates.",
            "After update, check /runtime/local-data and /runtime/database-migration-safety.",
        ],
        safety_note="Migration safety diagnostics are read-only and do not modify the database.",
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



def _list_backups(db_path: Path) -> list[DatabaseBackupResponse]:
    if not db_path.parent.exists():
        return []
    patterns = [
        f"{db_path.stem}-*.backup{db_path.suffix}",
        f"{db_path.name}.backup*",
        f"{db_path.stem}*.backup",
    ]
    paths: dict[str, Path] = {}
    for pattern in patterns:
        for backup_path in db_path.parent.glob(pattern):
            if backup_path.is_file():
                paths[str(backup_path.resolve())] = backup_path
    return sorted(
        (_backup_response(path, db_path) for path in paths.values()),
        key=lambda item: item.created_at,
        reverse=True,
    )


def _backup_response(path: Path, db_path: Path) -> DatabaseBackupResponse:
    stat = path.stat()
    return DatabaseBackupResponse(
        filename=path.name,
        path=_display_path(path),
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        is_current_database=path.resolve() == db_path.resolve(),
    )


def _resolve_backup(db_path: Path, filename: str) -> Path:
    if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Backup filename must be a file next to the workspace database.")
    return db_path.parent / filename


def _safe_update_excludes() -> list[str]:
    return [
        "backend/.ai-workbench",
        "*.db",
        "*.sqlite",
        "*/.venv/*",
        "*/node_modules/*",
        "*/dist/*",
        "*/__pycache__/*",
        "*/.pytest_cache/*",
        "*.tsbuildinfo",
    ]


def _display_path(path: Path) -> str:
    return str(path.expanduser())


def _shell_quote(path: Path) -> str:
    value = str(path)
    if not value:
        return "''"
    return "'" + value.replace("'", "'\\''") + "'"
