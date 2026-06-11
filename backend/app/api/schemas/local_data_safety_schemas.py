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


class FirstLaunchChecklistItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    detail: str
    user_action: str | None = None


class FirstLaunchReadinessResponse(BaseModel):
    status: str
    title: str
    summary: str
    checklist: list[FirstLaunchChecklistItemResponse]
    recommended_flow: list[str]
    copy_commands: list[DesktopStartupCommandResponse]
    safety_note: str


class DesktopPackagingDecisionResponse(BaseModel):
    id: str
    title: str
    decision: str
    rationale: str


class DesktopPackagingPhaseResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    deliverables: list[str]


class DesktopPackagingDesignResponse(BaseModel):
    status: str
    title: str
    summary: str
    chosen_shell: str
    backend_strategy: str
    frontend_strategy: str
    local_data_strategy: str
    port_strategy: str
    logging_strategy: str
    lifecycle_strategy: str
    decisions: list[DesktopPackagingDecisionResponse]
    phases: list[DesktopPackagingPhaseResponse]
    user_experience: list[str]
    safety_rules: list[str]
    not_in_scope_now: list[str]




class MacOSAppPackageArtifactResponse(BaseModel):
    name: str
    purpose: str
    path: str
    included_in_generated_zip: bool


class MacOSAppPackageFoundationResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    shell_choice: str
    build_script: str
    app_bundle_name: str
    expected_output_path: str
    launch_contract: list[str]
    supervisor_contract: list[str]
    artifacts: list[MacOSAppPackageArtifactResponse]
    build_steps: list[str]
    validation_steps: list[str]
    safety_rules: list[str]
    not_yet_included: list[str]
    user_experience: list[str]




class DesktopSupervisorPortResponse(BaseModel):
    id: str
    title: str
    rule: str
    reason: str


class DesktopSupervisorLogResponse(BaseModel):
    id: str
    title: str
    path: str
    purpose: str


class DesktopSupervisorStateResponse(BaseModel):
    id: str
    title: str
    user_message: str
    technical_behavior: str


class DesktopSupervisorContractResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    supervisor_script: str
    default_backend_port: int
    health_endpoint: str
    logs_directory: str
    data_directory: str
    port_rules: list[DesktopSupervisorPortResponse]
    startup_states: list[DesktopSupervisorStateResponse]
    log_streams: list[DesktopSupervisorLogResponse]
    environment_contract: list[str]
    shutdown_contract: list[str]
    safety_rules: list[str]
    validation_steps: list[str]
    next_packaging_steps: list[str]




class MacOSAppSupervisorWiringStepResponse(BaseModel):
    id: str
    title: str
    summary: str
    user_message: str


class MacOSAppSupervisorWiringFileResponse(BaseModel):
    path: str
    purpose: str
    generated: bool


class MacOSAppSupervisorWiringResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    build_script: str
    app_bundle_path: str
    launcher_path: str
    app_data_directory: str
    logs_directory: str
    backend_health_url: str
    startup_flow: list[MacOSAppSupervisorWiringStepResponse]
    generated_files: list[MacOSAppSupervisorWiringFileResponse]
    supervisor_guarantees: list[str]
    user_experience: list[str]
    validation_steps: list[str]
    known_limitations: list[str]
    next_steps: list[str]


class BackendRuntimeBundleItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    path: str | None = None


class BackendRuntimeBundleStepResponse(BaseModel):
    id: str
    title: str
    summary: str
    command: str | None = None


class BackendRuntimeBundlePlanResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    recommended_strategy: str
    build_script: str
    runtime_manifest_path: str
    bundle_items: list[BackendRuntimeBundleItemResponse]
    build_steps: list[BackendRuntimeBundleStepResponse]
    validation_steps: list[str]
    safety_rules: list[str]
    known_limitations: list[str]
    next_steps: list[str]


class TauriShellScaffoldFileResponse(BaseModel):
    path: str
    purpose: str
    generated: bool


class TauriShellScaffoldPhaseResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    deliverables: list[str]


class TauriShellScaffoldResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    shell_path: str
    scaffold_script: str
    chosen_stack: str
    supervisor_mapping: list[str]
    generated_files: list[TauriShellScaffoldFileResponse]
    implementation_phases: list[TauriShellScaffoldPhaseResponse]
    safety_rules: list[str]
    validation_steps: list[str]
    known_limitations: list[str]
    next_steps: list[str]


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
