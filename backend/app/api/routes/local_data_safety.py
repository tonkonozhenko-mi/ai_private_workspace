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
    BackendRuntimeBundleItemResponse,
    BackendRuntimeBundlePlanResponse,
    BackendRuntimeBundleStepResponse,
    DesktopRuntimeValidationCommandResponse,
    DesktopRuntimeReadinessItemResponse,
    DesktopRuntimeReadinessResponse,
    DesktopRuntimePreflightItemResponse,
    DesktopRuntimePreflightResponse,
    TauriShellScaffoldFileResponse,
    TauriShellScaffoldPhaseResponse,
    TauriShellScaffoldResponse,
    TauriSupervisorBridgeCommandResponse,
    TauriSupervisorBridgeResponse,
    TauriSupervisorBridgeStateResponse,
    TauriSupervisorStaticGateItemResponse,
    TauriSupervisorStaticGateResponse,
    DesktopTechnologyOptionResponse,
    DesktopTechnologyDecisionResponse,
    DesktopStackComponentResponse,
    DesktopRuntimeFreezeMilestoneResponse,
    DesktopStackAndRuntimeContractResponse,
    StagedBackendRuntimeItemResponse,
    StagedBackendRuntimeContractResponse,
    PyInstallerBackendRuntimeItemResponse,
    PyInstallerBackendRuntimeContractResponse,
    RuntimeSelectionCandidateResponse,
    FrozenBackendRuntimeSelectionResponse,
    FrozenBackendSmokeItemResponse,
    FrozenBackendSmokeContractResponse,
    AppOwnedBackendStartupGateItemResponse,
    AppOwnedBackendStartupGateResponse,
    AppOwnedBackendStartupImplementationItemResponse,
    AppOwnedBackendStartupImplementationResponse,
    AppOwnedBackendHealthReadinessItemResponse,
    AppOwnedBackendHealthReadinessResponse,
    MacOSTauriSmokeRunbookItemResponse,
    MacOSTauriSmokeRunbookResponse,
    MacOSPackagedAppSmokePreflightItemResponse,
    MacOSPackagedAppSmokePreflightResponse,
    PackagingToolchainPrerequisiteItemResponse,
    PackagingToolchainPrerequisitesResponse,
    TauriRustStructureRegistryItemResponse,
    TauriRustStructureRegistryResponse,
    TauriRustDependencyPinItemResponse,
    TauriRustDependencyPinsResponse,
    TauriIconAssetItemResponse,
    TauriIconAssetsResponse,
    TauriDevSmokeReadinessItemResponse,
    TauriDevSmokeReadinessResponse,
    WindowsPackagingArtifactResponse,
    WindowsPackagingFoundationResponse,
    WindowsPackagingPhaseResponse,
    ReleaseCandidateAuditCommandResponse,
    ReleaseCandidateAuditItemResponse,
    ReleaseCandidateAuditResponse,
    V01DemoStepResponse,
    V01HandoffResponse,
    V01RepositoryFileResponse,
    ProductCompletionStageResponse,
    ProductCompletionRoadmapResponse,
    FinalProductStageResponse,
    FinalProductStatusResponse,
    V01ReleaseGateItemResponse,
    V01ReleaseGateResponse,
    V01UISmokeCheckItemResponse,
    V01UISmokeCheckResponse,
    V01PublicationHandoffStepResponse,
    V01PublicationHandoffResponse,
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


@router.get("/tauri-shell-scaffold", response_model=TauriShellScaffoldResponse)
def get_tauri_shell_scaffold() -> TauriShellScaffoldResponse:
    return TauriShellScaffoldResponse(
        status="scaffolded",
        title="Tauri shell scaffold",
        summary="First source-controlled desktop shell foundation. It maps the existing supervisor contract into a future Tauri app without enabling frontend shell execution or automatic risky actions.",
        package_goal="Tauri shell starts -> supervisor starts app-owned localhost backend -> /health ready -> packaged UI opens.",
        shell_path="frontend/src-tauri",
        scaffold_script="scripts/prepare_tauri_shell_scaffold.sh",
        chosen_stack="Tauri first, with FastAPI as supervised localhost backend and Vite static assets as the UI.",
        supervisor_mapping=[
            "Tauri manages app window lifecycle; backend lifecycle remains app-owned and supervised.",
            "The UI calls localhost backend APIs only after health readiness.",
            "Startup states map to preparing, starting backend, waiting for health, ready, and failed.",
            "Logs stay under the app data directory, outside the app bundle and outside generated source zips.",
            "Model downloads remain backend-approved jobs; Tauri never runs ollama pull directly from the web UI.",
        ],
        generated_files=[
            TauriShellScaffoldFileResponse(
                path="frontend/src-tauri/tauri.conf.json",
                purpose="Tauri app metadata, window defaults, and build pointers for the Vite frontend.",
                generated=False,
            ),
            TauriShellScaffoldFileResponse(
                path="frontend/src-tauri/Cargo.toml",
                purpose="Minimal Rust package definition for the desktop shell scaffold.",
                generated=False,
            ),
            TauriShellScaffoldFileResponse(
                path="frontend/src-tauri/src/main.rs",
                purpose="Safe shell entrypoint placeholder. It opens the app window but does not execute project commands yet.",
                generated=False,
            ),
            TauriShellScaffoldFileResponse(
                path="scripts/prepare_tauri_shell_scaffold.sh",
                purpose="Read-only validation helper for the scaffold and expected frontend/backend packaging resources.",
                generated=False,
            ),
        ],
        implementation_phases=[
            TauriShellScaffoldPhaseResponse(
                id="scaffold",
                title="Shell scaffold",
                status="current",
                summary="Keep the initial Tauri files small, readable, and safe.",
                deliverables=[
                    "Commit frontend/src-tauri with minimal config and entrypoint.",
                    "Document how Tauri maps to backend supervisor states.",
                    "Do not add command execution from the frontend layer.",
                ],
            ),
            TauriShellScaffoldPhaseResponse(
                id="supervisor-bridge",
                title="Supervisor bridge",
                status="next",
                summary="Replace bash launcher behavior with Tauri-owned process lifecycle after the contract is stable.",
                deliverables=[
                    "Start the bundled backend from Tauri, not from browser UI code.",
                    "Poll /health before marking the app ready.",
                    "Show calm startup errors with links to local logs.",
                ],
            ),
            TauriShellScaffoldPhaseResponse(
                id="signed-package",
                title="Installer-grade package",
                status="later",
                summary="Move from developer scaffold to signed app distribution.",
                deliverables=[
                    "Bundle or freeze backend runtime.",
                    "Create macOS distribution artifact.",
                    "Keep runtime data outside app updates.",
                ],
            ),
        ],
        safety_rules=[
            "Frontend React code still never executes shell commands.",
            "Tauri shell may start only app-owned local processes after explicit packaging implementation.",
            "No scan, index, rebuild, MCP, agent workflow, or model download starts on app launch.",
            "Model downloads remain backend-side, allowlisted, explicit jobs.",
            "MCP execution stays disabled until sandbox/allowlist execution exists.",
            "Runtime data, databases, caches, and build artifacts are excluded from generated source archives.",
        ],
        validation_steps=[
            "Run npm build for the frontend.",
            "Run scripts/prepare_tauri_shell_scaffold.sh from project root.",
            "Verify frontend/src-tauri contains config, Cargo.toml, and src/main.rs.",
            "Verify the scaffold does not add shell execution to React code.",
            "Verify generated source zip excludes build/, node_modules, runtime DBs, and caches.",
        ],
        known_limitations=[
            "This task adds a Tauri scaffold, not a final signed .app/.dmg.",
            "The Tauri shell does not yet supervise a frozen backend binary.",
            "Rust/Tauri toolchain installation is not automated here.",
            "Windows packaging is still a separate foundation task.",
        ],
        next_steps=[
            "Implement the Tauri supervisor bridge for backend startup/readiness.",
            "Finish backend runtime bundling strategy.",
            "Create Windows packaging foundation with the same safety rules.",
            "Run a final release candidate audit after packaging paths are clear.",
        ],
    )


@router.get("/tauri-supervisor-bridge", response_model=TauriSupervisorBridgeResponse)
def get_tauri_supervisor_bridge() -> TauriSupervisorBridgeResponse:
    settings = get_settings()
    logs_dir = settings.app_data_dir / "logs"
    return TauriSupervisorBridgeResponse(
        status="foundation",
        title="Tauri supervisor bridge",
        summary="Maps the real desktop shell to the backend supervisor lifecycle: start app-owned backend, wait for health, open the UI, and show friendly errors without letting React execute shell commands.",
        package_goal="Double click the packaged app -> Tauri shell starts -> app-owned backend starts on localhost -> /health succeeds -> UI becomes ready.",
        bridge_file="frontend/src-tauri/src/main.rs",
        tauri_command_strategy="Expose small Tauri commands for startup status and log paths only. Process startup belongs to the native shell layer, never to React UI code.",
        backend_start_strategy="Future implementation starts the bundled backend executable/source from the Tauri process using app-owned paths and a localhost-only bind. Current scaffold records the contract but does not start processes yet.",
        readiness_strategy="Tauri polls http://127.0.0.1:8000/health and marks the app ready only after a successful response. If an unknown service owns the port, it fails calmly and points to logs.",
        log_strategy=f"Write launcher/backend logs under {_display_path(logs_dir)} and keep them outside source archives and app updates.",
        startup_states=[
            TauriSupervisorBridgeStateResponse(
                id="preflight",
                title="Preflight",
                user_message="Preparing your private workspace…",
                shell_behavior="Validate packaged frontend/backend resources, app data directory, log directory, and runtime manifest.",
            ),
            TauriSupervisorBridgeStateResponse(
                id="port-check",
                title="Safe port check",
                user_message="Checking the local workspace engine…",
                shell_behavior="Check localhost backend port without killing unknown processes.",
                backend_check="GET /health when a service answers on the expected port.",
            ),
            TauriSupervisorBridgeStateResponse(
                id="start-backend",
                title="Start app-owned backend",
                user_message="Starting the private local engine…",
                shell_behavior="Start only the backend packaged with this app and store its PID/log paths in app data.",
            ),
            TauriSupervisorBridgeStateResponse(
                id="wait-health",
                title="Wait for backend health",
                user_message="Almost ready…",
                shell_behavior="Poll health with timeout and produce a friendly error if startup fails.",
                backend_check="GET http://127.0.0.1:8000/health",
            ),
            TauriSupervisorBridgeStateResponse(
                id="ready",
                title="Ready",
                user_message="AI Private Workspace is ready.",
                shell_behavior="Show the packaged UI and let the user explicitly choose workspace/model actions.",
            ),
            TauriSupervisorBridgeStateResponse(
                id="failed",
                title="Friendly failure",
                user_message="The local engine could not start. Open logs for details.",
                shell_behavior="Do not hide errors in a terminal. Show log path, port guidance, and safe retry advice.",
            ),
        ],
        tauri_commands=[
            TauriSupervisorBridgeCommandResponse(
                name="get_supervisor_status",
                purpose="Return startup state, health URL, data/log directories, and user-facing message.",
                execution="read-only scaffold command",
            ),
            TauriSupervisorBridgeCommandResponse(
                name="get_supervisor_log_paths",
                purpose="Expose local log paths for troubleshooting without reading or uploading log contents.",
                execution="read-only scaffold command",
            ),
            TauriSupervisorBridgeCommandResponse(
                name="request_backend_start",
                purpose="Future native shell bridge to start only app-owned backend after packaging runtime is ready.",
                execution="not implemented in this task",
            ),
        ],
        implementation_steps=[
            "Keep React UI as a client of backend APIs only.",
            "Add Tauri-side startup status commands that are read-only first.",
            "Move backend process startup into native shell code after runtime bundling is stable.",
            "Poll /health before marking app ready.",
            "Surface calm startup errors and log paths in the desktop shell.",
        ],
        validation_steps=[
            "Run scripts/prepare_tauri_shell_scaffold.sh from the project root.",
            "Verify frontend/src-tauri/src/main.rs contains supervisor state commands but no arbitrary shell bridge.",
            "Verify React code does not call Tauri process APIs or shell commands.",
            "Verify app launch does not start scan/index/rebuild/MCP/agent/model downloads.",
            "Verify generated source zip excludes build/, dist/, node_modules, runtime DBs, caches, and app data.",
        ],
        safety_rules=[
            "React frontend never executes shell commands.",
            "Tauri shell may start only app-owned local backend processes after the runtime is bundled.",
            "Never kill unknown processes that happen to use the expected port.",
            "Backend binds to 127.0.0.1 by default.",
            "No scan, index, rebuild, MCP, agent workflow, or model download starts on app launch.",
            "Model downloads remain backend-side approved jobs with allowlisted models.",
        ],
        known_limitations=[
            "This task adds the Tauri supervisor bridge contract and read-only shell commands, not a signed installer.",
            "The backend process is not started by Tauri yet; that comes after runtime bundling/freeze is stable.",
            "Rust/Tauri toolchain installation is still manual for developers.",
            "Windows packaging remains a separate foundation task.",
        ],
        next_steps=[
            "Implement native backend process startup after runtime bundle is frozen or staged reliably.",
            "Add desktop startup screen that reads Tauri supervisor status before showing the full app.",
            "Create Windows packaging foundation with equivalent supervisor states and log rules.",
            "Run release candidate audit after macOS and Windows packaging paths are documented.",
        ],
    )


@router.get("/tauri-supervisor-static-gate", response_model=TauriSupervisorStaticGateResponse)
def get_tauri_supervisor_static_gate() -> TauriSupervisorStaticGateResponse:
    """Return the static safety gate for the read-only Tauri supervisor bridge."""
    root = Path(__file__).resolve().parents[4]
    bridge_file = root / "frontend" / "src-tauri" / "src" / "main.rs"
    check_script = root / "scripts" / "check_tauri_supervisor_bridge.sh"
    source = bridge_file.read_text(encoding="utf-8") if bridge_file.exists() else ""

    items = [
        TauriSupervisorStaticGateItemResponse(
            id="bridge-file",
            title="Tauri bridge source",
            status="ok" if bridge_file.exists() else "blocked",
            summary="frontend/src-tauri/src/main.rs exists" if bridge_file.exists() else "Tauri bridge source is missing",
            evidence="frontend/src-tauri/src/main.rs",
        ),
        TauriSupervisorStaticGateItemResponse(
            id="status-command",
            title="Read-only supervisor status command",
            status="ok" if "fn get_supervisor_status" in source else "blocked",
            summary="get_supervisor_status is present" if "fn get_supervisor_status" in source else "get_supervisor_status is missing",
            evidence="get_supervisor_status",
        ),
        TauriSupervisorStaticGateItemResponse(
            id="log-path-command",
            title="Read-only log path command",
            status="ok" if "fn get_supervisor_log_paths" in source else "blocked",
            summary="get_supervisor_log_paths is present" if "fn get_supervisor_log_paths" in source else "get_supervisor_log_paths is missing",
            evidence="get_supervisor_log_paths",
        ),
        TauriSupervisorStaticGateItemResponse(
            id="preflight-command",
            title="Read-only preflight command",
            status="ok" if "fn get_supervisor_preflight" in source else "blocked",
            summary="get_supervisor_preflight is present" if "fn get_supervisor_preflight" in source else "get_supervisor_preflight is missing",
            evidence="get_supervisor_preflight",
        ),
        TauriSupervisorStaticGateItemResponse(
            id="backend-start-disabled",
            title="Backend start disabled",
            status="ok" if "backend_start_enabled: false" in source else "blocked",
            summary="Tauri bridge exposes status/log paths but does not start the backend yet" if "backend_start_enabled: false" in source else "Backend start is not explicitly disabled",
            evidence="backend_start_enabled: false",
        ),
        TauriSupervisorStaticGateItemResponse(
            id="no-process-api",
            title="No process execution API",
            status="blocked" if any(token in source for token in ("std::process::Command", "Command::new", "std::process", "spawn(")) else "ok",
            summary="No process execution calls are present" if not any(token in source for token in ("std::process::Command", "Command::new", "std::process", "spawn(")) else "Process execution keywords found; keep Task 240 read-only",
            evidence="std::process::Command / Command::new / spawn(",
        ),
    ]
    status = "blocked" if any(item.status == "blocked" for item in items) else "ok"
    return TauriSupervisorStaticGateResponse(
        status=status,
        title="Tauri supervisor static gate",
        summary="Read-only Phase 22 gate for Tauri status/log-path commands before backend process startup is implemented.",
        check_script="scripts/check_tauri_supervisor_bridge.sh",
        bridge_file="frontend/src-tauri/src/main.rs",
        items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Tauri supervisor bridge check", command="scripts/check_tauri_supervisor_bridge.sh", purpose="Validate read-only Tauri commands and safety wording without starting backend processes."),
            DesktopRuntimeValidationCommandResponse(label="Desktop runtime preflight", command="scripts/check_desktop_runtime_preflight.sh", purpose="Validate runtime manifest, frontend build output, and packaging inputs."),
        ],
        safety_rules=[
            "Tauri commands are read-only in this stage.",
            "Backend startup stays disabled until runtime bundling is deterministic.",
            "React frontend still cannot execute shell commands.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
            "Unknown localhost processes must never be killed automatically.",
        ],
        next_steps=[
            "Use this gate before implementing app-owned backend startup.",
            "Next Phase 22 step should be frozen backend runtime selection/staging, not more v0.1 polish.",
        ],
    )


@router.get("/desktop-technology-decision", response_model=DesktopTechnologyDecisionResponse)
def get_desktop_technology_decision() -> DesktopTechnologyDecisionResponse:
    """Return the explicit desktop shell technology decision and alternatives."""
    return DesktopTechnologyDecisionResponse(
        status="reviewable",
        title="Desktop shell technology decision",
        summary="Tauri is the current candidate for the desktop shell, but it is not treated as an irreversible product decision. This record explains the choice, alternatives, and guardrails before v1.0 packaging is finalized.",
        current_candidate="Tauri-first desktop shell",
        decision_state="candidate locked for v0.2 exploration; replaceable before v1.0 signed installers",
        why_it_was_chosen=[
            "One React UI can be reused for macOS and Windows instead of maintaining two separate native interfaces.",
            "The app bundle can stay smaller than typical Chromium-bundled Electron apps because it uses the system webview.",
            "Rust native commands are a good fit for a narrow supervisor layer: status, log paths, health checks, and eventually app-owned backend startup.",
            "The current implementation keeps Tauri commands read-only, so React still cannot execute shell commands.",
            "It matches the product goal: downloaded package -> double click -> local backend -> local UI, without external services.",
        ],
        alternatives=[
            DesktopTechnologyOptionResponse(
                id="tauri",
                title="Tauri + React",
                status="current_candidate",
                summary="Best current balance for a small local-first desktop shell over the existing React frontend.",
                strengths=[
                    "Cross-platform macOS/Windows path with one frontend.",
                    "Small app shell compared with Electron-style bundles.",
                    "Native supervisor layer can be strictly allowlisted.",
                    "Good fit for local logs, app data paths, and readiness gates.",
                ],
                tradeoffs=[
                    "Requires Rust/Tauri toolchain for developers.",
                    "Uses platform webviews, so rendering can differ slightly by OS.",
                    "Final signing/notarization/installer flow still needs real validation.",
                ],
            ),
            DesktopTechnologyOptionResponse(
                id="electron",
                title="Electron + React",
                status="fallback_option",
                summary="Mature desktop packaging option, but usually heavier for a privacy-first local utility.",
                strengths=[
                    "Very mature ecosystem and many packaging examples.",
                    "Consistent Chromium rendering across platforms.",
                    "Large community and debugging resources.",
                ],
                tradeoffs=[
                    "Larger app size and higher memory footprint.",
                    "More surface area to harden for a local-first security model.",
                    "Still needs careful process-supervisor design.",
                ],
            ),
            DesktopTechnologyOptionResponse(
                id="native",
                title="Native SwiftUI + WinUI",
                status="not_recommended_for_now",
                summary="Best native feel, but it would split the product into separate macOS and Windows UI implementations.",
                strengths=[
                    "Excellent native OS integration.",
                    "Best platform-specific UX potential.",
                    "Clear access to OS app-data/log APIs.",
                ],
                tradeoffs=[
                    "Two frontend codebases to maintain.",
                    "Slower product delivery for a solo/early-stage project.",
                    "More duplicated QA across platforms.",
                ],
            ),
            DesktopTechnologyOptionResponse(
                id="browser_plus_launcher",
                title="Browser UI + local launcher scripts",
                status="v0.1_style_baseline",
                summary="Simplest for source release and development, but not the final user-friendly product.",
                strengths=[
                    "Easy to debug and explain.",
                    "No desktop toolchain required.",
                    "Good for GitHub source RC and demos.",
                ],
                tradeoffs=[
                    "Not a real double-click desktop app.",
                    "User still needs terminal/scripts.",
                    "Weak installer/update experience.",
                ],
            ),
        ],
        decision_guardrails=[
            "Tauri remains a candidate until a real macOS/Windows packaging spike passes.",
            "Frontend must never gain arbitrary shell execution through the desktop shell.",
            "Native commands must stay small, explicit, and allowlisted.",
            "Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "If Tauri increases complexity more than it reduces packaging risk, Electron or another shell can replace it before v1.0.",
        ],
        when_to_reconsider=[
            "Tauri packaging becomes unstable on target macOS/Windows versions.",
            "Webview differences break important UI flows.",
            "Signing/notarization/installer requirements are significantly simpler with another stack.",
            "The Rust supervisor layer becomes too complex for the project maintenance model.",
        ],
        next_steps=[
            "Keep Task 241 as the explicit decision record instead of treating Tauri as an invisible assumption.",
            "Before enabling backend startup from the shell, complete a frozen runtime/staging spike.",
            "Run one macOS and one Windows packaging proof before calling the choice final for v1.0.",
        ],
    )


@router.get("/desktop-stack-runtime-contract", response_model=DesktopStackAndRuntimeContractResponse)
def get_desktop_stack_runtime_contract() -> DesktopStackAndRuntimeContractResponse:
    """Return the selected open-source desktop stack and runtime freeze/staging contract."""
    return DesktopStackAndRuntimeContractResponse(
        status="accepted_for_v0.2",
        title="Desktop stack and runtime contract",
        summary="Locks the practical v0.2 direction: open-source/free components, one React UI for macOS and Windows, Tauri as the lightweight desktop shell candidate, and a staged backend runtime that must be deterministic before the shell starts it.",
        desktop_shell="Tauri + React, accepted for v0.2 unless the packaging spike proves it too costly",
        backend_runtime_strategy="Freeze/stage the Python backend runtime before enabling app-owned desktop startup; evaluate PyInstaller first, keep Nuitka or packaged Python as fallback paths.",
        frontend_strategy="React + TypeScript + Vite remains the shared UI because it already exists, builds fast, and can be reused in browser and desktop modes.",
        packaging_strategy="Start with developer-verifiable bundles and scripts, then move to signed macOS DMG and Windows installer after runtime freeze is stable.",
        stack_principles=[
            "Use open-source/free technologies by default.",
            "Keep one shared UI for macOS and Windows instead of two native codebases.",
            "Prefer lightweight tools with small operational surface area.",
            "Native desktop code must stay narrow: status, paths, health checks, and later app-owned backend lifecycle only.",
            "Every runtime-changing action must be explicit and testable.",
        ],
        selected_components=[
            DesktopStackComponentResponse(
                id="tauri",
                name="Tauri",
                role="Desktop shell and native supervisor bridge",
                license_model="Open source / free",
                why_selected="Best current balance for a lightweight cross-platform desktop app over the existing React UI.",
                maintenance_note="Keep Rust code small and allowlisted; reconsider before v1.0 if signing or Windows packaging becomes painful.",
            ),
            DesktopStackComponentResponse(
                id="react-vite",
                name="React + TypeScript + Vite",
                role="Shared frontend UI",
                license_model="Open source / free",
                why_selected="Already implemented, fast to build, familiar, and usable in both browser dev mode and desktop shell mode.",
                maintenance_note="Avoid adding desktop-only behavior to React; frontend remains display/copy/user-click only.",
            ),
            DesktopStackComponentResponse(
                id="fastapi",
                name="FastAPI",
                role="Local backend API",
                license_model="Open source / free",
                why_selected="Simple, productive Python backend with clear API boundaries and existing tests.",
                maintenance_note="Keep core logic outside FastAPI adapters to preserve clean architecture.",
            ),
            DesktopStackComponentResponse(
                id="sqlite-qdrant-ollama",
                name="SQLite + Qdrant + Ollama",
                role="Local persistence, vector search, and local model runtime",
                license_model="Open source / free for local development/use",
                why_selected="Matches the local-first privacy goal without requiring external services.",
                maintenance_note="Runtime data stays outside app bundles and must be excluded from source/release archives.",
            ),
            DesktopStackComponentResponse(
                id="pyinstaller-first",
                name="PyInstaller-first runtime freeze",
                role="Candidate for freezing/staging the backend runtime",
                license_model="Open source / free",
                why_selected="Most practical first spike for packaging a Python backend into an app-owned runtime on macOS and Windows.",
                maintenance_note="If binary size/startup/signing is bad, evaluate Nuitka or packaged Python without changing product architecture.",
            ),
        ],
        rejected_paths=[
            DesktopTechnologyOptionResponse(
                id="electron_first",
                title="Electron-first desktop shell",
                status="fallback_only",
                summary="Kept as fallback, but not selected now because it is usually heavier than needed for this product.",
                strengths=["Mature ecosystem", "Consistent Chromium rendering", "Many packaging examples"],
                tradeoffs=["Larger app size", "Higher memory footprint", "More surface area to harden"],
            ),
            DesktopTechnologyOptionResponse(
                id="separate_native_apps",
                title="Separate SwiftUI and WinUI apps",
                status="rejected_for_now",
                summary="Too much maintenance for this stage because it creates two UI products.",
                strengths=["Best native feel", "Deep OS integration"],
                tradeoffs=["Two UI codebases", "More QA", "Slower delivery"],
            ),
        ],
        runtime_freeze_milestones=[
            DesktopRuntimeFreezeMilestoneResponse(
                id="manifest",
                title="Runtime manifest",
                status="done_foundation",
                summary="Backend source and dependency manifest can be generated and checked before packaging.",
                exit_criteria=["Manifest contains requirements hash", "Runtime excludes are documented", "No launch actions are executed"],
            ),
            DesktopRuntimeFreezeMilestoneResponse(
                id="staged-runtime",
                title="Staged app-owned backend runtime",
                status="next",
                summary="Create a deterministic backend runtime directory that the desktop shell can later start safely.",
                exit_criteria=["Backend entrypoint exists", "Dependency lock/hash is recorded", "Logs/data paths are outside the bundle", "Health endpoint can be checked manually"],
            ),
            DesktopRuntimeFreezeMilestoneResponse(
                id="frozen-runtime",
                title="Frozen backend runtime",
                status="future",
                summary="Package backend runtime without requiring users to create a Python venv manually.",
                exit_criteria=["macOS smoke test passes", "Windows smoke test passes", "No runtime DB is bundled", "Startup and shutdown are app-owned"],
            ),
        ],
        staging_contract=[
            "Desktop shell may start only the staged app-owned backend runtime, never arbitrary user commands.",
            "Runtime staging must not include backend/.ai-workbench, databases, caches, node_modules, or build artifacts unrelated to the app package.",
            "App data and logs must be created under OS user data locations, not inside the app bundle.",
            "UI opens only after /health is ready or shows a calm local-log error screen.",
            "Port handling must never kill unknown processes; only a PID started by the app may be stopped by the app.",
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Release audit", command="./scripts/audit_release_candidate.sh", purpose="Check source/release hygiene before packaging work."),
            DesktopRuntimeValidationCommandResponse(label="Runtime manifest", command="scripts/prepare_macos_backend_runtime.sh", purpose="Generate the current backend runtime manifest foundation."),
            DesktopRuntimeValidationCommandResponse(label="Desktop preflight", command="scripts/check_desktop_runtime_preflight.sh", purpose="Validate runtime manifest, frontend build output, and desktop packaging inputs."),
            DesktopRuntimeValidationCommandResponse(label="Stack contract check", command="scripts/check_desktop_stack_contract.sh", purpose="Validate that the repository documents the selected open-source cross-platform stack and safety contract."),
        ],
        safety_rules=[
            "Frontend still cannot execute shell commands.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
            "Model downloads stay backend-side, opt-in, allowlisted, and explicitly approved.",
            "MCP servers/tools are not started automatically.",
            "Agent workflows remain approval-gated and do not execute tools automatically.",
        ],
        next_steps=[
            "Implement the staged backend runtime directory contract before enabling Tauri backend startup.",
            "Run a macOS packaging spike first, then validate Windows parity before calling the stack final for v1.0.",
            "Only after staging is deterministic, add app-owned backend start/stop in the Tauri supervisor.",
        ],
    )


@router.get("/staged-backend-runtime-contract", response_model=StagedBackendRuntimeContractResponse)
def get_staged_backend_runtime_contract() -> StagedBackendRuntimeContractResponse:
    """Return the staged backend runtime contract for the desktop app."""
    root = Path(__file__).resolve().parents[4]
    staging_script = root / "scripts" / "stage_backend_runtime.sh"
    check_script = root / "scripts" / "check_staged_backend_runtime.sh"
    stage_dir = root / "build" / "desktop" / "backend-runtime"
    manifest = stage_dir / "AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"
    launcher = stage_dir / "run_backend.sh"

    items = [
        StagedBackendRuntimeItemResponse(
            id="staging-script",
            title="Runtime staging script",
            status="ok" if staging_script.exists() else "blocked",
            summary="Creates a deterministic source-runtime staging directory without starting backend processes." if staging_script.exists() else "Runtime staging script is missing.",
            path="scripts/stage_backend_runtime.sh",
        ),
        StagedBackendRuntimeItemResponse(
            id="check-script",
            title="Runtime staging check",
            status="ok" if check_script.exists() else "blocked",
            summary="Validates staged runtime layout and forbidden artifacts." if check_script.exists() else "Runtime staging check script is missing.",
            path="scripts/check_staged_backend_runtime.sh",
        ),
        StagedBackendRuntimeItemResponse(
            id="manifest",
            title="Runtime manifest",
            status="ready_after_command" if not manifest.exists() else "ok",
            summary="Manifest is generated by scripts/stage_backend_runtime.sh and records source/runtime inputs.",
            path="build/desktop/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json",
        ),
        StagedBackendRuntimeItemResponse(
            id="launcher",
            title="Backend launcher",
            status="ready_after_command" if not launcher.exists() else "ok",
            summary="Launcher is generated for the staged source runtime; final frozen binary is still a later milestone.",
            path="build/desktop/backend-runtime/run_backend.sh",
        ),
        StagedBackendRuntimeItemResponse(
            id="frozen-binary",
            title="Frozen backend binary",
            status="future",
            summary="PyInstaller/Nuitka frozen runtime is intentionally not claimed as done in this task.",
            path=None,
        ),
    ]

    return StagedBackendRuntimeContractResponse(
        status="source_runtime_staging_ready",
        title="Staged backend runtime contract",
        summary="Adds the first practical runtime staging layer for the desktop app: deterministic source runtime layout, manifest, launcher, and validation script. It does not yet claim a final frozen backend binary.",
        staging_script="scripts/stage_backend_runtime.sh",
        check_script="scripts/check_staged_backend_runtime.sh",
        staging_directory="build/desktop/backend-runtime",
        launcher_path="build/desktop/backend-runtime/run_backend.sh",
        manifest_path="build/desktop/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json",
        items=items,
        runtime_contract=[
            "The staging command copies only backend source runtime inputs, not local databases, virtualenvs, caches, frontend build output, or user data.",
            "The staging command writes a manifest with requirements SHA256, Python version, source counts, and safety rules.",
            "The generated launcher starts only the local backend when explicitly executed by a trusted desktop supervisor or developer.",
            "Runtime data and logs stay in app-owned user data directories, outside the app bundle and outside the staged runtime.",
            "This is the bridge between v0.1 source release and future frozen PyInstaller/Nuitka backend runtime.",
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(
                label="Stage backend runtime",
                command="scripts/stage_backend_runtime.sh",
                purpose="Create build/desktop/backend-runtime with app source, requirements, manifest, and launcher.",
            ),
            DesktopRuntimeValidationCommandResponse(
                label="Check staged runtime",
                command="scripts/check_staged_backend_runtime.sh",
                purpose="Validate the generated staged runtime layout and forbidden artifacts.",
            ),
            DesktopRuntimeValidationCommandResponse(
                label="Desktop preflight",
                command="scripts/check_desktop_runtime_preflight.sh",
                purpose="Confirm desktop packaging preflight still sees the runtime direction and safety constraints.",
            ),
        ],
        safety_rules=[
            "Staging does not start the backend.",
            "Staging does not run scan, index, rebuild, MCP, Agent, model downloads, or arbitrary shell from frontend.",
            "Generated build/desktop output must not be committed or included in source release archives.",
            "The frontend still only displays commands/status; it does not execute the staging command.",
            "Final v1.0 still requires a frozen backend binary and signed installers.",
        ],
        next_steps=[
            "Wire macOS packaging foundation to prefer build/desktop/backend-runtime when present.",
            "Add a PyInstaller proof-of-concept for the backend runtime after source staging is stable.",
            "Enable Tauri backend startup only after staged/frozen runtime checks pass.",
            "Repeat the same staging contract on Windows before calling the desktop runtime production-ready.",
        ],
    )


@router.get("/pyinstaller-backend-runtime-contract", response_model=PyInstallerBackendRuntimeContractResponse)
def get_pyinstaller_backend_runtime_contract() -> PyInstallerBackendRuntimeContractResponse:
    """Return the PyInstaller frozen backend runtime proof-of-concept contract."""
    root = Path(__file__).resolve().parents[4]
    build_script = root / "scripts" / "build_pyinstaller_backend_runtime.sh"
    check_script = root / "scripts" / "check_pyinstaller_backend_runtime.sh"
    entrypoint = root / "backend" / "packaging" / "pyinstaller_backend_entrypoint.py"
    spec_file = root / "backend" / "packaging" / "ai_private_workspace_backend.spec"
    runtime_dir = root / "build" / "desktop" / "frozen-backend-runtime"
    manifest = runtime_dir / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"

    items = [
        PyInstallerBackendRuntimeItemResponse(
            id="entrypoint",
            title="Backend frozen-runtime entrypoint",
            status="ok" if entrypoint.exists() else "blocked",
            summary="Tiny PyInstaller entrypoint that starts app.main:app through Uvicorn and reads only explicit host/port environment variables." if entrypoint.exists() else "PyInstaller backend entrypoint is missing.",
            path="backend/packaging/pyinstaller_backend_entrypoint.py",
        ),
        PyInstallerBackendRuntimeItemResponse(
            id="spec",
            title="PyInstaller spec",
            status="ok" if spec_file.exists() else "blocked",
            summary="Proof-of-concept spec for building a single backend executable from the existing FastAPI app." if spec_file.exists() else "PyInstaller spec is missing.",
            path="backend/packaging/ai_private_workspace_backend.spec",
        ),
        PyInstallerBackendRuntimeItemResponse(
            id="build-script",
            title="Frozen runtime build script",
            status="ok" if build_script.exists() else "blocked",
            summary="Reproducible local build script; it fails with guidance if PyInstaller is not installed and never starts the backend." if build_script.exists() else "PyInstaller build script is missing.",
            path="scripts/build_pyinstaller_backend_runtime.sh",
        ),
        PyInstallerBackendRuntimeItemResponse(
            id="check-script",
            title="Frozen runtime check script",
            status="ok" if check_script.exists() else "blocked",
            summary="Static/safe gate that validates the PyInstaller PoC inputs and generated manifest when present." if check_script.exists() else "PyInstaller check script is missing.",
            path="scripts/check_pyinstaller_backend_runtime.sh",
        ),
        PyInstallerBackendRuntimeItemResponse(
            id="frozen-manifest",
            title="Frozen runtime manifest",
            status="ready_after_command" if not manifest.exists() else "ok",
            summary="Generated only after scripts/build_pyinstaller_backend_runtime.sh runs in a local packaging environment.",
            path="build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json",
        ),
    ]

    return PyInstallerBackendRuntimeContractResponse(
        status="pyinstaller_poc_ready",
        title="PyInstaller backend runtime proof-of-concept",
        summary="Adds a reproducible PyInstaller PoC path for freezing the FastAPI backend into an app-owned executable. This is the next runtime step after source staging, but it is still not a signed installer-grade v1.0 runtime.",
        builder="PyInstaller",
        build_script="scripts/build_pyinstaller_backend_runtime.sh",
        check_script="scripts/check_pyinstaller_backend_runtime.sh",
        entrypoint_path="backend/packaging/pyinstaller_backend_entrypoint.py",
        spec_path="backend/packaging/ai_private_workspace_backend.spec",
        frozen_runtime_dir="build/desktop/frozen-backend-runtime",
        manifest_path="build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json",
        items=items,
        runtime_contract=[
            "PyInstaller is the first frozen-backend candidate because it is open-source, free, cross-platform, and operationally simple for Python apps.",
            "The build script creates generated output only under build/desktop/frozen-backend-runtime and must not be committed.",
            "The frozen executable starts only the FastAPI backend on 127.0.0.1 using explicit environment variables from the desktop supervisor.",
            "The build command does not start backend, scan, index, rebuild, MCP, Agent, or model downloads.",
            "Nuitka or packaged Python runtime remain fallback paths if PyInstaller becomes unreliable for macOS/Windows packaging.",
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(
                label="Check PyInstaller PoC",
                command="scripts/check_pyinstaller_backend_runtime.sh",
                purpose="Validate frozen backend runtime inputs without requiring an actual binary build.",
            ),
            DesktopRuntimeValidationCommandResponse(
                label="Build PyInstaller runtime",
                command="scripts/build_pyinstaller_backend_runtime.sh",
                purpose="Build the local frozen backend runtime in a packaging environment where PyInstaller is installed.",
            ),
            DesktopRuntimeValidationCommandResponse(
                label="Desktop runtime preflight",
                command="scripts/check_desktop_runtime_preflight.sh",
                purpose="Confirm desktop packaging gates still pass after adding the frozen-runtime PoC.",
            ),
        ],
        safety_rules=[
            "Frontend still cannot execute shell commands or build the runtime.",
            "The build script never starts the backend process after building it.",
            "Generated build/desktop output is local-only and must not be committed to GitHub/source archives.",
            "Desktop startup must still not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "This is a PoC contract, not final signing/notarization or Windows installer completion.",
        ],
        next_steps=[
            "Run the PyInstaller build locally on macOS and record missing hidden imports or runtime issues.",
            "Add a smoke command that starts the frozen backend only in explicit developer mode and verifies /health.",
            "Teach Tauri supervisor to prefer frozen runtime when checks pass, otherwise keep backend startup disabled.",
            "Repeat the build/check path on Windows before declaring the runtime frozen for v1.0.",
        ],
    )


@router.get("/frozen-backend-runtime-selection", response_model=FrozenBackendRuntimeSelectionResponse)
def get_frozen_backend_runtime_selection() -> FrozenBackendRuntimeSelectionResponse:
    """Return the safe runtime selection contract for Tauri/future desktop startup."""
    root = Path(__file__).resolve().parents[4]
    frozen_manifest = root / "build" / "desktop" / "frozen-backend-runtime" / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
    staged_manifest = root / "build" / "desktop" / "backend-runtime" / "AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    check_script = root / "scripts" / "check_tauri_runtime_selection.sh"

    candidates = [
        RuntimeSelectionCandidateResponse(
            id="frozen-pyinstaller-runtime",
            title="Frozen PyInstaller backend runtime",
            status="ok" if frozen_manifest.exists() else "not_built_yet",
            path="build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json",
            selection_rule="Prefer this runtime when the manifest and backend executable exist and pass local smoke checks.",
            fallback_rule="If missing or unhealthy, do not auto-start an unknown backend; fall back to read-only status or developer staged runtime.",
        ),
        RuntimeSelectionCandidateResponse(
            id="staged-source-runtime",
            title="Staged source backend runtime",
            status="ok" if staged_manifest.exists() else "ready_after_command",
            path="build/desktop/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json",
            selection_rule="Use only as a developer fallback while frozen backend work is still in progress.",
            fallback_rule="If missing, keep backend startup disabled and show copyable preparation commands.",
        ),
        RuntimeSelectionCandidateResponse(
            id="external-dev-backend",
            title="External developer backend",
            status="manual_only",
            path="http://127.0.0.1:8000/health",
            selection_rule="Allowed only for local development when the user manually starts uvicorn.",
            fallback_rule="Never kill or replace an unknown process on the port.",
        ),
    ]

    return FrozenBackendRuntimeSelectionResponse(
        status="selection_contract_ready",
        title="Frozen backend runtime selection",
        summary="Defines how the desktop shell will choose between frozen backend, staged source runtime, and manually started developer backend without unsafe auto-execution.",
        selection_strategy="Prefer frozen app-owned runtime after manifest and health checks; use staged runtime only as a developer fallback; otherwise keep backend startup disabled.",
        tauri_bridge_file="frontend/src-tauri/src/main.rs",
        check_script="scripts/check_tauri_runtime_selection.sh",
        candidates=candidates,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check runtime selection bridge", command="scripts/check_tauri_runtime_selection.sh", purpose="Validate Tauri exposes runtime selection metadata while keeping backend process startup disabled."),
            DesktopRuntimeValidationCommandResponse(label="Check PyInstaller runtime", command="scripts/check_pyinstaller_backend_runtime.sh", purpose="Validate frozen runtime inputs and manifest when the binary has been built locally."),
            DesktopRuntimeValidationCommandResponse(label="Check staged runtime", command="scripts/stage_backend_runtime.sh && scripts/check_staged_backend_runtime.sh", purpose="Prepare and validate the developer fallback runtime layout."),
        ],
        safety_rules=[
            "Tauri runtime selection is read-only in this task; backend_start_enabled remains false.",
            "Frontend cannot execute shell commands or choose arbitrary executables.",
            "Desktop startup must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "The future supervisor may start only an app-owned runtime whose manifest passed checks.",
            "Unknown localhost processes must not be killed by port.",
        ],
        next_steps=[
            "Run PyInstaller build locally and inspect hidden-import/runtime issues.",
            "Add explicit developer-only frozen backend smoke command that starts the binary and checks /health.",
            "After smoke checks pass on macOS, enable Tauri app-owned backend startup behind a strict manifest gate.",
            "Repeat the same runtime selection checks on Windows before installer work.",
        ],
    )


@router.get("/frozen-backend-smoke-contract", response_model=FrozenBackendSmokeContractResponse)
def get_frozen_backend_smoke_contract() -> FrozenBackendSmokeContractResponse:
    """Return the explicit developer-only smoke contract for the frozen backend runtime."""
    root = Path(__file__).resolve().parents[4]
    smoke_script = root / "scripts" / "smoke_frozen_backend_runtime.sh"
    frozen_manifest = root / "build" / "desktop" / "frozen-backend-runtime" / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
    staged_manifest = root / "build" / "desktop" / "backend-runtime" / "AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json"
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"

    items = [
        FrozenBackendSmokeItemResponse(
            id="smoke-script",
            title="Developer-only smoke script",
            status="ok" if smoke_script.exists() else "blocked",
            summary="Starts only the app-owned frozen backend executable, waits for /health, and stops only the PID it created." if smoke_script.exists() else "Frozen backend smoke script is missing.",
            command="scripts/smoke_frozen_backend_runtime.sh",
        ),
        FrozenBackendSmokeItemResponse(
            id="frozen-manifest",
            title="Frozen runtime manifest",
            status="ready_after_build" if not frozen_manifest.exists() else "ok",
            summary="Generated by scripts/build_pyinstaller_backend_runtime.sh. The smoke script refuses to run without it.",
            command="scripts/build_pyinstaller_backend_runtime.sh",
        ),
        FrozenBackendSmokeItemResponse(
            id="staged-runtime-fallback",
            title="Staged source runtime fallback",
            status="ready_after_command" if not staged_manifest.exists() else "ok",
            summary="Developer fallback only. It is not the preferred runtime for installer-grade desktop startup.",
            command="scripts/stage_backend_runtime.sh && scripts/check_staged_backend_runtime.sh",
        ),
        FrozenBackendSmokeItemResponse(
            id="tauri-startup-gate",
            title="Tauri startup remains gated",
            status="ok" if tauri_bridge.exists() else "blocked",
            summary="Tauri can report runtime selection metadata, but backend startup remains disabled until smoke checks pass and a later task enables app-owned startup.",
            command="scripts/check_tauri_runtime_selection.sh",
        ),
    ]

    return FrozenBackendSmokeContractResponse(
        status="smoke_contract_ready",
        title="Frozen backend smoke contract",
        summary="Defines the explicit developer-only smoke path for validating a locally built frozen backend before Tauri is allowed to start it in a later phase.",
        smoke_script="scripts/smoke_frozen_backend_runtime.sh",
        smoke_mode="developer_only_explicit_command",
        health_url="http://127.0.0.1:8000/health",
        items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Build frozen backend runtime", command="scripts/build_pyinstaller_backend_runtime.sh", purpose="Create build/desktop/frozen-backend-runtime locally when PyInstaller is available."),
            DesktopRuntimeValidationCommandResponse(label="Check frozen backend runtime", command="scripts/check_pyinstaller_backend_runtime.sh", purpose="Validate frozen runtime files and manifest without starting it."),
            DesktopRuntimeValidationCommandResponse(label="Smoke frozen backend runtime", command="scripts/smoke_frozen_backend_runtime.sh", purpose="Explicitly start the app-owned frozen backend, verify /health, and stop only the spawned PID."),
            DesktopRuntimeValidationCommandResponse(label="Check runtime selection", command="scripts/check_tauri_runtime_selection.sh", purpose="Keep Tauri runtime selection read-only until smoke checks are proven."),
        ],
        safety_rules=[
            "The smoke script is developer-only and must be run manually from a terminal.",
            "It may start only the frozen app-owned backend executable generated under build/desktop/frozen-backend-runtime.",
            "It must stop only the PID it started; it must never kill unknown localhost processes by port.",
            "Frontend and React still cannot execute shell commands or run the smoke script.",
            "Desktop launch still must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
        ],
        next_steps=[
            "Run the PyInstaller build locally and fix hidden imports if the frozen executable does not start.",
            "Run scripts/smoke_frozen_backend_runtime.sh on macOS and record the result.",
            "After a passing smoke, enable Tauri app-owned backend startup behind manifest and PID gates.",
            "Repeat the same build/check/smoke path on Windows before installer work.",
        ],
    )


@router.get("/app-owned-backend-startup-gate", response_model=AppOwnedBackendStartupGateResponse)
def get_app_owned_backend_startup_gate() -> AppOwnedBackendStartupGateResponse:
    """Return the safe gate before Tauri may start an app-owned backend runtime."""
    root = Path(__file__).resolve().parents[4]
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    startup_check = root / "scripts" / "check_tauri_app_owned_startup_gate.sh"
    frozen_manifest = root / "build" / "desktop" / "frozen-backend-runtime" / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
    frozen_smoke = root / "scripts" / "smoke_frozen_backend_runtime.sh"

    required_gates = [
        AppOwnedBackendStartupGateItemResponse(
            id="tauri-startup-gate-command",
            title="Tauri startup gate command",
            status="ok" if tauri_bridge.exists() else "blocked",
            summary="Tauri exposes a read-only startup gate that documents whether backend startup may be enabled later; it still does not start processes.",
            command="scripts/check_tauri_app_owned_startup_gate.sh",
        ),
        AppOwnedBackendStartupGateItemResponse(
            id="frozen-runtime-manifest",
            title="Frozen runtime manifest",
            status="ready_after_build" if not frozen_manifest.exists() else "ok",
            summary="A future startup implementation may use only the app-owned frozen runtime manifest generated by the PyInstaller build.",
            command="scripts/build_pyinstaller_backend_runtime.sh && scripts/check_pyinstaller_backend_runtime.sh",
        ),
        AppOwnedBackendStartupGateItemResponse(
            id="developer-smoke",
            title="Developer smoke check",
            status="ok" if frozen_smoke.exists() else "blocked",
            summary="The frozen backend must pass explicit local smoke before Tauri startup can move from gate metadata to real process start.",
            command="scripts/smoke_frozen_backend_runtime.sh",
        ),
        AppOwnedBackendStartupGateItemResponse(
            id="no-arbitrary-process-control",
            title="No arbitrary process control",
            status="ok",
            summary="The current Tauri bridge remains free of generic shell execution, pkill, killall, taskkill, and kill-by-port behavior.",
            command="scripts/check_tauri_app_owned_startup_gate.sh",
        ),
    ]

    return AppOwnedBackendStartupGateResponse(
        status="startup_gate_ready",
        title="App-owned backend startup gate",
        summary="Defines the exact gate before the desktop shell can start the packaged backend: frozen manifest, explicit smoke pass, app-owned logs/data, PID-owned shutdown, and no risky launch side effects.",
        startup_mode="gate_metadata_only_no_process_start",
        tauri_bridge_file="frontend/src-tauri/src/main.rs",
        check_script="scripts/check_tauri_app_owned_startup_gate.sh",
        required_gates=required_gates,
        startup_contract=[
            "Prefer the frozen app-owned backend runtime over staged source runtime for packaged desktop startup.",
            "Start only the executable described by the app-owned frozen runtime manifest after smoke checks pass.",
            "Write backend logs under the app-owned logs directory, not inside the application bundle.",
            "Record the spawned PID and stop only that PID during app shutdown.",
            "If localhost port is already occupied by an unknown process, show a clear error and do not kill it.",
            "Open the UI only after /health responds successfully.",
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check startup gate", command="scripts/check_tauri_app_owned_startup_gate.sh", purpose="Validate Tauri startup gate metadata and safety boundaries before enabling real backend process startup."),
            DesktopRuntimeValidationCommandResponse(label="Check runtime selection", command="scripts/check_tauri_runtime_selection.sh", purpose="Validate frozen/staged/manual runtime selection metadata."),
            DesktopRuntimeValidationCommandResponse(label="Smoke frozen runtime", command="scripts/smoke_frozen_backend_runtime.sh", purpose="Explicit developer-only smoke for the frozen backend runtime before any Tauri startup enablement."),
        ],
        safety_rules=[
            "This task does not enable automatic backend startup from Tauri yet.",
            "React/frontend cannot execute shell commands.",
            "Tauri must not expose arbitrary command execution to the UI.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
            "No kill-by-port behavior is allowed; only PID-owned shutdown is acceptable.",
        ],
        next_steps=[
            "Build the frozen backend locally and run the smoke script.",
            "After a passing smoke, implement Tauri process startup against the frozen manifest only.",
            "Add PID file, health wait, log capture, and shutdown tests for macOS first.",
            "Repeat the same startup gate on Windows before installer work.",
        ],
    )


@router.get("/app-owned-backend-startup-implementation", response_model=AppOwnedBackendStartupImplementationResponse)
def get_app_owned_backend_startup_implementation() -> AppOwnedBackendStartupImplementationResponse:
    """Return the real-but-gated Tauri backend startup implementation status."""
    root = Path(__file__).resolve().parents[4]
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    check_script = root / "scripts" / "check_tauri_app_owned_backend_startup.sh"
    frozen_manifest = root / "build" / "desktop" / "frozen-backend-runtime" / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"

    bridge_text = tauri_bridge.read_text(encoding="utf-8") if tauri_bridge.exists() else ""
    items = [
        AppOwnedBackendStartupImplementationItemResponse(
            id="start-command",
            title="Tauri start command",
            status="ok" if "start_app_owned_backend_runtime" in bridge_text else "blocked",
            summary="Tauri exposes a narrow native command that can start only the app-owned backend runtime selected from the frozen manifest.",
            evidence="start_app_owned_backend_runtime",
            command="scripts/check_tauri_app_owned_backend_startup.sh",
        ),
        AppOwnedBackendStartupImplementationItemResponse(
            id="stop-command",
            title="PID-owned stop command",
            status="ok" if "stop_app_owned_backend_runtime" in bridge_text else "blocked",
            summary="Shutdown is limited to the backend child process spawned and stored by the Tauri supervisor; there is no kill-by-port behavior.",
            evidence="stop_app_owned_backend_runtime",
            command="scripts/check_tauri_app_owned_backend_startup.sh",
        ),
        AppOwnedBackendStartupImplementationItemResponse(
            id="process-status",
            title="Process status command",
            status="ok" if "get_app_owned_backend_process_status" in bridge_text else "blocked",
            summary="The shell can report runtime kind, PID, health URL, and logs without exposing arbitrary process control to React.",
            evidence="get_app_owned_backend_process_status",
            command="scripts/check_tauri_app_owned_backend_startup.sh",
        ),
        AppOwnedBackendStartupImplementationItemResponse(
            id="frozen-manifest",
            title="Frozen manifest gate",
            status="ready_after_local_build" if not frozen_manifest.exists() else "ok",
            summary="Real startup is gated by the generated frozen backend manifest. If it is missing, startup returns a clear blocked result instead of falling back to unknown commands.",
            evidence="build/desktop/frozen-backend-runtime/AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json",
            command="scripts/build_pyinstaller_backend_runtime.sh && scripts/check_pyinstaller_backend_runtime.sh",
        ),
        AppOwnedBackendStartupImplementationItemResponse(
            id="no-shell-exposure",
            title="No generic shell exposure",
            status="ok" if all(term not in bridge_text for term in ["pkill", "killall", "taskkill", "sh -c", "cmd /C"]) else "blocked",
            summary="The implementation uses Rust process APIs for one known backend executable; it does not expose shell strings, pkill, killall, taskkill, or kill-by-port behavior.",
            evidence="Command::new + stored child PID",
            command="scripts/check_tauri_app_owned_backend_startup.sh",
        ),
    ]

    status = "implementation_ready_after_local_frozen_build"
    if any(item.status == "blocked" for item in items):
        status = "blocked"

    return AppOwnedBackendStartupImplementationResponse(
        status=status,
        title="App-owned backend startup implementation",
        summary="Adds the first real Tauri supervisor lifecycle for starting a packaged app-owned backend runtime, while preserving strict manifest, port, PID, and no-auto-action gates.",
        startup_mode="real_tauri_process_start_gated_by_frozen_manifest",
        tauri_bridge_file="frontend/src-tauri/src/main.rs",
        check_script="scripts/check_tauri_app_owned_backend_startup.sh",
        runtime_priority=[
            "Frozen PyInstaller runtime from build/desktop/frozen-backend-runtime",
            "No automatic staged-source fallback for packaged startup",
            "External manually started backend only for development browser mode",
        ],
        implementation_items=items,
        tauri_commands=[
            "get_app_owned_backend_process_status",
            "start_app_owned_backend_runtime",
            "stop_app_owned_backend_runtime",
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check Tauri startup implementation", command="scripts/check_tauri_app_owned_backend_startup.sh", purpose="Validate that the Tauri supervisor exposes only narrow app-owned backend lifecycle commands and no generic shell execution."),
            DesktopRuntimeValidationCommandResponse(label="Build frozen backend", command="scripts/build_pyinstaller_backend_runtime.sh", purpose="Create the local frozen backend runtime manifest and executable used by the startup command."),
            DesktopRuntimeValidationCommandResponse(label="Smoke frozen backend", command="scripts/smoke_frozen_backend_runtime.sh", purpose="Validate the frozen backend outside Tauri before relying on desktop startup."),
        ],
        safety_rules=[
            "React/frontend still does not execute shell commands.",
            "Tauri may start only the executable named by the frozen backend manifest.",
            "If the backend port is already occupied, startup fails with a clear error and does not kill anything.",
            "Shutdown stops only the stored child process spawned by this app session.",
            "Desktop startup must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
        ],
        next_steps=[
            "Run PyInstaller build and frozen smoke locally on macOS.",
            "Run the Tauri shell locally and verify start/stop commands against the frozen runtime.",
            "After macOS is stable, repeat the same check on Windows.",
            "Then move to signed packaging/installer work.",
        ],
    )


@router.get("/app-owned-backend-health-readiness", response_model=AppOwnedBackendHealthReadinessResponse)
def get_app_owned_backend_health_readiness() -> AppOwnedBackendHealthReadinessResponse:
    """Return the Tauri /health readiness gate for app-owned backend startup."""
    root = Path(__file__).resolve().parents[4]
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    check_script = root / "scripts" / "check_tauri_backend_health_readiness.sh"
    bridge_text = tauri_bridge.read_text(encoding="utf-8") if tauri_bridge.exists() else ""

    items = [
        AppOwnedBackendHealthReadinessItemResponse(
            id="http-health-check",
            title="HTTP /health readiness",
            status="ok" if "backend_health_is_ready" in bridge_text and "GET /health HTTP/1.1" in bridge_text else "blocked",
            summary="Desktop readiness is based on an HTTP GET /health response, not only an open TCP port.",
            evidence="backend_health_is_ready + GET /health",
            command="scripts/check_tauri_backend_health_readiness.sh",
        ),
        AppOwnedBackendHealthReadinessItemResponse(
            id="health-wait",
            title="Wait for /health before ready",
            status="ok" if "wait_for_backend_health" in bridge_text else "blocked",
            summary="Tauri waits for backend /health before returning a successful startup status to the desktop shell.",
            evidence="wait_for_backend_health",
            command="scripts/check_tauri_backend_health_readiness.sh",
        ),
        AppOwnedBackendHealthReadinessItemResponse(
            id="failed-health-cleanup",
            title="PID-owned cleanup on failed readiness",
            status="ok" if "child.kill()" in bridge_text and "/health did not return HTTP 200" in bridge_text else "blocked",
            summary="If the spawned backend does not become healthy, the supervisor stops only the child process it just created.",
            evidence="child.kill + stored child process",
            command="scripts/check_tauri_backend_health_readiness.sh",
        ),
        AppOwnedBackendHealthReadinessItemResponse(
            id="tauri-contract-command",
            title="Read-only health contract command",
            status="ok" if "get_backend_health_readiness_contract" in bridge_text else "blocked",
            summary="Tauri exposes a read-only contract describing the /health gate without exposing arbitrary shell execution.",
            evidence="get_backend_health_readiness_contract",
            command="scripts/check_tauri_backend_health_readiness.sh",
        ),
    ]

    status = "health_readiness_gate_ready"
    if any(item.status == "blocked" for item in items):
        status = "blocked"

    return AppOwnedBackendHealthReadinessResponse(
        status=status,
        title="App-owned backend health readiness",
        summary="Hardens the real Tauri backend startup path so desktop readiness requires HTTP /health 200 instead of treating an open localhost port as success.",
        readiness_mode="http_get_health_must_return_200",
        health_url="http://127.0.0.1:8000/health",
        tauri_bridge_file="frontend/src-tauri/src/main.rs",
        check_script="scripts/check_tauri_backend_health_readiness.sh",
        implementation_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check Tauri health readiness", command="scripts/check_tauri_backend_health_readiness.sh", purpose="Validate HTTP /health readiness, failure cleanup, and no kill-by-port behavior."),
            DesktopRuntimeValidationCommandResponse(label="Check Tauri startup", command="scripts/check_tauri_app_owned_backend_startup.sh", purpose="Validate app-owned backend startup implementation and safety boundaries."),
            DesktopRuntimeValidationCommandResponse(label="Run macOS smoke", command="scripts/build_pyinstaller_backend_runtime.sh && scripts/smoke_frozen_backend_runtime.sh && cd frontend && npm run tauri dev", purpose="Locally prove frozen backend and desktop startup after the health gate is in place."),
        ],
        safety_rules=[
            "Do not treat an open TCP port as application readiness.",
            "Desktop startup is successful only after /health returns HTTP 200.",
            "If /health fails after spawning, stop only the spawned child process.",
            "Do not kill unknown processes by port.",
            "Do not start scan, index, rebuild, MCP, Agent, or model downloads during desktop launch.",
        ],
        next_steps=[
            "Run cargo check locally because the sandbox may not have Rust/Cargo installed.",
            "Build the frozen backend and run the frozen smoke script.",
            "Run Tauri dev smoke and confirm UI readiness follows /health, not TCP-only availability.",
            "After macOS passes, mirror the smoke on Windows.",
        ],
    )


@router.get("/macos-tauri-smoke-runbook", response_model=MacOSTauriSmokeRunbookResponse)
def get_macos_tauri_smoke_runbook() -> MacOSTauriSmokeRunbookResponse:
    """Return the explicit local macOS frozen runtime and Tauri smoke runbook."""
    root = Path(__file__).resolve().parents[4]
    frozen_manifest = root / "build" / "desktop" / "frozen-backend-runtime" / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    runbook = root / "docs" / "TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md"
    check_script = root / "scripts" / "check_macos_tauri_smoke_runbook.sh"

    steps = [
        MacOSTauriSmokeRunbookItemResponse(
            id="build-frozen-backend",
            title="Build frozen backend runtime",
            status="manual_required",
            summary="Create the local PyInstaller backend runtime and generated manifest on the developer Mac.",
            command="scripts/build_pyinstaller_backend_runtime.sh",
        ),
        MacOSTauriSmokeRunbookItemResponse(
            id="check-frozen-runtime",
            title="Check frozen backend runtime",
            status="ready_after_build" if not frozen_manifest.exists() else "ok",
            summary="Validate the generated frozen runtime manifest and executable before any Tauri startup test.",
            command="scripts/check_pyinstaller_backend_runtime.sh",
        ),
        MacOSTauriSmokeRunbookItemResponse(
            id="smoke-frozen-runtime",
            title="Smoke frozen backend runtime",
            status="manual_required",
            summary="Start only the generated backend executable, wait for /health, and stop only the PID created by the smoke script.",
            command="scripts/smoke_frozen_backend_runtime.sh",
        ),
        MacOSTauriSmokeRunbookItemResponse(
            id="check-tauri-startup",
            title="Check Tauri startup implementation",
            status="ok" if tauri_bridge.exists() else "blocked",
            summary="Verify the Tauri bridge exposes only the narrow app-owned backend lifecycle commands and no arbitrary shell execution.",
            command="scripts/check_tauri_app_owned_backend_startup.sh",
        ),
        MacOSTauriSmokeRunbookItemResponse(
            id="tauri-dev-smoke",
            title="Run Tauri local smoke",
            status="manual_required",
            summary="Run the desktop shell locally after frozen backend smoke passes, then verify startup, status, logs, and PID-owned shutdown.",
            command="cd frontend && npm run tauri dev",
        ),
    ]

    status = "ready_for_local_macos_smoke"
    if not runbook.exists() or not check_script.exists() or not tauri_bridge.exists():
        status = "blocked"

    return MacOSTauriSmokeRunbookResponse(
        status=status,
        title="macOS frozen runtime and Tauri smoke runbook",
        summary="Defines the shortest safe local path from source to a developer-verified macOS desktop smoke: build frozen backend, smoke it, then verify Tauri app-owned startup without frontend shell execution.",
        runbook_doc="docs/TASK249_MACOS_TAURI_SMOKE_RUNBOOK.md",
        check_script="scripts/check_macos_tauri_smoke_runbook.sh",
        platform="macOS first, Windows parity after macOS pass",
        prerequisites=[
            "Python virtualenv for backend tests and PyInstaller build.",
            "Node dependencies installed under frontend/ for Vite and Tauri dev mode.",
            "Rust/Cargo and Tauri prerequisites installed locally on the developer Mac.",
            "Port 8000 free before frozen/Tauri startup smoke.",
        ],
        smoke_steps=steps,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check runbook files", command="scripts/check_macos_tauri_smoke_runbook.sh", purpose="Validate that Task 249 runbook, scripts, Tauri commands, and safety wording are present."),
            DesktopRuntimeValidationCommandResponse(label="Build frozen backend", command="scripts/build_pyinstaller_backend_runtime.sh", purpose="Generate the local frozen backend runtime used by Tauri."),
            DesktopRuntimeValidationCommandResponse(label="Smoke frozen backend", command="scripts/smoke_frozen_backend_runtime.sh", purpose="Validate the frozen backend outside Tauri first."),
            DesktopRuntimeValidationCommandResponse(label="Check Tauri startup", command="scripts/check_tauri_app_owned_backend_startup.sh", purpose="Validate the Tauri bridge safety boundaries."),
            DesktopRuntimeValidationCommandResponse(label="Run Tauri smoke locally", command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml && npm run tauri dev", purpose="Compile and manually smoke the desktop shell on macOS."),
        ],
        pass_criteria=[
            "Frozen backend build creates a manifest and executable under build/desktop/frozen-backend-runtime.",
            "Frozen backend smoke returns /health successfully and stops only the spawned PID.",
            "Tauri command status shows app-owned runtime paths and no generic shell execution.",
            "The desktop UI opens only after backend health is ready.",
            "Logs are written under the app-owned logs directory, not inside the app bundle.",
        ],
        fail_fast_conditions=[
            "Port 8000 is already occupied by an unknown process.",
            "PyInstaller build does not produce the frozen runtime manifest.",
            "Frozen backend /health does not answer during the smoke timeout.",
            "Tauri bridge contains shell escape patterns, pkill, killall, taskkill, or kill-by-port behavior.",
            "Desktop launch triggers scan, index, rebuild, MCP, Agent, or model downloads without explicit user action.",
        ],
        safety_rules=[
            "React/frontend still cannot execute shell commands.",
            "Tauri may start only the executable referenced by the app-owned frozen backend manifest.",
            "Shutdown is PID-owned; do not kill unknown localhost processes by port.",
            "No scan, index, rebuild, MCP server, agent workflow, or model download starts on desktop launch.",
            "Windows parity starts only after this macOS path is locally proven.",
        ],
        next_steps=[
            "Run the Task 249 local smoke sequence on the Mac and capture any PyInstaller/Tauri errors.",
            "Fix hidden imports or resource paths found by the frozen runtime smoke.",
            "After macOS Tauri startup is proven, mirror the runtime smoke contract on Windows.",
            "Then move to signed DMG/MSI packaging and update flow work.",
        ],
    )


@router.get("/macos-packaged-app-smoke-preflight", response_model=MacOSPackagedAppSmokePreflightResponse)
def get_macos_packaged_app_smoke_preflight() -> MacOSPackagedAppSmokePreflightResponse:
    """Return the local macOS packaged-app smoke preflight checklist."""
    root = Path(__file__).resolve().parents[4]
    package_json = root / "frontend" / "package.json"
    package_lock = root / "frontend" / "package-lock.json"
    tauri_bridge = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    tauri_config = root / "frontend" / "src-tauri" / "tauri.conf.json"
    frozen_manifest = root / "build" / "desktop" / "frozen-backend-runtime" / "AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json"

    package_text = package_json.read_text(encoding="utf-8") if package_json.exists() else ""
    lock_text = package_lock.read_text(encoding="utf-8") if package_lock.exists() else ""
    bridge_text = tauri_bridge.read_text(encoding="utf-8") if tauri_bridge.exists() else ""

    items = [
        MacOSPackagedAppSmokePreflightItemResponse(
            id="tauri-cli-script",
            title="Tauri CLI npm scripts",
            status="ok" if '"tauri": "tauri"' in package_text and '"tauri:dev": "tauri dev"' in package_text else "blocked",
            summary="Frontend package exposes npm run tauri dev and npm run tauri:dev so the smoke runbook is executable.",
            command="cd frontend && npm run tauri dev",
        ),
        MacOSPackagedAppSmokePreflightItemResponse(
            id="tauri-cli-lockfile",
            title="Tauri CLI lockfile",
            status="ok" if "node_modules/@tauri-apps/cli" in lock_text else "blocked",
            summary="package-lock.json includes @tauri-apps/cli, so npm ci can install the desktop CLI reproducibly.",
            command="cd frontend && npm ci",
        ),
        MacOSPackagedAppSmokePreflightItemResponse(
            id="tauri-config",
            title="Tauri config",
            status="ok" if tauri_config.exists() else "blocked",
            summary="Tauri config is present for macOS dev/package smoke.",
            command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml",
        ),
        MacOSPackagedAppSmokePreflightItemResponse(
            id="health-readiness",
            title="HTTP health readiness",
            status="ok" if "GET /health HTTP/1.1" in bridge_text and "wait_for_backend_health" in bridge_text else "blocked",
            summary="Desktop readiness requires HTTP /health 200, not TCP-only availability.",
            command="scripts/check_tauri_backend_health_readiness.sh",
        ),
        MacOSPackagedAppSmokePreflightItemResponse(
            id="frozen-manifest",
            title="Frozen runtime manifest",
            status="ready_after_local_build" if not frozen_manifest.exists() else "ok",
            summary="Frozen backend manifest is generated locally and should not be committed in source archives.",
            command="scripts/build_pyinstaller_backend_runtime.sh && scripts/check_pyinstaller_backend_runtime.sh",
        ),
    ]

    status = "ready_after_local_frozen_build"
    if any(item.status == "blocked" for item in items):
        status = "blocked"

    return MacOSPackagedAppSmokePreflightResponse(
        status=status,
        title="macOS packaged app smoke preflight",
        summary="Makes the macOS/Tauri smoke path reproducible by adding npm Tauri CLI wiring, lockfile support, and a single preflight checklist before packaged app smoke.",
        runbook_doc="docs/TASK251_MACOS_PACKAGED_APP_SMOKE_PREFLIGHT.md",
        check_script="scripts/check_macos_packaged_app_smoke_preflight.sh",
        package_manager="npm + package-lock.json",
        desktop_shell="Tauri + React",
        preflight_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check packaged app smoke preflight", command="scripts/check_macos_packaged_app_smoke_preflight.sh", purpose="Validate npm/Tauri CLI wiring, Rust scaffold, frozen runtime gates, and safety boundaries before package smoke."),
            DesktopRuntimeValidationCommandResponse(label="Build and smoke frozen backend", command="scripts/build_pyinstaller_backend_runtime.sh && scripts/check_pyinstaller_backend_runtime.sh && scripts/smoke_frozen_backend_runtime.sh", purpose="Generate the local frozen backend runtime and prove /health before Tauri smoke."),
            DesktopRuntimeValidationCommandResponse(label="Run Tauri dev smoke", command="cd frontend && npm ci && npm run build && cargo check --manifest-path src-tauri/Cargo.toml && npm run tauri dev", purpose="Run the macOS desktop shell against the app-owned backend lifecycle."),
        ],
        pass_criteria=[
            "npm ci installs @tauri-apps/cli from package-lock.json.",
            "npm run tauri dev is available.",
            "cargo check passes locally on macOS.",
            "Frozen backend smoke passes before Tauri startup is trusted.",
            "Tauri reports ready only after HTTP /health returns 200.",
        ],
        safety_rules=[
            "React/frontend does not execute shell commands.",
            "Tauri exposes only app-owned backend lifecycle commands.",
            "No generic shell execution is exposed to the UI.",
            "No pkill, killall, taskkill, or kill-by-port behavior.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
        ],
        next_steps=[
            "Run the preflight and frozen backend smoke locally on macOS.",
            "Run npm run tauri dev and verify start/health/stop behavior.",
            "After dev smoke passes, run npm run tauri:build and inspect packaged app resources.",
            "Then mirror the same smoke path on Windows before installer work.",
        ],
    )





@router.get("/tauri-rust-structure-registry", response_model=TauriRustStructureRegistryResponse)
def get_tauri_rust_structure_registry() -> TauriRustStructureRegistryResponse:
    root = Path(__file__).resolve().parents[4]
    main_rs = root / "frontend" / "src-tauri" / "src" / "main.rs"
    lib_rs = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    cargo_toml = root / "frontend" / "src-tauri" / "Cargo.toml"
    package_lock = root / "frontend" / "package-lock.json"

    lock_text = package_lock.read_text(encoding="utf-8") if package_lock.exists() else ""
    internal_registry_found = any(token in lock_text for token in ["applied-caas", "internal.api.openai", "artifactory"])
    main_text = main_rs.read_text(encoding="utf-8") if main_rs.exists() else ""
    lib_text = lib_rs.read_text(encoding="utf-8") if lib_rs.exists() else ""
    cargo_text = cargo_toml.read_text(encoding="utf-8") if cargo_toml.exists() else ""

    items = [
        TauriRustStructureRegistryItemResponse(
            id="cargo-library-contract",
            title="Cargo library contract",
            status="ok" if 'name = "ai_private_workspace_lib"' in cargo_text and lib_rs.exists() else "blocked",
            summary="Cargo declares ai_private_workspace_lib and frontend/src-tauri/src/lib.rs exists.",
            command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml",
        ),
        TauriRustStructureRegistryItemResponse(
            id="thin-main-entrypoint",
            title="Thin Tauri main entrypoint",
            status="ok" if "ai_private_workspace_lib::run();" in main_text else "blocked",
            summary="main.rs delegates to the library run function instead of duplicating supervisor logic.",
            command="scripts/check_tauri_rust_structure_and_registry.sh",
        ),
        TauriRustStructureRegistryItemResponse(
            id="supervisor-library",
            title="Supervisor library implementation",
            status="ok" if "pub fn run()" in lib_text and "start_app_owned_backend_runtime" in lib_text else "blocked",
            summary="lib.rs owns the Tauri command registration and app-owned backend lifecycle implementation.",
            command="scripts/check_tauri_rust_structure_and_registry.sh",
        ),
        TauriRustStructureRegistryItemResponse(
            id="public-npm-lockfile",
            title="Public npm lockfile",
            status="blocked" if internal_registry_found else "ok",
            summary="package-lock.json must not contain internal sandbox/OpenAI registry URLs.",
            command="grep -R -E 'applied-caas|internal.api.openai|artifactory' frontend/package-lock.json",
        ),
    ]

    status = "blocked" if any(item.status == "blocked" for item in items) else "ready"
    return TauriRustStructureRegistryResponse(
        status=status,
        title="Tauri Rust structure and registry guard",
        summary="Validates the Cargo library layout required by Tauri and guards npm lockfiles against internal registry URLs.",
        check_script="scripts/check_tauri_rust_structure_and_registry.sh",
        rust_entrypoint="frontend/src-tauri/src/main.rs",
        rust_library="frontend/src-tauri/src/lib.rs",
        npm_registry_policy="frontend/package-lock.json must resolve packages from the public npm registry, not internal sandbox registries.",
        validation_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check Tauri Rust structure", command="scripts/check_tauri_rust_structure_and_registry.sh", purpose="Validate main.rs/lib.rs layout, manifest-gated startup commands, and npm registry hygiene."),
            DesktopRuntimeValidationCommandResponse(label="Frontend build", command="cd frontend && npm ci && npm run build", purpose="Validate public npm lockfile and production frontend build."),
            DesktopRuntimeValidationCommandResponse(label="Cargo check", command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml", purpose="Validate the Tauri Rust manifest and library structure locally."),
        ],
        safety_rules=[
            "Frontend React code must not execute shell commands.",
            "Tauri startup is limited to the app-owned frozen backend runtime selected by manifest.",
            "Do not use internal package registry URLs in committed lockfiles.",
            "Do not kill unknown processes or ports.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
        ],
        next_steps=[
            "Run npm ci after ensuring npm registry points to https://registry.npmjs.org/.",
            "Run cargo check locally now that Cargo is installed.",
            "Run npm run tauri dev after the frozen backend runtime smoke succeeds.",
        ],
    )



@router.get("/tauri-rust-dependency-pins", response_model=TauriRustDependencyPinsResponse)
def get_tauri_rust_dependency_pins() -> TauriRustDependencyPinsResponse:
    root = Path(__file__).resolve().parents[4]
    cargo_toml = root / "frontend" / "src-tauri" / "Cargo.toml"
    cargo_lock = root / "frontend" / "src-tauri" / "Cargo.lock"
    gitignore = root / ".gitignore"

    cargo_text = cargo_toml.read_text(encoding="utf-8") if cargo_toml.exists() else ""
    lock_text = cargo_lock.read_text(encoding="utf-8") if cargo_lock.exists() else ""
    gitignore_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    lock_has_known_bad_time = 'name = "time"' in lock_text and 'version = "0.3.48"' in lock_text

    items = [
        TauriRustDependencyPinItemResponse(
            id="time-cookie-compatibility-pin",
            title="time/cookie compatibility pin",
            status="ok" if 'time = "=0.3.36"' in cargo_text else "blocked",
            summary="Cargo.toml pins time to =0.3.36 to avoid the cookie 0.18.x E0119 conflict seen on the local macOS Rust toolchain.",
            command="cd frontend && cargo update --manifest-path src-tauri/Cargo.toml -p time --precise 0.3.36 && cargo check --manifest-path src-tauri/Cargo.toml",
        ),
        TauriRustDependencyPinItemResponse(
            id="cargo-lock-refresh",
            title="Cargo.lock refresh",
            status="review" if lock_has_known_bad_time else "ok",
            summary="Cargo.lock should be refreshed locally after the time pin so cargo check does not keep the known-bad time 0.3.48 resolution.",
            command="cd frontend && cargo update --manifest-path src-tauri/Cargo.toml -p time --precise 0.3.36",
        ),
        TauriRustDependencyPinItemResponse(
            id="tauri-target-gitignore",
            title="Tauri target gitignore",
            status="ok" if "frontend/src-tauri/target/" in gitignore_text else "blocked",
            summary="frontend/src-tauri/target is a Rust build cache and must not be committed or included in release zips.",
            command="git status --short frontend/src-tauri/target",
        ),
    ]

    status = "blocked" if any(item.status == "blocked" for item in items) else "ready"
    return TauriRustDependencyPinsResponse(
        status=status,
        title="Tauri Rust dependency pins",
        summary="Documents and validates the local fix for the cookie/time Rust dependency conflict plus Tauri target build-cache hygiene.",
        check_script="scripts/check_tauri_rust_dependency_pins.sh",
        cargo_toml_policy="Pin time =0.3.36 until cookie/Tauri dependency resolution is upgraded and verified on macOS and Windows.",
        gitignore_policy="frontend/src-tauri/target/ is local Rust build output and must never be committed.",
        validation_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check Rust dependency pins", command="scripts/check_tauri_rust_dependency_pins.sh", purpose="Validate the time pin, Cargo.lock refresh guidance, and Tauri target gitignore rule."),
            DesktopRuntimeValidationCommandResponse(label="Refresh Cargo lock", command="cd frontend && cargo update --manifest-path src-tauri/Cargo.toml -p time --precise 0.3.36", purpose="Resolve Cargo.lock to the pinned time version before cargo check."),
            DesktopRuntimeValidationCommandResponse(label="Cargo check", command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml", purpose="Validate the Tauri Rust app locally after dependency resolution."),
        ],
        safety_rules=[
            "This change only pins Rust dependencies and ignores local build output.",
            "It does not add frontend shell execution.",
            "It does not start scan, index, rebuild, MCP, Agent, or model downloads.",
            "frontend/src-tauri/target must stay local-only.",
        ],
        next_steps=[
            "Run the dependency pin check script.",
            "Refresh Cargo.lock using cargo update -p time --precise 0.3.36.",
            "Run cargo check locally and upload the next zip if another Rust dependency blocker appears.",
        ],
    )

@router.get("/packaging-toolchain-prerequisites", response_model=PackagingToolchainPrerequisitesResponse)
def get_packaging_toolchain_prerequisites() -> PackagingToolchainPrerequisitesResponse:
    root = Path(__file__).resolve().parents[4]
    requirements = root / "backend" / "requirements.txt"
    spec_file = root / "backend" / "packaging" / "ai_private_workspace_backend.spec"
    package_json = root / "frontend" / "package.json"
    check_script = root / "scripts" / "check_packaging_toolchain_prerequisites.sh"

    items = [
        PackagingToolchainPrerequisiteItemResponse(
            id="pyinstaller-dependency",
            title="PyInstaller dependency",
            status="ok" if requirements.exists() and "pyinstaller" in requirements.read_text().lower() else "blocked",
            summary="backend/requirements.txt declares PyInstaller so the frozen backend build script can run after npm/pip setup.",
            command="cd backend && python3 -m pip install -r requirements.txt",
        ),
        PackagingToolchainPrerequisiteItemResponse(
            id="pyinstaller-spec-path",
            title="PyInstaller spec path resolution",
            status="ok" if spec_file.exists() and "SPECPATH" in spec_file.read_text() else "blocked",
            summary="The spec resolves the entrypoint from its own directory, avoiding duplicated backend/packaging paths.",
            command="scripts/build_pyinstaller_backend_runtime.sh",
        ),
        PackagingToolchainPrerequisiteItemResponse(
            id="tauri-cli",
            title="Tauri CLI npm script",
            status="ok" if package_json.exists() and "@tauri-apps/cli" in package_json.read_text() else "blocked",
            summary="frontend/package.json declares Tauri CLI scripts used by macOS desktop smoke tests.",
            command="cd frontend && npm ci",
        ),
        PackagingToolchainPrerequisiteItemResponse(
            id="cargo",
            title="Rust/Cargo for Tauri",
            status="manual",
            summary="Cargo is required locally for cargo check and npm run tauri dev/build. It is installed outside the repository.",
            command="brew install rust",
        ),
    ]

    return PackagingToolchainPrerequisitesResponse(
        status="ready",
        title="Packaging toolchain prerequisites",
        summary="Developer-machine prerequisites for building the frozen backend and running Tauri smoke tests.",
        check_script="scripts/check_packaging_toolchain_prerequisites.sh",
        pyinstaller_dependency="pyinstaller>=6.0,<7.0",
        cargo_install_options=[
            "Preferred on macOS with Homebrew: brew install rust",
            "Alternative cross-platform installer: rustup from https://rustup.rs",
            "After install, verify with: cargo --version",
        ],
        prerequisite_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Install backend packaging deps", command="cd backend && python3 -m pip install -r requirements.txt", purpose="Install PyInstaller in the backend virtual environment before frozen runtime build."),
            DesktopRuntimeValidationCommandResponse(label="Check packaging toolchain", command="scripts/check_packaging_toolchain_prerequisites.sh", purpose="Validate PyInstaller dependency, spec path handling, Tauri CLI scripts, and Cargo availability."),
            DesktopRuntimeValidationCommandResponse(label="Build frozen backend", command="scripts/build_pyinstaller_backend_runtime.sh", purpose="Create the local PyInstaller frozen backend runtime."),
            DesktopRuntimeValidationCommandResponse(label="Check Tauri locally", command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml", purpose="Validate Rust/Tauri compile readiness on the developer machine."),
        ],
        safety_rules=[
            "Installing Cargo/Rust is a developer-machine prerequisite, not an app startup action.",
            "Building PyInstaller runtime does not start scan, index, rebuild, MCP, Agent, or model downloads.",
            "Frontend still cannot execute shell commands.",
            "Generated build/desktop artifacts must not be committed.",
        ],
        next_steps=[
            "Install backend requirements in the local .venv.",
            "Install Cargo on macOS if cargo --version is missing.",
            "Run the frozen backend build and smoke scripts.",
            "Run cargo check and npm run tauri dev from frontend.",
        ],
    )



@router.get("/tauri-icon-assets", response_model=TauriIconAssetsResponse)
def get_tauri_icon_assets() -> TauriIconAssetsResponse:
    root = Path(__file__).resolve().parents[4]
    icons_dir = root / "frontend" / "src-tauri" / "icons"
    lib_rs = root / "frontend" / "src-tauri" / "src" / "lib.rs"
    required = {
        "icon.png": (512, 512),
        "32x32.png": (32, 32),
        "128x128.png": (128, 128),
        "128x128@2x.png": (256, 256),
    }

    items: list[TauriIconAssetItemResponse] = []
    for name, expected in required.items():
        path = icons_dir / name
        status = "blocked"
        summary = "Missing required Tauri icon asset."
        if path.exists():
            info = _read_png_header(path)
            if info is None:
                summary = "Icon exists but is not a valid PNG file."
            else:
                width, height, bit_depth, color_type = info
                if (width, height) == expected and bit_depth == 8 and color_type == 6:
                    status = "ok"
                    summary = f"{name} is {width}x{height} 8-bit RGBA PNG."
                else:
                    summary = f"{name} must be {expected[0]}x{expected[1]} 8-bit RGBA PNG; got {width}x{height}, bit_depth={bit_depth}, color_type={color_type}."
        items.append(
            TauriIconAssetItemResponse(
                id=name.replace("@", "-").replace(".", "-"),
                title=name,
                status=status,
                summary=summary,
                path=f"frontend/src-tauri/icons/{name}",
                command="scripts/check_tauri_icon_assets.sh",
            )
        )

    lib_text = lib_rs.read_text(encoding="utf-8") if lib_rs.exists() else ""
    items.append(
        TauriIconAssetItemResponse(
            id="rust-unused-path-import",
            title="Rust unused Path import",
            status="blocked" if "use std::path::{Path, PathBuf};" in lib_text else "ok",
            summary="frontend/src-tauri/src/lib.rs should import PathBuf only to keep cargo check warning-free.",
            path="frontend/src-tauri/src/lib.rs",
            command="scripts/check_tauri_icon_assets.sh",
        )
    )

    status = "blocked" if any(item.status == "blocked" for item in items) else "ready"
    return TauriIconAssetsResponse(
        status=status,
        title="Tauri icon assets",
        summary="Validates the RGBA PNG icon assets required by Tauri's generate_context macro and keeps cargo check warning-free.",
        check_script="scripts/check_tauri_icon_assets.sh",
        icons_directory="frontend/src-tauri/icons",
        required_icons=list(required.keys()),
        validation_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Check Tauri icon assets", command="scripts/check_tauri_icon_assets.sh", purpose="Validate required RGBA PNG icons and Rust import hygiene."),
            DesktopRuntimeValidationCommandResponse(label="Cargo check", command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml", purpose="Verify Tauri generate_context can read icon assets locally."),
            DesktopRuntimeValidationCommandResponse(label="Tauri dev smoke", command="cd frontend && npm run tauri dev", purpose="Run the local desktop shell after frozen backend smoke passes."),
        ],
        safety_rules=[
            "Icon checks are read-only and do not start backend processes.",
            "Frontend React code still does not execute shell commands.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
            "Tauri app-owned startup remains gated by frozen runtime manifest and /health readiness.",
        ],
        next_steps=[
            "Run scripts/check_tauri_icon_assets.sh from the project root.",
            "Run cargo check locally on macOS now that the required icons exist.",
            "If cargo check passes, continue to npm run tauri dev after frozen backend smoke.",
        ],
    )


@router.get("/tauri-dev-smoke-readiness", response_model=TauriDevSmokeReadinessResponse)
def get_tauri_dev_smoke_readiness() -> TauriDevSmokeReadinessResponse:
    root = Path(__file__).resolve().parents[4]
    checks = [
        (
            "cargo-check",
            "Cargo check passed locally",
            "ok",
            "User reported that `cargo check --manifest-path src-tauri/Cargo.toml` now passes after the icon/RGBA and Rust dependency fixes.",
            "cd frontend && cargo check --manifest-path src-tauri/Cargo.toml",
        ),
        (
            "tauri-dev",
            "Tauri dev smoke starts",
            "ok",
            "User reported that `npm run tauri dev` now starts successfully. This confirms the Tauri scaffold is no longer only theoretical.",
            "cd frontend && npm run tauri dev",
        ),
        (
            "target-hygiene",
            "Tauri target is ignored",
            "ok" if "frontend/src-tauri/target/" in (root / ".gitignore").read_text(encoding="utf-8") else "blocked",
            "Rust build output must stay local and must not be committed or included in source release archives.",
            "git check-ignore frontend/src-tauri/target || true",
        ),
        (
            "frozen-manifest-gate",
            "Frozen runtime manifest gate remains required",
            "ok",
            "Tauri app-owned backend startup remains gated by the frozen runtime manifest and HTTP `/health` readiness. Dev-mode success does not weaken runtime safety.",
            "scripts/check_tauri_app_owned_backend_startup.sh",
        ),
        (
            "registry-hygiene",
            "Public npm registry hygiene",
            "ok",
            "The npm lockfile must not include internal registry URLs, so contributors can run `npm ci` outside this environment.",
            "scripts/check_tauri_rust_structure_and_registry.sh",
        ),
    ]

    items = [
        TauriDevSmokeReadinessItemResponse(
            id=item_id,
            title=title,
            status=status,
            summary=summary,
            command=command,
        )
        for item_id, title, status, summary, command in checks
    ]
    status = "blocked" if any(item.status == "blocked" for item in items) else "ready"
    return TauriDevSmokeReadinessResponse(
        status=status,
        title="Tauri dev smoke readiness",
        summary="Records that the local macOS Tauri development shell now starts successfully and defines the next safe path from dev smoke to packaged app smoke.",
        milestone="Task 256 — Tauri dev smoke success recorded",
        check_script="scripts/check_tauri_dev_smoke_readiness.sh",
        local_success_reported=True,
        readiness_items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Tauri dev smoke readiness", command="scripts/check_tauri_dev_smoke_readiness.sh", purpose="Verify the source tree still contains the files and guardrails needed for local Tauri dev smoke."),
            DesktopRuntimeValidationCommandResponse(label="Cargo check", command="cd frontend && cargo check --manifest-path src-tauri/Cargo.toml", purpose="Compile-check the Tauri Rust shell locally."),
            DesktopRuntimeValidationCommandResponse(label="Tauri dev", command="cd frontend && npm run tauri dev", purpose="Run the local desktop shell smoke after cargo check passes."),
            DesktopRuntimeValidationCommandResponse(label="Frozen backend smoke", command="scripts/build_pyinstaller_backend_runtime.sh && scripts/check_pyinstaller_backend_runtime.sh && scripts/smoke_frozen_backend_runtime.sh", purpose="Validate the app-owned backend runtime that packaged Tauri should supervise."),
        ],
        safety_rules=[
            "React/frontend code still does not execute shell commands.",
            "Tauri may start only the app-owned frozen backend runtime selected by manifest.",
            "Startup success requires HTTP GET /health 200, not just an open TCP port.",
            "No pkill, killall, taskkill, or kill-by-port behavior is allowed.",
            "Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.",
        ],
        next_steps=[
            "Run the frozen backend build/check/smoke scripts locally on macOS.",
            "Run cargo check and npm run tauri dev from frontend after each desktop-shell change.",
            "Prepare packaged macOS app smoke using npm run tauri:build after the frozen runtime is validated.",
            "Then mirror the same startup/readiness/shutdown contract on Windows.",
        ],
    )


@router.get("/windows-packaging-foundation", response_model=WindowsPackagingFoundationResponse)
def get_windows_packaging_foundation() -> WindowsPackagingFoundationResponse:
    return WindowsPackagingFoundationResponse(
        status="foundation",
        title="Windows packaging foundation",
        summary="Defines the Windows equivalent of the desktop app packaging path: double-click app, app-owned localhost backend, readable logs, safe port handling, and no automatic risky actions on launch.",
        package_goal="Install or open AI Private Workspace on Windows, double-click it, and let the app start its own local backend before showing the UI.",
        shell_choice="Tauri-first Windows shell, sharing the same React UI and supervisor contract as macOS.",
        app_name="AI Private Workspace",
        app_data_directory=r"%LOCALAPPDATA%\AI Private Workspace",
        logs_directory=r"%LOCALAPPDATA%\AI Private Workspace\logs",
        backend_health_url="http://127.0.0.1:8000/health",
        packaging_strategy="Use Tauri Windows bundling as the primary path, with an app-owned backend runtime staged beside the shell before moving to installer-grade MSI/NSIS packaging.",
        supervisor_strategy="The Windows shell starts only the packaged app-owned backend, waits for /health, writes logs to LocalAppData, and stops only the PID it started.",
        installer_strategy="Start with a developer-verifiable package foundation, then move to signed MSI/NSIS artifacts after backend runtime bundling is stable.",
        scripts=[
            WindowsPackagingArtifactResponse(
                path="scripts/windows_supervisor_contract.ps1",
                purpose="PowerShell contract for Windows supervisor lifecycle, log paths, localhost backend, and safe port checks.",
                generated=False,
            ),
            WindowsPackagingArtifactResponse(
                path="scripts/package_windows_app_foundation.ps1",
                purpose="Developer packaging foundation script that validates frontend/Tauri/backend resources and creates a build manifest without bundling runtime data.",
                generated=False,
            ),
            WindowsPackagingArtifactResponse(
                path="scripts/prepare_windows_packaging_foundation.sh",
                purpose="Cross-platform validation helper for CI/sandbox checks. It validates the Windows scripts without executing PowerShell packaging.",
                generated=False,
            ),
        ],
        lifecycle_flow=[
            "User launches AI Private Workspace from Start Menu, Desktop shortcut, or installer-created app entry.",
            "Desktop shell prepares %LOCALAPPDATA% app data and logs directories.",
            "Supervisor checks whether the configured localhost port is free without killing unknown processes.",
            "Supervisor starts only the app-owned backend runtime and records its PID.",
            "Shell waits for /health before showing the main UI.",
            "If startup fails, the app shows a calm error and points to local logs.",
            "On exit, the app stops only the backend PID it owns.",
        ],
        implementation_phases=[
            WindowsPackagingPhaseResponse(
                id="foundation",
                title="Windows foundation",
                status="current",
                summary="Document and validate Windows lifecycle, data paths, logs, scripts, and safe startup rules.",
                deliverables=[
                    "Add PowerShell supervisor contract.",
                    "Add package foundation manifest script.",
                    "Expose read-only backend/UI packaging guidance.",
                ],
            ),
            WindowsPackagingPhaseResponse(
                id="tauri-bundle",
                title="Tauri Windows bundle",
                status="next",
                summary="Map Tauri shell startup to the Windows supervisor lifecycle after backend runtime bundling is reliable.",
                deliverables=[
                    "Package React static UI.",
                    "Stage backend runtime next to app resources.",
                    "Start backend through native shell lifecycle, not frontend code.",
                ],
            ),
            WindowsPackagingPhaseResponse(
                id="installer",
                title="Installer-grade artifact",
                status="later",
                summary="Produce signed/distributable Windows installer artifacts after the v0.1 runtime path is stable.",
                deliverables=[
                    "MSI or NSIS installer direction.",
                    "Start Menu/Desktop shortcuts.",
                    "Update-safe app data policy.",
                ],
            ),
        ],
        validation_steps=[
            "Run scripts/prepare_windows_packaging_foundation.sh from the project root.",
            "Confirm Windows scripts use %LOCALAPPDATA%/LocalAppData for logs and app data.",
            "Confirm scripts document safe port behavior and never kill unknown processes.",
            "Confirm package manifests exclude runtime DBs, build outputs, node_modules, caches, and app data.",
            "Confirm frontend still does not execute shell commands.",
        ],
        safety_rules=[
            "React/frontend never executes PowerShell, cmd.exe, or shell commands.",
            "Windows desktop shell may start only packaged app-owned backend processes.",
            "Never kill unknown processes that happen to use the expected port.",
            "Backend binds to 127.0.0.1 by default.",
            "No scan, index, rebuild, MCP server, agent workflow, or model download starts on app launch.",
            "Model downloads remain backend-side approved jobs with allowlisted models.",
            "Runtime data lives under LocalAppData and is not overwritten by app updates.",
        ],
        known_limitations=[
            "This is a Windows packaging foundation, not a signed installer yet.",
            "The backend runtime is not frozen into a Windows executable yet.",
            "Tauri Windows build requires developer toolchain setup outside this app.",
            "Installer signing, auto-update, and enterprise deployment are later release concerns.",
        ],
        next_steps=[
            "Add release candidate audit across macOS, Windows, model manager, MCP, and safety docs.",
            "Decide whether v0.1 ships as source-controlled foundation or a generated local package artifact.",
            "Freeze/stage backend runtime for macOS first, then mirror the approach on Windows.",
            "Create final v0.1 demo flow and handoff package.",
        ],
    )


@router.get("/backend-runtime-bundle-plan", response_model=BackendRuntimeBundlePlanResponse)
def get_backend_runtime_bundle_plan() -> BackendRuntimeBundlePlanResponse:
    return BackendRuntimeBundlePlanResponse(
        status="planned-foundation",
        title="Backend runtime bundle plan",
        summary="Defines how the macOS app should move from relying on the user's local python3 setup to an app-owned backend runtime with pinned dependencies and a repeatable manifest.",
        package_goal="Double click AI Private Workspace.app without asking the user to create a venv, install requirements, or understand backend scripts.",
        recommended_strategy="Bundle a pinned backend runtime first as a staged app resource, then replace it with a frozen executable when installer-grade packaging is introduced. Keep PyInstaller/Nuitka as packaging candidates, but do not lock them until dependency/runtime checks are repeatable.",
        build_script="scripts/prepare_macos_backend_runtime.sh",
        runtime_manifest_path="build/macos/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt",
        bundle_items=[
            BackendRuntimeBundleItemResponse(
                id="requirements",
                title="Pinned backend dependencies",
                status="source",
                summary="requirements.txt remains the source of truth for FastAPI, uvicorn, httpx, qdrant-client, and test/runtime dependencies.",
                path="backend/requirements.txt",
            ),
            BackendRuntimeBundleItemResponse(
                id="runtime-manifest",
                title="Runtime manifest",
                status="generated",
                summary="A build-time manifest records Python version, requirements hash, source paths, excludes, and the next freeze candidate.",
                path="build/macos/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt",
            ),
            BackendRuntimeBundleItemResponse(
                id="backend-source",
                title="Backend source bundle",
                status="staged",
                summary="Backend source is copied into the app bundle without runtime databases, caches, venvs, or generated state.",
                path="build/macos/AI Private Workspace.app/Contents/Resources/app/backend",
            ),
            BackendRuntimeBundleItemResponse(
                id="app-data",
                title="App-owned runtime data",
                status="external",
                summary="Workspace DB, logs, and runtime state stay outside the app bundle so updates cannot erase user data.",
                path="~/Library/Application Support/AI Private Workspace",
            ),
        ],
        build_steps=[
            BackendRuntimeBundleStepResponse(
                id="frontend-build",
                title="Build packaged UI assets",
                summary="Create frontend/dist before building the macOS app foundation.",
                command="cd frontend && npm ci && npm run build",
            ),
            BackendRuntimeBundleStepResponse(
                id="runtime-manifest",
                title="Generate backend runtime manifest",
                summary="Validate backend requirements and write a repeatable runtime manifest without copying runtime data.",
                command="scripts/prepare_macos_backend_runtime.sh",
            ),
            BackendRuntimeBundleStepResponse(
                id="app-foundation",
                title="Build macOS app foundation",
                summary="Stage frontend assets, backend source, launcher, and supervisor wiring into build/macos.",
                command="scripts/package_macos_app_foundation.sh",
            ),
            BackendRuntimeBundleStepResponse(
                id="open-app",
                title="Open generated app foundation",
                summary="Validate the double-click lifecycle after the manifest and app bundle are generated.",
                command="open \"build/macos/AI Private Workspace.app\"",
            ),
        ],
        validation_steps=[
            "Runtime manifest exists and contains a requirements hash.",
            "App bundle contains backend source but not backend/.ai-workbench, *.db, *.sqlite, .venv, __pycache__, or .pytest_cache.",
            "Launcher writes logs outside the app bundle under the app data directory.",
            "Opening the app waits for /health before showing UI.",
            "Packaging still works after deleting build/ and rebuilding from source.",
        ],
        safety_rules=[
            "Frontend never executes shell commands.",
            "Runtime preparation scripts are explicit developer/packager commands, not UI actions.",
            "No scan, index, rebuild, MCP, agent, or model download starts during runtime preparation or launch.",
            "Generated archives must not include build/, frontend/dist, node_modules, backend/.ai-workbench, databases, or virtual environments.",
            "The app should never overwrite user runtime data when the package is rebuilt or updated.",
        ],
        known_limitations=[
            "The current foundation still depends on local python3 and installed backend dependencies.",
            "This task does not create a signed .dmg or notarized app.",
            "This task does not yet freeze the backend into a standalone binary.",
            "Windows runtime packaging remains a separate packaging foundation task.",
        ],
        next_steps=[
            "Choose the backend freeze tool after the manifest is stable: PyInstaller, Nuitka, or a packaged Python runtime.",
            "Wire the runtime manifest into the macOS package script as a preflight requirement.",
            "Add Tauri shell scaffold and map supervisor states to native startup UI.",
            "Create Windows packaging foundation with equivalent runtime/data/log rules.",
        ],
    )


@router.get("/desktop-runtime-readiness", response_model=DesktopRuntimeReadinessResponse)
def get_desktop_runtime_readiness() -> DesktopRuntimeReadinessResponse:
    """Return the Phase 22 / v0.2 desktop runtime readiness plan."""
    return DesktopRuntimeReadinessResponse(
        status="phase-22-ready-to-start",
        title="v0.2 desktop runtime readiness",
        summary="v0.1 source RC is effectively complete. The next product stage should turn the current packaging foundation into a reliable desktop runtime path without weakening the existing safety rules.",
        current_phase="Phase 22 — v0.2 desktop runtime foundation",
        v01_position="v0.1 / Phase 21 is effectively complete after local UI smoke-check, source archive, git status cleanup, and first GitHub push.",
        v02_goal="Double-click desktop package starts an app-owned local backend, waits for /health, opens the UI, keeps logs/data outside the app bundle, and never starts scan/index/MCP/Agent/model downloads automatically.",
        readiness_items=[
            DesktopRuntimeReadinessItemResponse(
                id="runtime-manifest",
                title="Backend runtime manifest",
                status="foundation-ready",
                summary="The backend runtime bundle plan and manifest path are already documented.",
                evidence="GET /runtime/backend-runtime-bundle-plan and scripts/prepare_macos_backend_runtime.sh",
                next_action="Make the manifest a required preflight for macOS/Tauri packaging.",
            ),
            DesktopRuntimeReadinessItemResponse(
                id="tauri-shell",
                title="Tauri shell scaffold",
                status="foundation-ready",
                summary="The Tauri scaffold exists as the chosen desktop direction, but it is not yet the final process supervisor.",
                evidence="frontend/src-tauri plus GET /runtime/tauri-shell-scaffold",
                next_action="Implement native read-only supervisor status first, then app-owned backend process start after runtime staging is reliable.",
            ),
            DesktopRuntimeReadinessItemResponse(
                id="supervisor-contract",
                title="Supervisor safety contract",
                status="foundation-ready",
                summary="Startup states, safe port handling, app-owned logs, and no kill-by-port rules are already defined.",
                evidence="GET /runtime/desktop-supervisor-contract and GET /runtime/tauri-supervisor-bridge",
                next_action="Turn the contract into tests and Tauri-side startup state output.",
            ),
            DesktopRuntimeReadinessItemResponse(
                id="macos-package",
                title="macOS package foundation",
                status="partial",
                summary="A generated .app foundation exists, but it still is not a signed installer-grade DMG.",
                evidence="scripts/package_macos_app_foundation.sh and build/macos/AI Private Workspace.app after local build",
                next_action="Wire staged backend runtime into the package and verify double-click lifecycle on a clean local clone.",
            ),
            DesktopRuntimeReadinessItemResponse(
                id="windows-package",
                title="Windows packaging foundation",
                status="partial",
                summary="Windows data/log/supervisor rules exist, but installer output is future work.",
                evidence="GET /runtime/windows-packaging-foundation and scripts/package_windows_app_foundation.ps1",
                next_action="Keep Windows aligned after macOS/Tauri runtime startup is stable.",
            ),
            DesktopRuntimeReadinessItemResponse(
                id="persistent-jobs",
                title="Persistent background jobs",
                status="not-started",
                summary="Model download jobs have safe in-process history, but installer-grade restart persistence is not finished.",
                evidence="Model manager job history exists, but no durable desktop job supervisor is complete.",
                next_action="Design durable job state before enabling long-running desktop operations across restarts.",
            ),
        ],
        implementation_order=[
            "Keep v0.1 frozen except for blockers found during local UI smoke-check.",
            "Run the desktop runtime preflight before packaging changes.",
            "Make backend runtime manifest a required packaging preflight.",
            "Add Tauri read-only supervisor status/log path commands.",
            "Start app-owned backend from Tauri only after runtime staging is deterministic.",
            "Add desktop startup screen that waits for /health before showing full UI.",
            "Mirror the stabilized lifecycle on Windows packaging.",
            "Only then continue toward signed installers, persistent jobs, MCP runtime, and sandboxed Agent execution.",
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Source RC audit", command="./scripts/audit_release_candidate.sh", purpose="Keep source release hygiene green before starting v0.2 runtime work."),
            DesktopRuntimeValidationCommandResponse(label="Desktop runtime preflight", command="scripts/check_desktop_runtime_preflight.sh", purpose="Read-only Phase 22 gate before packaging/runtime changes."),
            DesktopRuntimeValidationCommandResponse(label="Backend runtime manifest", command="scripts/prepare_macos_backend_runtime.sh", purpose="Validate backend runtime staging inputs and generate the manifest."),
            DesktopRuntimeValidationCommandResponse(label="Tauri scaffold check", command="scripts/prepare_tauri_shell_scaffold.sh", purpose="Validate the Tauri scaffold without executing unsafe shell from the frontend."),
            DesktopRuntimeValidationCommandResponse(label="macOS package foundation", command="cd frontend && npm ci && npm run build && cd .. && scripts/package_macos_app_foundation.sh", purpose="Build the current developer-verifiable macOS app foundation."),
        ],
        blocked_until=[
            "v0.1 local UI smoke-check is passed or any blocker is fixed.",
            "Source archive excludes runtime/build/cache/database artifacts.",
            "Tauri supervisor status is read-only before process start behavior is added.",
            "Backend runtime staging is deterministic enough to test from a clean checkout.",
        ],
        safety_rules=[
            "Frontend React code must never execute shell commands",
            "Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "Tauri may start only app-owned local backend runtime after explicit packaging implementation.",
            "Never kill unknown processes using the expected localhost port.",
            "Logs and workspace data stay outside app bundles and source archives.",
            "MCP/Agent execution remains disabled until sandbox, allowlist, approvals, and audit logs exist.",
        ],
        honest_remaining_work="v0.2 desktop runtime is roughly 5-8 large tasks. Full v1.0 remains roughly 15-25 large tasks including signed installers, persistent jobs, MCP runtime, sandboxed Agent execution, update flow, and final QA.",
    )


@router.get("/desktop-runtime-preflight", response_model=DesktopRuntimePreflightResponse)
def get_desktop_runtime_preflight() -> DesktopRuntimePreflightResponse:
    """Return the read-only desktop runtime preflight for Phase 22 packaging work."""
    root = Path(__file__).resolve().parents[4]
    manifest = root / "build" / "macos" / "backend-runtime" / "AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt"
    package_script = root / "scripts" / "package_macos_app_foundation.sh"
    preflight_script = root / "scripts" / "check_desktop_runtime_preflight.sh"
    frontend_dist = root / "frontend" / "dist" / "index.html"
    backend_app = root / "backend" / "app" / "main.py"
    tauri_main = root / "frontend" / "src-tauri" / "src" / "main.rs"

    items = [
        DesktopRuntimePreflightItemResponse(
            id="backend-source",
            title="Backend source entrypoint",
            status="ok" if backend_app.exists() else "blocked",
            summary="backend/app/main.py is present" if backend_app.exists() else "backend/app/main.py is missing",
            evidence="backend/app/main.py",
            fix_command=None,
        ),
        DesktopRuntimePreflightItemResponse(
            id="runtime-manifest",
            title="Backend runtime manifest",
            status="ok" if manifest.exists() else "review",
            summary="Runtime manifest exists" if manifest.exists() else "Runtime manifest has not been generated in this checkout",
            evidence="build/macos/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt",
            fix_command="scripts/prepare_macos_backend_runtime.sh" if not manifest.exists() else None,
        ),
        DesktopRuntimePreflightItemResponse(
            id="frontend-dist",
            title="Packaged frontend assets",
            status="ok" if frontend_dist.exists() else "review",
            summary="frontend/dist/index.html exists" if frontend_dist.exists() else "frontend/dist is not built in the source checkout",
            evidence="frontend/dist/index.html",
            fix_command="cd frontend && npm ci && npm run build" if not frontend_dist.exists() else None,
        ),
        DesktopRuntimePreflightItemResponse(
            id="package-script",
            title="macOS package foundation script",
            status="ok" if package_script.exists() else "blocked",
            summary="Package script exists" if package_script.exists() else "Package script is missing",
            evidence="scripts/package_macos_app_foundation.sh",
            fix_command=None,
        ),
        DesktopRuntimePreflightItemResponse(
            id="tauri-shell",
            title="Tauri shell scaffold",
            status="ok" if tauri_main.exists() else "review",
            summary="Tauri shell source exists" if tauri_main.exists() else "Tauri shell scaffold is not present",
            evidence="frontend/src-tauri/src/main.rs",
            fix_command="scripts/prepare_tauri_shell_scaffold.sh" if not tauri_main.exists() else None,
        ),
    ]
    if any(item.status == "blocked" for item in items):
        status = "blocked"
    elif any(item.status == "review" for item in items):
        status = "review"
    else:
        status = "ok"

    return DesktopRuntimePreflightResponse(
        status=status,
        title="Desktop runtime preflight",
        summary="Read-only Phase 22 checkpoint before turning the packaging foundation into a real app-owned desktop runtime.",
        preflight_script="scripts/check_desktop_runtime_preflight.sh",
        runtime_manifest_path="build/macos/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt",
        package_script="scripts/package_macos_app_foundation.sh",
        items=items,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Read-only preflight", command="scripts/check_desktop_runtime_preflight.sh", purpose="Checks source, manifest, build outputs, package script, and Tauri scaffold without starting services."),
            DesktopRuntimeValidationCommandResponse(label="Generate runtime manifest", command="scripts/prepare_macos_backend_runtime.sh", purpose="Creates the manifest used by packaging preflight; it does not start backend or models."),
            DesktopRuntimeValidationCommandResponse(label="Build frontend assets", command="cd frontend && npm ci && npm run build", purpose="Creates frontend/dist for package foundation validation."),
            DesktopRuntimeValidationCommandResponse(label="Build macOS app foundation", command="scripts/package_macos_app_foundation.sh", purpose="Stages the current foundation .app after manifest and frontend assets are ready."),
        ],
        pass_criteria=[
            "backend/app/main.py exists and imports in backend tests.",
            "Runtime manifest is generated before packaging.",
            "frontend/dist exists before packaging the .app foundation.",
            "Package script refuses missing inputs instead of silently creating a broken app.",
            "Tauri scaffold remains present and does not grant shell execution to React frontend code.",
        ],
        fail_fast_conditions=[
            "Missing backend/app/main.py.",
            "Missing scripts/package_macos_app_foundation.sh.",
            "Any release audit blocker for database/runtime/build artifacts outside ignored paths.",
            "Any packaging step that starts scan, index, rebuild, MCP, Agent, or model downloads automatically.",
        ],
        safety_rules=[
            "This endpoint is read-only and never executes the preflight commands.",
            "Frontend can display and copy commands only; it cannot run shell commands.",
            "Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "Runtime data and logs stay outside the app bundle and source release archive.",
            "Unknown processes on localhost ports must never be killed automatically.",
        ],
        next_steps=[
            "Use this preflight as the first Phase 22 gate before every desktop runtime change.",
            "Next task can add Tauri-side read-only supervisor status/log path commands.",
            "Only after that should app-owned backend process start move into Tauri.",
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



@router.get("/release-candidate-audit", response_model=ReleaseCandidateAuditResponse)
def get_release_candidate_audit() -> ReleaseCandidateAuditResponse:
    settings = get_settings()
    project_root = Path(__file__).resolve().parents[4]
    required_paths = ["backend", "frontend", "docs", "scripts", "pytest.ini", ".gitignore", "README.md", ".github"]
    required_docs = [
        "docs/START_HERE.md",
        "docs/ROADMAP.md",
        "docs/API_INVENTORY.md",
        "docs/PROJECT_CHECKPOINT.md",
        "docs/DESKTOP_PACKAGING_DESIGN_LOCK.md",
        "docs/WINDOWS_PACKAGING_FOUNDATION.md",
        "docs/RELEASE_CANDIDATE_AUDIT.md",
    ]
    forbidden_paths = [
        "backend/.ai-workbench",
        "frontend/node_modules",
        "frontend/dist",
        "build",
        ".pytest_cache",
    ]

    passed: list[ReleaseCandidateAuditItemResponse] = []
    review: list[ReleaseCandidateAuditItemResponse] = []
    blocked: list[ReleaseCandidateAuditItemResponse] = []

    def add_item(target: list[ReleaseCandidateAuditItemResponse], id: str, title: str, summary: str, detail: str, action: str | None = None) -> None:
        target.append(ReleaseCandidateAuditItemResponse(id=id, title=title, status="blocked" if target is blocked else "review" if target is review else "ok", summary=summary, detail=detail, recommended_action=action))

    missing_required = [path for path in required_paths if not (project_root / path).exists()]
    if missing_required:
        add_item(blocked, "required-root-structure", "Root structure", "Required release paths are missing.", ", ".join(missing_required), "Restore the root-preserving project structure before packaging.")
    else:
        add_item(passed, "required-root-structure", "Root structure", "Required release paths are present.", "backend/, frontend/, docs/, scripts/, README.md, .github/, pytest.ini, and .gitignore are available.")

    missing_docs = [path for path in required_docs if not (project_root / path).exists()]
    if missing_docs:
        add_item(review, "release-docs", "Release docs", "Some release/operator docs are missing.", ", ".join(missing_docs), "Add or restore missing docs before final handoff.")
    else:
        add_item(passed, "release-docs", "Release docs", "Release and packaging docs are present.", "The handoff has start, roadmap, API, checkpoint, packaging, and audit docs.")

    local_artifacts = [path for path in forbidden_paths if (project_root / path).exists()]
    if local_artifacts:
        add_item(review, "local-artifacts", "Local build/runtime artifacts", "Local artifacts exist in the working tree.", ", ".join(local_artifacts), "They may exist locally, but must be excluded from generated release zip.")
    else:
        add_item(passed, "local-artifacts", "Local build/runtime artifacts", "No common runtime/build artifact directories found.", "Source tree looks clean for zip generation.")

    db_files = [str(path.relative_to(project_root)) for path in project_root.rglob("*") if path.is_file() and path.suffix in {".db", ".sqlite", ".sqlite3"} and ".git" not in path.parts]
    if db_files:
        add_item(blocked, "database-files", "Runtime database files", "Database files were found in the source tree.", ", ".join(db_files[:10]), "Remove DB files from the source archive and keep runtime data under app data paths.")
    else:
        add_item(passed, "database-files", "Runtime database files", "No *.db, *.sqlite, or *.sqlite3 files found in source tree.", "Runtime data is not present in the release source tree.")

    safety_docs = ["docs/MODEL_DOWNLOAD_JOBS.md", "docs/MCP_SETUP_UX_TASK212.md", "docs/AGENT_MCP_READINESS_TASK213.md"]
    missing_safety = [path for path in safety_docs if not (project_root / path).exists()]
    if missing_safety:
        add_item(review, "safety-docs", "Model/MCP/Agent safety docs", "Some safety docs are missing.", ", ".join(missing_safety), "Restore safety docs before final release notes.")
    else:
        add_item(passed, "safety-docs", "Model/MCP/Agent safety docs", "Safety docs are present.", "Model downloads, MCP setup, and Agent workflow boundaries are documented.")

    if settings.model_download_execution_enabled:
        add_item(review, "model-execution-enabled", "Model download execution", "Model download execution is enabled in this runtime.", "This is allowed only for trusted local runtime, not default release demos.", "Use MODEL_DOWNLOAD_EXECUTION_ENABLED=false for default safe demos.")
    else:
        add_item(passed, "model-execution-disabled", "Model download execution", "Model download execution is disabled by default.", "Downloads require explicit opt-in and backend allowlist execution.")

    ok_count = len(passed)
    total = len(passed) + len(review) + len(blocked)
    status = "blocked" if blocked else "review" if review else "ready"
    score = round((ok_count / total) * 100) if total else 0

    return ReleaseCandidateAuditResponse(
        status=status,
        title="Release candidate audit",
        summary="Final read-only audit for v0.1 source handoff, safety boundaries, packaging readiness, and no-runtime-data policy.",
        release_label="v0.1 release candidate",
        readiness_score=score,
        audit_script="scripts/audit_release_candidate.sh",
        source_archive_policy=[
            "Keep root-preserving structure: backend/, frontend/, docs/, scripts/, pytest.ini, .gitignore.",
            "Exclude backend/.ai-workbench, *.db, *.sqlite, *.sqlite3, node_modules, dist, build, caches, and __pycache__.",
            "Generated .app/.exe/.msi artifacts are build outputs, not source archive contents.",
        ],
        blocked_items=blocked,
        review_items=review,
        passed_items=passed,
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Run release audit", command="./scripts/audit_release_candidate.sh", purpose="Checks source structure, docs, runtime-data exclusions, and script syntax."),
            DesktopRuntimeValidationCommandResponse(label="Frontend build", command="cd frontend && npm ci && npm run build", purpose="Validates React/TypeScript production build."),
            DesktopRuntimeValidationCommandResponse(label="Backend targeted tests", command="cd backend && pytest -q tests/test_api_inventory.py tests/test_windows_packaging_foundation.py tests/test_tauri_supervisor_bridge.py", purpose="Runs packaging/API safety coverage without requiring the full long test suite."),
        ],
        final_handoff_steps=[
            "Run the audit script and targeted tests.",
            "Open Overview, Ask, Models, Agent, MCP, and Settings once in light and dark mode.",
            "Create a clean root-preserving zip that excludes runtime/build data.",
            "Prepare final demo flow: create/select workspace -> scan -> index -> ask -> report -> model manager -> safe agent plan.",
        ],
        safety_rules=[
            "Frontend never executes shell commands.",
            "App launch never starts scan, index, rebuild, MCP, agent execution, or model downloads.",
            "Model downloads remain backend-side approved jobs with allowlisted models only.",
            "MCP and Agent execution stay disabled until sandbox/allowlist execution exists.",
            "Desktop shell may start only app-owned local backend processes and must not kill unknown processes by port.",
        ],
        known_limitations=[
            "Tauri shell is scaffolded but not a final signed installer.",
            "Backend runtime freezing/bundling is planned but not final.",
            "Windows packaging foundation is documented and scaffolded, not final MSI/NSIS distribution.",
        ],
    )


@router.get("/v0.1-handoff", response_model=V01HandoffResponse)
def get_v01_handoff() -> V01HandoffResponse:
    return V01HandoffResponse(
        status="release-candidate",
        title="AI Private Workspace v0.1 handoff",
        release_label="v0.1 local-first release candidate",
        summary="Final demo and GitHub handoff guide for the local-first AI Private Workspace MVP.",
        github_ready=True,
        demo_story="A private desktop-like AI workspace that helps a user onboard to a local project: create workspace, scan files, build local context, ask questions, generate reports, manage local models, and prepare safe agent plans without uploading project data.",
        demo_steps=[
            V01DemoStepResponse(id="open", title="Open the app", summary="Start the local workspace with the current launcher or packaged app foundation.", expected_result="Backend health is ready and the UI opens without starting scans or model downloads.", ui_location="Desktop app / browser"),
            V01DemoStepResponse(id="workspace", title="Create or select workspace", summary="Choose a local project folder and assistant mode.", expected_result="Workspace dashboard shows the next safe action.", ui_location="Overview"),
            V01DemoStepResponse(id="scan", title="Scan project", summary="Run explicit user-click scan to detect files and skills.", expected_result="Detected technologies and project summary appear.", ui_location="Overview"),
            V01DemoStepResponse(id="index", title="Build search context", summary="Index selected files only after explicit action.", expected_result="Ask can use retrieved local context instead of guessing from skills alone.", ui_location="Overview / Ask"),
            V01DemoStepResponse(id="ask", title="Ask about the project", summary="Ask a practical onboarding question about the local codebase.", expected_result="Answer includes local context and does not claim facts without retrieved sources.", ui_location="Ask"),
            V01DemoStepResponse(id="report", title="Generate report", summary="Create a project overview or documentation report.", expected_result="Report is saved locally and can be reviewed later.", ui_location="Reports"),
            V01DemoStepResponse(id="models", title="Check local models", summary="Verify installed Ollama models and use safe download jobs only if explicitly enabled.", expected_result="User understands LLM vs embedding model and installed/missing status.", ui_location="Models"),
            V01DemoStepResponse(id="agent", title="Create safe agent plan", summary="Draft an Agent/MCP workflow plan without automatic execution.", expected_result="The plan maps possible tools and approvals, but execution remains manual/sandbox future.", ui_location="Agent / MCP"),
        ],
        repository_highlights=[
            "Local-first architecture with backend clean architecture and frontend-only API calls.",
            "Root-preserving repository layout ready for GitHub: backend/, frontend/, docs/, scripts/.",
            "Safety-first model manager with backend-owned jobs, allowlist, history, and cancel-safe semantics.",
            "Desktop packaging foundation for macOS and Windows with Tauri-first direction.",
            "Calm Apple-style UX direction with beginner-friendly flows and advanced details behind disclosure sections.",
        ],
        important_files=[
            V01RepositoryFileResponse(path="README.md", purpose="GitHub landing page and quick start."),
            V01RepositoryFileResponse(path="docs/START_HERE.md", purpose="First entry point for running and understanding the project."),
            V01RepositoryFileResponse(path="docs/V01_DEMO_HANDOFF.md", purpose="Final demo scenario and handoff guide."),
            V01RepositoryFileResponse(path="docs/V01_RELEASE_NOTES.md", purpose="Release notes for the v0.1 candidate."),
            V01RepositoryFileResponse(path="docs/ROADMAP.md", purpose="Current roadmap and remaining packaging work."),
            V01RepositoryFileResponse(path="docs/RELEASE_CANDIDATE_AUDIT.md", purpose="Release audit and archive policy."),
            V01RepositoryFileResponse(path="scripts/audit_release_candidate.sh", purpose="Local source tree release audit."),
        ],
        validation_commands=[
            DesktopRuntimeValidationCommandResponse(label="Release audit", command="./scripts/audit_release_candidate.sh", purpose="Checks source layout, docs, safety boundaries, and no-runtime-data policy."),
            DesktopRuntimeValidationCommandResponse(label="Backend targeted tests", command="cd backend && pytest -q tests/test_v01_handoff.py tests/test_release_candidate_audit.py tests/test_api_inventory.py", purpose="Validates v0.1 handoff and release audit API coverage."),
            DesktopRuntimeValidationCommandResponse(label="Frontend production build", command="cd frontend && npm ci && npm run build", purpose="Validates UI build before GitHub/release handoff."),
        ],
        release_notes=[
            "v0.1 is a local-first MVP release candidate, not a signed commercial installer yet.",
            "Core workspace flow is available: onboarding, scan, indexing, Ask, reports, conversations, model manager, Agent/MCP planning.",
            "macOS and Windows packaging foundations are present; final signed installers remain future work.",
            "All risky actions remain explicit and backend-owned where execution exists.",
        ],
        known_limitations=[
            "Tauri shell is scaffolded but backend process startup from Tauri is not final production code.",
            "Backend runtime freezing/bundling is planned but not final.",
            "MCP/Agent execution remains planning/manual tracking only.",
            "The current release archive is source handoff, not a notarized macOS app or Windows MSI.",
        ],
        next_after_v01=[
            "Finalize Tauri backend supervisor execution with app-owned packaged backend runtime.",
            "Produce signed macOS app package and then Windows installer.",
            "Add sandboxed Agent/MCP execution only after strict allowlist and audit logging are ready.",
            "Continue final UI QA with screenshots from real light/dark runs.",
        ],
        safety_rules=[
            "Frontend never executes shell commands.",
            "App startup never triggers scan, index, rebuild, MCP, agent execution, or model downloads.",
            "Model download execution is disabled by default and requires backend opt-in plus allowlist validation.",
            "Agent and MCP are planning/readiness workflows until sandboxed execution exists.",
            "Runtime data and build artifacts are excluded from source release archives.",
        ],
    )


@router.get("/product-completion-roadmap", response_model=ProductCompletionRoadmapResponse)
def get_product_completion_roadmap() -> ProductCompletionRoadmapResponse:
    """Return an honest product-completion map without implying v0.1 is v1.0."""
    return ProductCompletionRoadmapResponse(
        status="v0.1-source-rc",
        title="Product completion roadmap",
        summary="AI Private Workspace is a GitHub-ready v0.1 source release candidate. A fully packaged v1.0 desktop product still needs runtime bundling, installers, persistent jobs, and sandboxed Agent/MCP execution.",
        current_stage="v0.1 source release candidate",
        honest_completion_estimate="Roughly 15-25 large tasks remain for a polished v1.0 product, depending on installer quality and Agent/MCP execution depth.",
        stages=[
            ProductCompletionStageResponse(id="source-rc", title="v0.1 source release candidate", status="current", summary="Source repo, local demo, safety, docs, model manager foundation, desktop packaging foundation, and GitHub readiness.", remaining_large_tasks=2),
            ProductCompletionStageResponse(id="desktop-runtime", title="v0.2 desktop runtime", status="next", summary="Frozen backend runtime, stronger supervisor lifecycle, app-owned logs/data, and persistent local jobs.", remaining_large_tasks=5),
            ProductCompletionStageResponse(id="installers", title="v0.3 installers", status="planned", summary="macOS signed package, Windows installer, icons, shortcuts, uninstall/update behavior, and packaging QA.", remaining_large_tasks=7),
            ProductCompletionStageResponse(id="agent-mcp-readonly", title="v0.4 read-only Agent/MCP execution", status="planned", summary="Sandboxed read-only tool execution with allowlists, approvals, evidence, and audit logs.", remaining_large_tasks=7),
            ProductCompletionStageResponse(id="v1", title="v1.0 polished product", status="target", summary="Installer-grade desktop product with stable local runtime, polished onboarding, safe execution model, and user-facing troubleshooting.", remaining_large_tasks=4),
        ],
        next_recommended_tasks=[
            "Task 235 — final v0.1 release gate and roadmap lock.",
            "Task 236 — local UI smoke-check results and first GitHub publication cleanup, if needed.",
            "Task 237 — v0.2 planning kickoff: frozen backend runtime and Tauri supervisor implementation.",
        ],
        not_done_yet=[
            "Final frozen backend binary/runtime bundle.",
            "Signed/notarized macOS DMG and Windows installer.",
            "Persistent background jobs that survive app restart.",
            "MCP server install/run lifecycle.",
            "Sandboxed Agent/MCP read-only execution.",
            "Controlled write execution with rollback/verification design.",
        ],
        safety_rules=[
            "Do not call the source release candidate a finished v1.0 product.",
            "Keep frontend shell execution forbidden.",
            "Keep model downloads backend-owned, opt-in, and allowlisted.",
            "Keep MCP and Agent execution disabled until sandbox/allowlist/audit logs are implemented.",
            "Do not include runtime databases or build artifacts in GitHub or source release archives.",
        ],
    )



@router.get("/v0.1-ui-smoke-check", response_model=V01UISmokeCheckResponse)
def get_v01_ui_smoke_check() -> V01UISmokeCheckResponse:
    """Return the manual local UI smoke-check for the final v0.1 source RC."""
    return V01UISmokeCheckResponse(
        status="manual-check-required",
        title="v0.1 local UI smoke-check",
        summary="A short manual checklist for validating the source RC in a real browser before GitHub publication. It is intentionally read-only: it tells the user what to open and what must not start automatically.",
        estimated_duration="10-15 minutes",
        checklist=[
            V01UISmokeCheckItemResponse(
                id="startup",
                title="Start backend and frontend manually",
                status="required",
                summary="Open the local app only after the backend /health endpoint is ready.",
                expected_result="The UI loads without a blank page, React crash boundary, or console-visible startup error.",
                ui_location="App shell",
                must_not_happen=["No scan starts", "No indexing job starts", "No model download starts", "No MCP/Agent execution starts"],
            ),
            V01UISmokeCheckItemResponse(
                id="models",
                title="Models page renders",
                status="required",
                summary="Open Models and verify selected LLM/embedding status, recommendations, installed model check, and Build context guidance.",
                expected_result="Models explains the difference between selected embedding model and indexed context without requiring a download on load.",
                ui_location="Models",
                must_not_happen=["No ollama pull is triggered by opening the page", "No shell command is executed by the frontend"],
            ),
            V01UISmokeCheckItemResponse(
                id="onboarding",
                title="Create or open a workspace",
                status="required",
                summary="Use the explicit workspace flow and verify that assistant mode/privacy mode are visible before any scan/index action.",
                expected_result="Workspace creation succeeds or existing workspace opens; scan/index actions remain explicit buttons.",
                ui_location="Overview / Create workspace",
                must_not_happen=["No automatic filesystem scan on app load", "No automatic context rebuild"],
            ),
            V01UISmokeCheckItemResponse(
                id="ask",
                title="Ask flow keeps source-grounding language",
                status="recommended",
                summary="Ask a small question after context is available, or verify the empty-context explanation if it is not indexed yet.",
                expected_result="The answer is source-aware, or the UI clearly says context must be built first.",
                ui_location="Ask",
                must_not_happen=["No unsupported project claims without retrieved sources"],
            ),
            V01UISmokeCheckItemResponse(
                id="settings",
                title="Settings release sections are readable",
                status="required",
                summary="Open Settings and verify final product status, release gate, release audit, local data safety, and packaging sections.",
                expected_result="The page clearly separates v0.1 source RC from future v1.0 installer-grade work.",
                ui_location="Settings",
                must_not_happen=["No unsafe apply/update action runs from the page"],
            ),
        ],
        copy_commands=[
            ReleaseCandidateAuditCommandResponse(
                label="Backend",
                command="cd backend && uvicorn app.main:app --reload",
                purpose="Start the local API for UI smoke-checking.",
            ),
            ReleaseCandidateAuditCommandResponse(
                label="Frontend",
                command="cd frontend && npm ci && npm run dev",
                purpose="Start the Vite UI for manual browser verification.",
            ),
            ReleaseCandidateAuditCommandResponse(
                label="Release gate",
                command="./scripts/audit_release_candidate.sh && cd backend && pytest -q tests/test_v01_release_gate.py tests/test_v01_ui_smoke_check.py tests/test_final_product_status.py tests/test_api_inventory.py && cd ../frontend && npm run build",
                purpose="Run the targeted checks that support the final UI smoke-check handoff.",
            ),
        ],
        pass_criteria=[
            "UI opens without a blank Models page or React hook-order crash.",
            "Models, onboarding, Ask, and Settings are understandable without reading developer docs first.",
            "No scan, index, rebuild, MCP, Agent, or model download starts automatically on app launch.",
            "Release/status wording still says v0.1 source RC, not finished v1.0 product.",
        ],
        fail_fast_conditions=[
            "Models or Settings render a blank page.",
            "Opening the app starts filesystem scan/index/model download without a user click.",
            "Frontend executes or attempts to execute shell commands.",
            "Generated source archive includes runtime/build data or local databases.",
        ],
        safety_note="This endpoint is documentation for a human smoke-check only. It does not inspect browser state, start servers, run tests, scan files, index context, download models, or execute shell commands.",
    )


@router.get("/v0.1-release-gate", response_model=V01ReleaseGateResponse)
def get_v01_release_gate() -> V01ReleaseGateResponse:
    """Return the final go/no-go checklist before publishing the v0.1 source RC."""
    return V01ReleaseGateResponse(
        status="v0.1-source-rc-release-gate",
        title="v0.1 release gate",
        summary="Use this as the final local go/no-go checklist before creating the source archive or pushing AI Private Workspace v0.1 to GitHub.",
        current_position="Phase 21 is effectively complete as a source release candidate. The remaining v0.1 work is local verification and publication hygiene, not new product capability.",
        source_rc_remaining_tasks="0-1 large task: local UI smoke-check, clean git status, audit/build/test pass, and source archive or first GitHub push.",
        v1_remaining_large_tasks="Roughly 15-25 large tasks remain for a true v1.0 installer-grade product: frozen runtime, signed installers, persistent jobs, MCP runtime, sandboxed Agent execution, update flow, and final QA.",
        release_gate_items=[
            V01ReleaseGateItemResponse(id="audit", title="Release audit", status="required", summary="Must pass with no real blockers before source publication.", command="./scripts/audit_release_candidate.sh"),
            V01ReleaseGateItemResponse(id="backend-tests", title="Backend targeted tests", status="required", summary="Validates release audit, API inventory, final status, and source archive behavior.", command="cd backend && pytest -q tests/test_release_candidate_audit_script.py tests/test_source_release_archive_script.py tests/test_release_candidate_audit.py tests/test_api_inventory.py tests/test_final_product_status.py tests/test_product_completion_roadmap.py tests/test_v01_release_gate.py"),
            V01ReleaseGateItemResponse(id="frontend-build", title="Frontend production build", status="required", summary="Confirms the UI compiles before GitHub/source archive publication.", command="cd frontend && npm ci && npm run build"),
            V01ReleaseGateItemResponse(id="ui-smoke", title="Local UI smoke-check", status="recommended", summary="Open the app locally and verify Models, Settings, onboarding, workspace creation, and no automatic scan/index/model download on startup."),
            V01ReleaseGateItemResponse(id="git-status", title="Git status cleanup", status="required", summary="Only intentional source/docs/config changes should be staged; runtime/build/cache data must remain untracked or ignored.", command="git status --short"),
            V01ReleaseGateItemResponse(id="source-archive", title="Clean source archive", status="required-for-zip-release", summary="Creates a root-preserving source archive without runtime/build artifacts.", command="./scripts/prepare_source_release_archive.sh"),
        ],
        go_no_go_rule="Go only when audit, backend targeted tests, frontend build, and git status are clean; treat UI smoke-check as the final human confidence check before publishing.",
        next_actions=[
            "Run the release gate commands locally on the latest clean source tree.",
            "Fix only real blockers; avoid adding new features to v0.1 unless they are release blockers.",
            "Create the source archive or push the clean repository to GitHub.",
            "After v0.1 is published, start Phase 22/v0.2 with frozen backend runtime and Tauri supervisor work.",
        ],
        safety_rules=[
            "Do not include backend/.ai-workbench, virtualenvs, node_modules, dist/build outputs, caches, or SQLite/database files in the release.",
            "Desktop startup must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "Frontend must not execute shell commands.",
            "MCP/Agent execution remains disabled until sandbox, approvals, allowlists, and audit logs are implemented.",
        ],
    )



@router.get("/v0.1-publication-handoff", response_model=V01PublicationHandoffResponse)
def get_v01_publication_handoff() -> V01PublicationHandoffResponse:
    """Return the final publish handoff after the local v0.1 smoke-check passes."""
    return V01PublicationHandoffResponse(
        status="ready-after-local-smoke-check",
        title="v0.1 publication handoff",
        summary="A final, copyable source-release path for publishing AI Private Workspace v0.1 after manual UI smoke-check passes.",
        current_position="Phase 21 is effectively complete. Do not add new v0.1 features unless a release blocker appears.",
        publish_verdict="Go for GitHub/source release after audit, backend targeted tests, frontend build, UI smoke-check, and git status are clean.",
        v01_remaining_work="0-1 large task: only local smoke-check and publication cleanup remain.",
        v1_remaining_work="15-25 large tasks remain for installer-grade v1.0.",
        steps=[
            V01PublicationHandoffStepResponse(
                id="audit",
                title="Run release audit",
                status="required",
                summary="Verify source layout, required docs, scripts, GitHub files, and no runtime database leakage.",
                command="./scripts/audit_release_candidate.sh",
                expected_result="Audit passes. Local cache/build warnings are acceptable only if they are excluded from commit/archive.",
            ),
            V01PublicationHandoffStepResponse(
                id="backend-tests",
                title="Run backend release tests",
                status="required",
                summary="Validate release endpoints, API inventory, audit rules, and source archive hygiene.",
                command="cd backend && python -m pytest -q tests/test_v01_publication_handoff.py tests/test_v01_ui_smoke_check.py tests/test_v01_release_gate.py tests/test_final_product_status.py tests/test_api_inventory.py tests/test_release_candidate_audit.py tests/test_release_candidate_audit_script.py tests/test_source_release_archive_script.py",
                expected_result="All selected tests pass.",
            ),
            V01PublicationHandoffStepResponse(
                id="frontend-build",
                title="Build frontend",
                status="required",
                summary="Validate that Settings, Models, and release status UI compile into a production bundle.",
                command="cd frontend && npm ci && npm run build",
                expected_result="Vite build completes without TypeScript or bundling errors.",
            ),
            V01PublicationHandoffStepResponse(
                id="ui-smoke",
                title="Manual browser smoke-check",
                status="required",
                summary="Start backend and frontend manually, then check Models, Settings, onboarding, Ask, and startup safety.",
                command="cd backend && uvicorn app.main:app --reload  # second terminal: cd frontend && npm run dev",
                expected_result="UI loads; no blank Models page; no automatic scan/index/rebuild/MCP/Agent/model download starts.",
            ),
            V01PublicationHandoffStepResponse(
                id="source-archive",
                title="Create clean source archive",
                status="required",
                summary="Create the root-preserving source archive using the audited release script.",
                command="./scripts/prepare_source_release_archive.sh",
                expected_result="build/release/ai-private-workspace-v0.1-source.zip exists and does not include runtime/build artifacts.",
            ),
            V01PublicationHandoffStepResponse(
                id="git-status",
                title="Review git status",
                status="required",
                summary="Confirm only intended source/docs/config changes are staged before commit and push.",
                command="git status --short",
                expected_result="Only intended files are listed. No build/release, node_modules, dist, .venv, .pytest_cache, database, or tsbuildinfo files are staged.",
            ),
        ],
        source_archive_name="build/release/ai-private-workspace-v0.1-source.zip",
        git_commit_message="Prepare v0.1 source release",
        github_push_commands=[
            ReleaseCandidateAuditCommandResponse(label="Stage intended files", command="git add README.md CONTRIBUTING.md SECURITY.md .editorconfig .gitattributes .github backend frontend docs scripts pytest.ini .gitignore", purpose="Stage source, docs, scripts, UI, backend, and GitHub repository files only."),
            ReleaseCandidateAuditCommandResponse(label="Review staged diff", command="git diff --cached --stat && git diff --cached --check", purpose="Catch whitespace/errors and confirm the staged change set is reasonable."),
            ReleaseCandidateAuditCommandResponse(label="Commit", command="git commit -m \"Prepare v0.1 source release\"", purpose="Create the v0.1 source release commit."),
            ReleaseCandidateAuditCommandResponse(label="Push", command="git push origin main", purpose="Push after confirming the target branch name for the new GitHub repository."),
        ],
        do_not_commit=[
            "backend/.ai-workbench/",
            "backend/.venv/",
            "frontend/node_modules/",
            "frontend/dist/",
            "frontend/.vite/",
            "build/",
            ".pytest_cache/",
            "__pycache__/",
            "*.db, *.sqlite, *.sqlite3",
            "*.tsbuildinfo",
        ],
        after_publish=[
            "Create the GitHub repository description and topics.",
            "Attach or keep the source archive under build/release locally; do not commit it unless a release artifact workflow is chosen.",
            "Open the README on GitHub and verify links/rendering.",
            "Start Phase 22/v0.2 work: frozen backend runtime and real Tauri supervisor lifecycle.",
        ],
        safety_rules=[
            "Frontend must never execute shell commands.",
            "Desktop launch must not auto-start scan, index, rebuild, MCP, Agent, or model downloads.",
            "Model download execution stays backend-owned, opt-in, allowlisted, and disabled by default.",
            "MCP/Agent execution remains planning/manual tracking until sandbox, allowlists, approvals, and audit logs exist.",
            "Do not call v0.1 a finished installer-grade v1.0 product.",
        ],
    )

@router.get("/final-product-status", response_model=FinalProductStatusResponse)
def get_final_product_status() -> FinalProductStatusResponse:
    """Return a clear source-RC versus v1 product status for the final handoff."""
    return FinalProductStatusResponse(
        status="v0.1-source-rc-ready",
        title="Final product status",
        summary="AI Private Workspace is ready as a polished v0.1 source release candidate for GitHub publication and local demos. It is not yet a signed, installer-grade v1.0 desktop product.",
        current_milestone="v0.1 source release candidate",
        current_stage_completion="About 95% of the source-RC stage is complete; remaining work is local verification, screenshots, and first GitHub push hygiene.",
        honest_v1_estimate="A polished v1.0 product still needs roughly 15-25 large tasks: packaged runtime, signed installers, persistent jobs, MCP runtime, sandboxed Agent execution, update flow, and final QA.",
        source_rc_verdict="Ready to publish after local audit/build/test pass and after runtime/build artifacts are excluded.",
        remaining_current_stage_tasks=[
            "Run the release audit and fix any real source-tree failures.",
            "Run targeted backend tests and frontend build on the local machine.",
            "Create the clean source archive or push the clean repository to GitHub.",
            "Optionally capture final screenshots for README/docs after real UI review.",
        ],
        stages=[
            FinalProductStageResponse(id="source-rc", title="v0.1 source RC", status="current", summary="GitHub-ready source repository, local demo, safety docs, model manager foundation, Agent/MCP planning, and packaging foundations.", remaining_large_tasks="0-2"),
            FinalProductStageResponse(id="desktop-runtime", title="v0.2 desktop runtime", status="next", summary="Frozen backend runtime, real Tauri supervisor startup, app-owned logs/data, and persistent local background jobs.", remaining_large_tasks="5-8"),
            FinalProductStageResponse(id="installers", title="v0.3 installers", status="planned", summary="Signed/notarized macOS package, Windows installer, icons, shortcuts, update/uninstall behavior, and packaging QA.", remaining_large_tasks="5-8"),
            FinalProductStageResponse(id="agent-mcp", title="v0.4 safe Agent + MCP execution", status="planned", summary="MCP server lifecycle, read-only sandbox, tool allowlists, approvals, audit logs, and later controlled write execution.", remaining_large_tasks="6-10"),
            FinalProductStageResponse(id="v1", title="v1.0 polished product", status="target", summary="Installer-grade local desktop product with stable runtime, clear onboarding, safe execution, recovery, and polished UI.", remaining_large_tasks="4-6"),
        ],
        next_recommended_tasks=[
            "Task 235 — final v0.1 release gate and roadmap lock.",
            "Task 236 — local UI smoke-check results and first GitHub publication cleanup, if needed.",
            "Task 237 — v0.2 planning kickoff: frozen backend runtime and Tauri supervisor implementation.",
        ],
        publication_checks=[
            ReleaseCandidateAuditCommandResponse(label="Release audit", command="./scripts/audit_release_candidate.sh", purpose="Verify source layout, docs, safety rules, and no runtime database leakage."),
            ReleaseCandidateAuditCommandResponse(label="Backend targeted tests", command="cd backend && pytest -q tests/test_health.py tests/test_release_candidate_audit.py tests/test_api_inventory.py", purpose="Validate core API and release audit coverage before publication."),
            ReleaseCandidateAuditCommandResponse(label="Frontend build", command="cd frontend && npm ci && npm run build", purpose="Validate the production frontend bundle."),
            ReleaseCandidateAuditCommandResponse(label="Clean source archive", command="./scripts/prepare_source_release_archive.sh", purpose="Create a root-preserving archive excluding runtime/build/cache data."),
        ],
        stop_condition_for_v01=[
            "Audit passes with only expected local warnings.",
            "Frontend build passes.",
            "Backend targeted tests pass.",
            "Git status contains only intended source/docs/config changes.",
            "No runtime databases, build outputs, node_modules, or cache folders are committed.",
        ],
        not_v1_yet=[
            "No final frozen backend binary yet.",
            "No signed/notarized macOS DMG or Windows MSI yet.",
            "Tauri bridge is still foundation/read-only, not the final process supervisor.",
            "MCP servers are not installed or executed automatically.",
            "Agent execution is planning/manual tracking, not sandboxed tool execution.",
            "Background jobs are not persisted across app restarts yet.",
        ],
        safety_rules=[
            "Do not describe v0.1 source RC as a finished v1.0 product.",
            "Frontend must never run shell commands.",
            "Desktop startup must not trigger scan, index, rebuild, MCP, Agent, or model downloads.",
            "Model downloads remain backend-owned, opt-in, and allowlisted.",
            "MCP/Agent execution stays disabled until sandbox, approvals, and audit logs exist.",
        ],
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


def _read_png_header(path: Path) -> tuple[int, int, int, int] | None:
    import struct

    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 26 or data[12:16] != b"IHDR":
        return None
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, bit_depth, color_type
