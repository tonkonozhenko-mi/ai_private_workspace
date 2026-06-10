from pydantic import BaseModel


class LocalDataBackupHintResponse(BaseModel):
    label: str
    command: str


class LocalDataSafetyResponse(BaseModel):
    status: str
    app_data_dir: str
    database_path: str
    database_exists: bool
    database_size_bytes: int
    repository: str
    vector_store: str
    llm_provider: str
    embedding_provider: str
    workspaces_count: int | None
    conversations_count: int | None
    saved_reports_count: int | None
    answer_notes_count: int | None
    warnings: list[str]
    protected_paths: list[str]
    safe_update_excludes: list[str]
    backup_hints: list[LocalDataBackupHintResponse]



class StartupChecklistItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    detail: str
    action_label: str | None = None
    copy_command: str | None = None


class StartupChecklistResponse(BaseModel):
    status: str
    summary: str
    items: list[StartupChecklistItemResponse]
    safe_to_continue: bool
    safety_note: str



class DesktopStartupCommandResponse(BaseModel):
    label: str
    command: str
    description: str


class DesktopStartupExperienceResponse(BaseModel):
    status: str
    summary: str
    open_last_workspace_enabled: bool
    last_workspace_storage_key: str
    suggested_next_action: str
    startup_commands: list[DesktopStartupCommandResponse]
    checklist: list[str]
    safety_notes: list[str]


class DatabaseBackupResponse(BaseModel):
    filename: str
    path: str
    size_bytes: int
    created_at: str
    is_current_database: bool = False


class CreateDatabaseBackupResponse(BaseModel):
    status: str
    backup: DatabaseBackupResponse
    safety_note: str


class DatabaseBackupListResponse(BaseModel):
    database_path: str
    backups: list[DatabaseBackupResponse]
    restore_note: str


class DatabaseRestorePlanRequest(BaseModel):
    backup_filename: str


class DatabaseRestorePlanResponse(BaseModel):
    status: str
    backup: DatabaseBackupResponse
    steps: list[str]
    copy_commands: list[str]
    warnings: list[str]
    safety_note: str


class DatabaseMigrationTableResponse(BaseModel):
    name: str
    exists: bool
    row_count: int | None = None


class DatabaseMigrationSafetyResponse(BaseModel):
    status: str
    database_path: str
    schema_version: str
    tables: list[DatabaseMigrationTableResponse]
    missing_tables: list[str]
    warnings: list[str]
    recommended_actions: list[str]
    safety_note: str


class SafeUpdateWorkflowResponse(BaseModel):
    status: str
    summary: str
    script_path: str
    dry_run_command: str
    apply_command: str
    required_excludes: list[str]
    backup_policy: str
    protected_paths: list[str]
    preflight_checks: list[str]
    warnings: list[str]
    safety_note: str


class ProductionReadinessItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    detail: str
    recommended_action: str | None = None


class PackagingOptionResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    steps: list[str]
    copy_commands: list[str]


class ProductionReadinessResponse(BaseModel):
    status: str
    summary: str
    readiness_score: int
    items: list[ProductionReadinessItemResponse]
    packaging_options: list[PackagingOptionResponse]
    recommended_next_steps: list[str]
    safety_note: str
