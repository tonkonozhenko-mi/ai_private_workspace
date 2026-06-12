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




class DesktopRuntimeValidationCommandResponse(BaseModel):
    label: str
    command: str
    purpose: str


class DesktopRuntimeReadinessItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    evidence: str
    next_action: str


class DesktopRuntimeReadinessResponse(BaseModel):
    status: str
    title: str
    summary: str
    current_phase: str
    v01_position: str
    v02_goal: str
    readiness_items: list[DesktopRuntimeReadinessItemResponse]
    implementation_order: list[str]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    blocked_until: list[str]
    safety_rules: list[str]
    honest_remaining_work: str




class DesktopRuntimePreflightItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    evidence: str
    fix_command: str | None = None


class DesktopRuntimePreflightResponse(BaseModel):
    status: str
    title: str
    summary: str
    preflight_script: str
    runtime_manifest_path: str
    package_script: str
    items: list[DesktopRuntimePreflightItemResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    pass_criteria: list[str]
    fail_fast_conditions: list[str]
    safety_rules: list[str]
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


class TauriSupervisorBridgeStateResponse(BaseModel):
    id: str
    title: str
    user_message: str
    shell_behavior: str
    backend_check: str | None = None


class TauriSupervisorBridgeCommandResponse(BaseModel):
    name: str
    purpose: str
    execution: str


class TauriSupervisorBridgeResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    bridge_file: str
    tauri_command_strategy: str
    backend_start_strategy: str
    readiness_strategy: str
    log_strategy: str
    startup_states: list[TauriSupervisorBridgeStateResponse]
    tauri_commands: list[TauriSupervisorBridgeCommandResponse]
    implementation_steps: list[str]
    validation_steps: list[str]
    safety_rules: list[str]
    known_limitations: list[str]
    next_steps: list[str]



class TauriSupervisorStaticGateItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    evidence: str


class TauriSupervisorStaticGateResponse(BaseModel):
    status: str
    title: str
    summary: str
    check_script: str
    bridge_file: str
    items: list[TauriSupervisorStaticGateItemResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]




class DesktopTechnologyOptionResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    strengths: list[str]
    tradeoffs: list[str]


class DesktopTechnologyDecisionResponse(BaseModel):
    status: str
    title: str
    summary: str
    current_candidate: str
    decision_state: str
    why_it_was_chosen: list[str]
    alternatives: list[DesktopTechnologyOptionResponse]
    decision_guardrails: list[str]
    when_to_reconsider: list[str]
    next_steps: list[str]



class DesktopStackComponentResponse(BaseModel):
    id: str
    name: str
    role: str
    license_model: str
    why_selected: str
    maintenance_note: str


class DesktopRuntimeFreezeMilestoneResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    exit_criteria: list[str]


class DesktopStackAndRuntimeContractResponse(BaseModel):
    status: str
    title: str
    summary: str
    desktop_shell: str
    backend_runtime_strategy: str
    frontend_strategy: str
    packaging_strategy: str
    stack_principles: list[str]
    selected_components: list[DesktopStackComponentResponse]
    rejected_paths: list[DesktopTechnologyOptionResponse]
    runtime_freeze_milestones: list[DesktopRuntimeFreezeMilestoneResponse]
    staging_contract: list[str]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]


class StagedBackendRuntimeItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    path: str | None = None


class StagedBackendRuntimeContractResponse(BaseModel):
    status: str
    title: str
    summary: str
    staging_script: str
    check_script: str
    staging_directory: str
    launcher_path: str
    manifest_path: str
    items: list[StagedBackendRuntimeItemResponse]
    runtime_contract: list[str]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]


class PyInstallerBackendRuntimeItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    path: str | None = None


class PyInstallerBackendRuntimeContractResponse(BaseModel):
    status: str
    title: str
    summary: str
    builder: str
    build_script: str
    check_script: str
    entrypoint_path: str
    spec_path: str
    frozen_runtime_dir: str
    manifest_path: str
    items: list[PyInstallerBackendRuntimeItemResponse]
    runtime_contract: list[str]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]


class RuntimeSelectionCandidateResponse(BaseModel):
    id: str
    title: str
    status: str
    path: str
    selection_rule: str
    fallback_rule: str


class FrozenBackendRuntimeSelectionResponse(BaseModel):
    status: str
    title: str
    summary: str
    selection_strategy: str
    tauri_bridge_file: str
    check_script: str
    candidates: list[RuntimeSelectionCandidateResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]



class FrozenBackendSmokeItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    command: str | None = None


class FrozenBackendSmokeContractResponse(BaseModel):
    status: str
    title: str
    summary: str
    smoke_script: str
    smoke_mode: str
    health_url: str
    items: list[FrozenBackendSmokeItemResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]



class AppOwnedBackendStartupGateItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    command: str | None = None


class AppOwnedBackendStartupGateResponse(BaseModel):
    status: str
    title: str
    summary: str
    startup_mode: str
    tauri_bridge_file: str
    check_script: str
    required_gates: list[AppOwnedBackendStartupGateItemResponse]
    startup_contract: list[str]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]



class AppOwnedBackendStartupImplementationItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    evidence: str
    command: str | None = None


class AppOwnedBackendStartupImplementationResponse(BaseModel):
    status: str
    title: str
    summary: str
    startup_mode: str
    tauri_bridge_file: str
    check_script: str
    runtime_priority: list[str]
    implementation_items: list[AppOwnedBackendStartupImplementationItemResponse]
    tauri_commands: list[str]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]



class AppOwnedBackendHealthReadinessItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    evidence: str
    command: str | None = None


class AppOwnedBackendHealthReadinessResponse(BaseModel):
    status: str
    title: str
    summary: str
    readiness_mode: str
    health_url: str
    tauri_bridge_file: str
    check_script: str
    implementation_items: list[AppOwnedBackendHealthReadinessItemResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    safety_rules: list[str]
    next_steps: list[str]



class MacOSTauriSmokeRunbookItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    command: str | None = None


class MacOSTauriSmokeRunbookResponse(BaseModel):
    status: str
    title: str
    summary: str
    runbook_doc: str
    check_script: str
    platform: str
    prerequisites: list[str]
    smoke_steps: list[MacOSTauriSmokeRunbookItemResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    pass_criteria: list[str]
    fail_fast_conditions: list[str]
    safety_rules: list[str]
    next_steps: list[str]



class WindowsPackagingArtifactResponse(BaseModel):
    path: str
    purpose: str
    generated: bool


class WindowsPackagingPhaseResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    deliverables: list[str]


class WindowsPackagingFoundationResponse(BaseModel):
    status: str
    title: str
    summary: str
    package_goal: str
    shell_choice: str
    app_name: str
    app_data_directory: str
    logs_directory: str
    backend_health_url: str
    packaging_strategy: str
    supervisor_strategy: str
    installer_strategy: str
    scripts: list[WindowsPackagingArtifactResponse]
    lifecycle_flow: list[str]
    implementation_phases: list[WindowsPackagingPhaseResponse]
    validation_steps: list[str]
    safety_rules: list[str]
    known_limitations: list[str]
    next_steps: list[str]


class ReleaseCandidateAuditItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    detail: str
    recommended_action: str | None = None


class ReleaseCandidateAuditCommandResponse(BaseModel):
    label: str
    command: str
    purpose: str


class ReleaseCandidateAuditResponse(BaseModel):
    status: str
    title: str
    summary: str
    release_label: str
    readiness_score: int
    audit_script: str
    source_archive_policy: list[str]
    blocked_items: list[ReleaseCandidateAuditItemResponse]
    review_items: list[ReleaseCandidateAuditItemResponse]
    passed_items: list[ReleaseCandidateAuditItemResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    final_handoff_steps: list[str]
    safety_rules: list[str]
    known_limitations: list[str]




class V01DemoStepResponse(BaseModel):
    id: str
    title: str
    summary: str
    expected_result: str
    ui_location: str


class V01RepositoryFileResponse(BaseModel):
    path: str
    purpose: str


class V01HandoffResponse(BaseModel):
    status: str
    title: str
    release_label: str
    summary: str
    github_ready: bool
    demo_story: str
    demo_steps: list[V01DemoStepResponse]
    repository_highlights: list[str]
    important_files: list[V01RepositoryFileResponse]
    validation_commands: list[DesktopRuntimeValidationCommandResponse]
    release_notes: list[str]
    known_limitations: list[str]
    next_after_v01: list[str]
    safety_rules: list[str]



class ProductCompletionStageResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    remaining_large_tasks: int


class ProductCompletionRoadmapResponse(BaseModel):
    status: str
    title: str
    summary: str
    current_stage: str
    honest_completion_estimate: str
    stages: list[ProductCompletionStageResponse]
    next_recommended_tasks: list[str]
    not_done_yet: list[str]
    safety_rules: list[str]



class FinalProductStageResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    remaining_large_tasks: str


class FinalProductStatusResponse(BaseModel):
    status: str
    title: str
    summary: str
    current_milestone: str
    current_stage_completion: str
    honest_v1_estimate: str
    source_rc_verdict: str
    remaining_current_stage_tasks: list[str]
    stages: list[FinalProductStageResponse]
    next_recommended_tasks: list[str]
    publication_checks: list[ReleaseCandidateAuditCommandResponse]
    stop_condition_for_v01: list[str]
    not_v1_yet: list[str]
    safety_rules: list[str]





class V01UISmokeCheckItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    expected_result: str
    ui_location: str
    must_not_happen: list[str] = []


class V01UISmokeCheckResponse(BaseModel):
    status: str
    title: str
    summary: str
    estimated_duration: str
    checklist: list[V01UISmokeCheckItemResponse]
    copy_commands: list[ReleaseCandidateAuditCommandResponse]
    pass_criteria: list[str]
    fail_fast_conditions: list[str]
    safety_note: str

class V01ReleaseGateItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    command: str | None = None


class V01ReleaseGateResponse(BaseModel):
    status: str
    title: str
    summary: str
    current_position: str
    source_rc_remaining_tasks: str
    v1_remaining_large_tasks: str
    release_gate_items: list[V01ReleaseGateItemResponse]
    go_no_go_rule: str
    next_actions: list[str]
    safety_rules: list[str]



class V01PublicationHandoffStepResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    command: str | None = None
    expected_result: str


class V01PublicationHandoffResponse(BaseModel):
    status: str
    title: str
    summary: str
    current_position: str
    publish_verdict: str
    v01_remaining_work: str
    v1_remaining_work: str
    steps: list[V01PublicationHandoffStepResponse]
    source_archive_name: str
    git_commit_message: str
    github_push_commands: list[ReleaseCandidateAuditCommandResponse]
    do_not_commit: list[str]
    after_publish: list[str]
    safety_rules: list[str]

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
