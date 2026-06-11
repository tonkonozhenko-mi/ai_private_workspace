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
    DesktopPackagingDecisionResponse,
    DesktopPackagingDesignResponse,
    DesktopPackagingPhaseResponse,
    DesktopSupervisorContractResponse,
    DesktopSupervisorLogResponse,
    DesktopSupervisorPortResponse,
    DesktopSupervisorStateResponse,
    MacOSAppPackageArtifactResponse,
    MacOSAppPackageFoundationResponse,
    MacOSAppSupervisorWiringFileResponse,
    MacOSAppSupervisorWiringResponse,
    MacOSAppSupervisorWiringStepResponse,
    FirstLaunchChecklistItemResponse,
    FirstLaunchReadinessResponse,
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


@router.get("/desktop-packaging-design", response_model=DesktopPackagingDesignResponse)
def get_desktop_packaging_design() -> DesktopPackagingDesignResponse:
    return DesktopPackagingDesignResponse(
        status="locked",
        title="Real desktop app design lock",
        summary="Target architecture for a two-click local desktop app. Current scripts remain the safe bridge until the package is built.",
        chosen_shell="Tauri first",
        backend_strategy="Run the FastAPI backend as a supervised local child process owned by the desktop app, with a health check before opening the UI.",
        frontend_strategy="Build the Vite frontend into static assets and serve them inside the desktop shell instead of requiring npm run dev.",
        local_data_strategy="Keep runtime data in an app-owned local data directory and never overwrite backend/.ai-workbench, *.db, or *.sqlite during updates.",
        port_strategy="Use localhost only. Prefer a configured local port first, then a safe fallback if the port is busy. Never expose the API on the network by default.",
        logging_strategy="Write backend, frontend-shell, and model-download logs to a local logs directory with a visible troubleshooting path.",
        lifecycle_strategy="Double-click starts the desktop shell, starts/checks backend, opens the UI, restores last workspace, and shuts down only app-owned processes on exit.",
        decisions=[
            DesktopPackagingDecisionResponse(
                id="shell",
                title="Desktop shell",
                decision="Use Tauri first; keep Electron as fallback.",
                rationale="Tauri is lighter and closer to native desktop UX. Electron remains a practical fallback if Python/backend bundling becomes simpler there.",
            ),
            DesktopPackagingDecisionResponse(
                id="backend-supervisor",
                title="Backend supervisor",
                decision="Desktop shell owns backend lifecycle.",
                rationale="The user should not run backend scripts manually in the final product. The app should start, health-check, and stop the local backend safely.",
            ),
            DesktopPackagingDecisionResponse(
                id="model-downloads",
                title="Model downloads",
                decision="Backend-only, approved, allowlisted jobs.",
                rationale="Model downloads are long-running and shell-adjacent. They must stay behind explicit approval and backend-side validation.",
            ),
            DesktopPackagingDecisionResponse(
                id="mcp",
                title="MCP tools",
                decision="Registry/config first; execution later.",
                rationale="MCP tools can touch files or commands, so packaged app must keep them disabled until sandbox/allowlist execution exists.",
            ),
        ],
        phases=[
            DesktopPackagingPhaseResponse(
                id="phase-1-design",
                title="Design lock",
                status="current",
                summary="Freeze packaging architecture before adding app shell code.",
                deliverables=[
                    "Document shell/backend/data/logging decisions.",
                    "Keep script launcher as development bridge.",
                    "Make UI wording clear that repo scripts are temporary.",
                ],
            ),
            DesktopPackagingPhaseResponse(
                id="phase-2-macos",
                title="macOS app foundation",
                status="next",
                summary="Create first real .app wrapper with static frontend and supervised backend.",
                deliverables=[
                    "Build frontend assets for desktop shell.",
                    "Start backend from app-owned supervisor.",
                    "Open UI only after backend health is ready.",
                    "Write logs to local app data path.",
                ],
            ),
            DesktopPackagingPhaseResponse(
                id="phase-3-installer",
                title="Installer-grade packaging",
                status="later",
                summary="Move from developer package to downloadable app distribution.",
                deliverables=[
                    "macOS .dmg or signed .app direction.",
                    "Windows .exe/.msi direction.",
                    "Safe update and backup behavior.",
                ],
            ),
        ],
        user_experience=[
            "User downloads the app package.",
            "User double-clicks AI Private Workspace.",
            "App starts the local backend and checks health automatically.",
            "UI opens on a calm start screen with last workspace restored when possible.",
            "User chooses models and downloads them only after explicit approval.",
        ],
        safety_rules=[
            "Frontend never executes shell commands.",
            "Desktop shell may start only app-owned local processes.",
            "Backend API binds to localhost only by default.",
            "Runtime data is never overwritten by generated updates.",
            "Model downloads stay opt-in, allowlisted, backend-side jobs.",
            "MCP/tool execution stays disabled until sandbox/allowlist gates exist.",
        ],
        not_in_scope_now=[
            "Automatic MCP server execution.",
            "Remote/cloud sync.",
            "Silent model downloads during startup.",
            "Auto-updates that can touch workspace databases.",
        ],
    )


@router.get("/macos-app-package-foundation", response_model=MacOSAppPackageFoundationResponse)
def get_macos_app_package_foundation() -> MacOSAppPackageFoundationResponse:
    return MacOSAppPackageFoundationResponse(
        status="foundation",
        title="macOS app package foundation",
        summary="First concrete packaging foundation for a real double-click macOS app. It defines the app bundle skeleton, supervisor contract, build steps, and safe boundaries before introducing full Tauri code.",
        package_goal="Downloaded package -> double click AI Private Workspace.app -> app starts local backend -> UI opens after health is ready.",
        shell_choice="Tauri-first desktop shell; shell code comes after this packaging contract is stable.",
        build_script="scripts/package_macos_app_foundation.sh",
        app_bundle_name="AI Private Workspace.app",
        expected_output_path="build/macos/AI Private Workspace.app",
        launch_contract=[
            "The desktop shell owns app startup; the user should not run backend or frontend scripts in the final package.",
            "Frontend assets are built once and opened by the desktop shell as app content, not by npm run dev.",
            "Backend starts as an app-owned localhost-only process and must pass /health before the UI is considered ready.",
            "The last workspace may be restored only after the backend is healthy and local data path is confirmed.",
        ],
        supervisor_contract=[
            "Start only app-owned local processes.",
            "Bind backend to 127.0.0.1 by default and avoid network exposure.",
            "Write backend, shell, and model-download logs to a local logs directory.",
            "Stop only processes started by the app on exit; never kill unrelated user processes by port alone.",
            "Keep model downloads as backend-approved jobs, not shell commands from the frontend.",
        ],
        artifacts=[
            MacOSAppPackageArtifactResponse(
                name="Info.plist",
                purpose="macOS bundle metadata for the app skeleton.",
                path="build/macos/AI Private Workspace.app/Contents/Info.plist",
                included_in_generated_zip=False,
            ),
            MacOSAppPackageArtifactResponse(
                name="MacOS/AI Private Workspace",
                purpose="Temporary safe launcher stub for the bundle foundation; future Tauri binary replaces it.",
                path="build/macos/AI Private Workspace.app/Contents/MacOS/AI Private Workspace",
                included_in_generated_zip=False,
            ),
            MacOSAppPackageArtifactResponse(
                name="Resources/app/frontend",
                purpose="Static frontend build staged for app-shell consumption.",
                path="build/macos/AI Private Workspace.app/Contents/Resources/app/frontend",
                included_in_generated_zip=False,
            ),
            MacOSAppPackageArtifactResponse(
                name="Resources/app/backend",
                purpose="Backend source staged for the next supervisor/bundling step; runtime data is excluded.",
                path="build/macos/AI Private Workspace.app/Contents/Resources/app/backend",
                included_in_generated_zip=False,
            ),
        ],
        build_steps=[
            "Run frontend npm ci and npm run build to create frontend/dist.",
            "Run scripts/package_macos_app_foundation.sh from the project root.",
            "Inspect build/macos/AI Private Workspace.app before opening it.",
            "Use the bundle as a packaging skeleton, not as the final signed installer.",
        ],
        validation_steps=[
            "Verify frontend/dist exists before packaging.",
            "Verify backend/.ai-workbench, *.db, *.sqlite, node_modules, dist, and caches are not copied as runtime data.",
            "Verify the app bundle contains Info.plist, MacOS launcher stub, staged frontend assets, and staged backend source.",
            "Verify the launcher binds only to localhost and prints log locations instead of hiding failures.",
        ],
        safety_rules=[
            "Packaging script does not execute model downloads.",
            "Packaging script does not run scan, index, rebuild, restart, MCP, or agent tools.",
            "Generated app bundle lives under build/ and must not be committed into normal source archives.",
            "Runtime data is excluded from staged backend files.",
            "This foundation does not replace the backend approval gates or model download allowlist.",
        ],
        not_yet_included=[
            "Signed .app or .dmg distribution.",
            "Real Tauri backend supervisor implementation.",
            "Bundled Python runtime and dependency freezing.",
            "Auto-update system.",
            "Windows .exe/.msi package.",
        ],
        user_experience=[
            "Developer builds the package skeleton from source.",
            "The skeleton proves the bundle shape and local lifecycle contract.",
            "Next task replaces the temporary launcher stub with real app shell/supervisor work.",
            "Final target remains a normal macOS app opened by double click.",
        ],
    )


@router.get("/desktop-supervisor-contract", response_model=DesktopSupervisorContractResponse)
def get_desktop_supervisor_contract() -> DesktopSupervisorContractResponse:
    settings = get_settings()
    logs_dir = settings.app_data_dir / "logs"
    return DesktopSupervisorContractResponse(
        status="contract-ready",
        title="Desktop app supervisor contract",
        summary="Defines how the packaged desktop app starts, observes, and stops its app-owned local backend without exposing shell control to the frontend.",
        package_goal="Double click AI Private Workspace.app -> supervisor starts the local backend -> waits for /health -> opens the UI -> writes readable logs.",
        supervisor_script="scripts/desktop_supervisor_contract.sh",
        default_backend_port=8000,
        health_endpoint="http://127.0.0.1:8000/health",
        logs_directory=_display_path(logs_dir),
        data_directory=_display_path(settings.app_data_dir),
        port_rules=[
            DesktopSupervisorPortResponse(
                id="localhost-only",
                title="Bind locally",
                rule="Backend listens on 127.0.0.1 only.",
                reason="The packaged app is a private local workspace, not a LAN service.",
            ),
            DesktopSupervisorPortResponse(
                id="no-port-kill",
                title="Never kill by port",
                rule="If port 8000 is busy, the supervisor reports a friendly error instead of killing the process.",
                reason="Another app or dev backend may already own the port; the desktop shell must not destroy unrelated processes.",
            ),
            DesktopSupervisorPortResponse(
                id="future-port-selection",
                title="Future port selection",
                rule="Installer-grade packaging may allocate an app-owned port and pass it to the frontend via environment/config.",
                reason="This keeps multi-instance and corporate endpoint policies possible later.",
            ),
        ],
        startup_states=[
            DesktopSupervisorStateResponse(
                id="preflight",
                title="Preparing local runtime",
                user_message="Checking local app files and data paths…",
                technical_behavior="Create logs directory, validate backend entrypoint, and preserve existing runtime data.",
            ),
            DesktopSupervisorStateResponse(
                id="starting-backend",
                title="Starting private backend",
                user_message="Starting the local AI workspace engine…",
                technical_behavior="Start only the app-owned backend process with localhost binding and known environment variables.",
            ),
            DesktopSupervisorStateResponse(
                id="waiting-health",
                title="Waiting until ready",
                user_message="Almost ready. Waiting for the local backend health check…",
                technical_behavior="Poll /health with timeout and show logs path on failure.",
            ),
            DesktopSupervisorStateResponse(
                id="ready",
                title="Ready",
                user_message="AI Private Workspace is ready.",
                technical_behavior="Open the packaged UI after backend readiness is confirmed.",
            ),
            DesktopSupervisorStateResponse(
                id="failed",
                title="Could not start",
                user_message="The app could not start safely. Check the logs and try again.",
                technical_behavior="Do not hide startup errors; preserve logs and avoid killing unrelated processes.",
            ),
        ],
        log_streams=[
            DesktopSupervisorLogResponse(
                id="supervisor",
                title="Supervisor log",
                path=_display_path(logs_dir / "desktop-supervisor.log"),
                purpose="App lifecycle, preflight, startup states, and shutdown notes.",
            ),
            DesktopSupervisorLogResponse(
                id="backend",
                title="Backend log",
                path=_display_path(logs_dir / "backend.log"),
                purpose="FastAPI startup, health, and runtime errors.",
            ),
            DesktopSupervisorLogResponse(
                id="model-downloads",
                title="Model download log",
                path=_display_path(logs_dir / "model-downloads.log"),
                purpose="Approved backend model download jobs only.",
            ),
        ],
        environment_contract=[
            "APP_ENV=desktop",
            "HOST=127.0.0.1",
            "PORT=8000",
            "AI_WORKSPACE_APP_DATA_DIR points to the app-owned local data directory.",
            "MODEL_DOWNLOAD_EXECUTION_ENABLED remains false unless the trusted local runtime explicitly enables it.",
        ],
        shutdown_contract=[
            "Track only the backend PID started by the supervisor.",
            "On app exit, ask that PID to stop gracefully first.",
            "Never kill processes discovered only by port number.",
            "Leave workspace database and vector data untouched.",
        ],
        safety_rules=[
            "Frontend never executes shell commands.",
            "Desktop supervisor starts only app-owned local processes.",
            "No scan, index, rebuild, MCP, agent, or model download starts on app launch.",
            "Model downloads remain backend-approved allowlisted jobs.",
            "MCP execution remains disabled until sandbox/allowlist execution is implemented.",
            "Runtime data and databases are never packaged into generated source zips.",
        ],
        validation_steps=[
            "Run the supervisor contract script from project root in development mode.",
            "Verify logs are written under the app data logs directory.",
            "Verify /health is polled before opening the UI.",
            "Verify a busy port produces a friendly error and does not kill anything.",
            "Verify app exit stops only the PID started by the supervisor.",
        ],
        next_packaging_steps=[
            "Wire this contract into the macOS .app skeleton.",
            "Add a packaged UI startup screen for preparing/starting/ready/failed states.",
            "Freeze backend runtime/dependencies for installer-grade distribution.",
            "Repeat the supervisor contract for Windows service/process lifecycle.",
        ],
    )


@router.get("/macos-app-supervisor-wiring", response_model=MacOSAppSupervisorWiringResponse)
def get_macos_app_supervisor_wiring() -> MacOSAppSupervisorWiringResponse:
    settings = get_settings()
    logs_dir = settings.app_data_dir / "logs"
    return MacOSAppSupervisorWiringResponse(
        status="wired-foundation",
        title="macOS app wired to desktop supervisor",
        summary="Connects the generated .app bundle to the desktop supervisor contract: double-click starts an app-owned local backend, waits for /health, writes readable logs, and opens the packaged UI only after readiness.",
        package_goal="Double click AI Private Workspace.app -> supervisor preflight -> app-owned backend -> /health ready -> packaged UI opens.",
        build_script="scripts/package_macos_app_foundation.sh",
        app_bundle_path="build/macos/AI Private Workspace.app",
        launcher_path="build/macos/AI Private Workspace.app/Contents/MacOS/AI Private Workspace",
        app_data_directory=_display_path(settings.app_data_dir),
        logs_directory=_display_path(logs_dir),
        backend_health_url="http://127.0.0.1:8000/health",
        startup_flow=[
            MacOSAppSupervisorWiringStepResponse(
                id="preflight",
                title="Preflight",
                summary="Validate packaged backend/frontend resources and create local app data/log paths.",
                user_message="Preparing AI Private Workspace…",
            ),
            MacOSAppSupervisorWiringStepResponse(
                id="port-check",
                title="Safe port check",
                summary="If localhost:8000 already answers /health, reuse it; if the port is busy with something else, stop with a friendly error.",
                user_message="Checking the local workspace engine…",
            ),
            MacOSAppSupervisorWiringStepResponse(
                id="start-backend",
                title="Start app-owned backend",
                summary="Start FastAPI from the packaged backend source with localhost-only binding and app-owned data path.",
                user_message="Starting the private local engine…",
            ),
            MacOSAppSupervisorWiringStepResponse(
                id="wait-health",
                title="Wait for health",
                summary="Poll /health before opening UI; failures point to launch/backend logs instead of hiding errors.",
                user_message="Almost ready…",
            ),
            MacOSAppSupervisorWiringStepResponse(
                id="open-ui",
                title="Open packaged UI",
                summary="Open static frontend assets after backend readiness is confirmed.",
                user_message="Opening AI Private Workspace…",
            ),
        ],
        generated_files=[
            MacOSAppSupervisorWiringFileResponse(
                path="build/macos/AI Private Workspace.app/Contents/MacOS/AI Private Workspace",
                purpose="Executable launcher stub wired to the supervisor contract.",
                generated=True,
            ),
            MacOSAppSupervisorWiringFileResponse(
                path="build/macos/AI Private Workspace.app/Contents/Resources/app/frontend",
                purpose="Packaged static UI assets from frontend/dist.",
                generated=True,
            ),
            MacOSAppSupervisorWiringFileResponse(
                path="build/macos/AI Private Workspace.app/Contents/Resources/app/backend",
                purpose="Packaged backend source without runtime data, caches, databases, or virtual environments.",
                generated=True,
            ),
            MacOSAppSupervisorWiringFileResponse(
                path=_display_path(logs_dir / "macos-app-launcher.log"),
                purpose="Readable launcher lifecycle log in app data, outside the app bundle.",
                generated=False,
            ),
            MacOSAppSupervisorWiringFileResponse(
                path=_display_path(logs_dir / "backend.log"),
                purpose="Backend runtime log in app data, outside the app bundle.",
                generated=False,
            ),
        ],
        supervisor_guarantees=[
            "The .app launcher starts only the app-owned backend process.",
            "Backend binds to 127.0.0.1 by default.",
            "The UI opens only after /health succeeds.",
            "If the port is occupied by an unknown process, the launcher refuses to kill it.",
            "Logs are written outside the .app bundle so updates do not erase diagnostics.",
            "No scan, index, rebuild, MCP, agent workflow, or model download starts on launch.",
        ],
        user_experience=[
            "Developer builds the app foundation from source while packaging is still being finalized.",
            "User-facing target remains a normal double-click macOS app.",
            "Startup errors should be readable, calm, and actionable instead of silent terminal failures.",
            "Final signed package should remove the need to understand repo scripts.",
        ],
        validation_steps=[
            "Run frontend build before packaging.",
            "Run scripts/package_macos_app_foundation.sh from the project root.",
            "Open build/macos/AI Private Workspace.app and verify it waits for backend health before opening UI.",
            "Check logs under the app data logs directory if launch fails.",
            "Verify runtime data is not copied into the app bundle.",
        ],
        known_limitations=[
            "This is still a foundation bundle, not a signed .dmg installer.",
            "It still depends on local python3 and installed backend dependencies.",
            "It opens static frontend assets directly; the future Tauri shell should host them natively.",
            "Windows packaging is not implemented in this task.",
        ],
        next_steps=[
            "Freeze/bundle backend runtime dependencies for macOS.",
            "Replace launcher stub with Tauri supervisor shell.",
            "Add signed macOS distribution path.",
            "Create Windows packaging foundation with the same supervisor rules.",
        ],
    )


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
    ollama_selected = settings.llm_provider.lower() == "ollama" and settings.embedding_provider.lower() == "ollama"
    qdrant_selected = settings.vector_store.lower() == "qdrant"
    launcher_exists = (Path("../scripts/launch_macos.command").exists() or Path("scripts/launch_macos.command").exists())

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
            user_action=None if has_workspace else "Create or reopen a workspace after the app starts.",
        ),
        FirstLaunchChecklistItemResponse(
            id="local-ai-models",
            title="Local AI models",
            status="ok" if ollama_selected else "review",
            summary=f"LLM={settings.llm_provider}/{settings.ollama_llm_model}; embeddings={settings.embedding_provider}/{settings.ollama_embedding_model}",
            detail="This check only validates selected providers and model names. It does not pull or start models.",
            user_action=None if ollama_selected else "Use the guided model setup and start backend with Ollama providers when ready.",
        ),
        FirstLaunchChecklistItemResponse(
            id="search-context-store",
            title="Search context store",
            status="ok" if qdrant_selected else "review",
            summary=f"Vector store: {settings.vector_store}",
            detail="Persistent search context is expected to use Qdrant for packaging-ready local use.",
            user_action=None if qdrant_selected else "Use Qdrant before depending on persistent RAG answers.",
        ),
        FirstLaunchChecklistItemResponse(
            id="macos-launcher",
            title="macOS launcher",
            status="ok" if launcher_exists else "review",
            summary="launch_macos.command found" if launcher_exists else "Launcher script not found from current working directory",
            detail="The launcher is a user-started helper for backend/frontend only.",
            user_action=None if launcher_exists else "Run from the project root or verify scripts/launch_macos.command is packaged.",
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
        summary="Ready after launch" if status == "ok" else "Review post-launch checklist before daily use",
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
