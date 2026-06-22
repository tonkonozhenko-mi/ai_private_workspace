
export interface ProjectFileResponse {
  path: string;
  extension: string | null;
  size_bytes: number;
  detected_type: string;
}

export interface DetectedSkillResponse {
  name: string;
  category: string;
  confidence: string;
  evidence: string[];
}

export interface FileSelectionRulesRequest {
  profile: string;
  include_patterns: string[];
  exclude_patterns: string[];
}

export interface WorkspaceIndexingRules {
  workspace_id: string;
  profile: string;
  include_patterns: string[];
  exclude_patterns: string[];
  include_rules_count: number;
  exclude_rules_count: number;
  updated_at: string | null;
  source: "saved" | "default" | string;
}

export interface FileSelectionPreviewItem {
  path: string;
  detected_type: string;
  size_bytes: number;
  decision: "included" | "excluded";
  reason: string;
  matched_rule: string | null;
}

export interface FileSelectionPreview {
  workspace_id: string;
  project_path: string;
  profile: string;
  total_files: number;
  included_files_count: number;
  excluded_files_count: number;
  skipped_files_count: number;
  include_rules_count: number;
  exclude_rules_count: number;
  included_samples: FileSelectionPreviewItem[];
  excluded_samples: FileSelectionPreviewItem[];
}

export interface ScanChanges {
  has_baseline: boolean;
  changed: boolean;
  added_count: number;
  removed_count: number;
  modified_count: number;
  current_file_count: number;
  previous_file_count: number;
}

export interface ProjectRisk {
  text: string;
  file: string | null;
}

export interface ProjectStartPoint {
  file: string;
  reason: string;
}

export interface ProjectRunCommand {
  command: string;
  note: string;
}

export interface ProjectUnderstandingResponse {
  workspace_id: string;
  model: string;
  generated_at: string;
  index_signature: string;
  summary: string;
  risks: ProjectRisk[];
  sources: string[];
  is_stale: boolean;
  architecture: string;
  start_here: ProjectStartPoint[];
  run_commands: ProjectRunCommand[];
}

export interface ProjectTodo {
  file: string;
  line: number;
  marker: string;
  text: string;
}

export interface ProjectTodosResponse {
  total: number;
  truncated: boolean;
  items: ProjectTodo[];
}

export interface GgufCatalogItem {
  id: string;
  name: string;
  model_type: "llm" | "embedding" | "reranker";
  repo_id: string;
  filename: string;
  quantization: string;
  size_bytes: number;
  recommended: boolean;
  min_ram_gb: number | null;
  ollama_tag: string | null;
  download_url: string;
  installed: boolean;
  active: boolean;
  custom: boolean;
}

export interface GgufDownloadJob {
  id: string;
  model_id: string;
  name: string;
  model_type: "llm" | "embedding" | "reranker";
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  downloaded_bytes: number;
  total_bytes: number | null;
  progress_percent: number | null;
  destination_path: string | null;
  error: string | null;
}

export interface LlamaRuntimeStatus {
  binary_available: boolean;
  models_ready: boolean;
  running: boolean;
  active_llm_model: string | null;
  llm_url: string | null;
  embed_url: string | null;
}

export interface ProjectScanResponse {
  project_path: string;
  total_files: number;
  scanned_files: number;
  skipped_files: number;
  total_size_bytes: number;
  detected_skills: DetectedSkillResponse[];
  files: ProjectFileResponse[];
}

export interface GitCommitResponse {
  short_hash: string;
  subject: string;
  author: string;
  committed_at: string;
}

export interface GitContributorResponse {
  name: string;
  commits: number;
  share: number;
  commits_last_90_days: number;
  last_active: string | null;
}

export interface GitFileHotspotResponse {
  path: string;
  changes: number;
}

export interface GitActivityBucketResponse {
  period_start: string;
  commits: number;
}

export interface GitMergeActivityResponse {
  merge_commits: number;
  pull_requests_detected: number;
  merge_requests_detected: number;
  source_branch_types: Record<string, number>;
  target_branches: Record<string, number>;
}

export interface GitBranchStrategyResponse {
  default_branch: string | null;
  total_branches: number;
  long_lived_branches: string[];
  prefixes: string[];
  inferred_strategy: string;
  rationale: string;
}

export interface GitInsightsResponse {
  is_repo: boolean;
  branch: string | null;
  last_commit: GitCommitResponse | null;
  total_commits: number;
  commits_last_30_days: number;
  contributors_count: number;
  first_commit_at: string | null;
  top_contributors: GitContributorResponse[];
  hotspots: GitFileHotspotResponse[];
  branch_strategy: GitBranchStrategyResponse | null;
  commits_last_7_days: number;
  commits_last_90_days: number;
  active_contributors_90d: number;
  merge_commit_share: number;
  recent_commits: GitCommitResponse[];
  activity_weeks: GitActivityBucketResponse[];
  activity_by_weekday: number[];
  merge_activity: GitMergeActivityResponse | null;
}

export interface IndexedDocumentSummaryResponse {
  source_path: string;
  chunks_count: number;
}

export interface WorkspaceIndexResponse {
  workspace_id: string;
  indexed_files_count: number;
  chunks_count: number;
  skipped_files_count: number;
  documents: IndexedDocumentSummaryResponse[];
}

export type WorkspacePersistence = "saved" | "temporary";

export interface CreateWorkspaceRequest {
  name: string;
  project_path: string;
  assistant_mode: string;
  privacy_mode: string;
  persistence?: WorkspacePersistence;
}

export interface CreatedWorkspace {
  id: string;
  name: string;
  project_path: string;
  assistant_mode: string;
  privacy_mode: string;
  created_at: string;
  archived_at: string | null;
  persistence: string;
}

export interface PurgeTemporaryResult {
  deleted_count: number;
  deleted_ids: string[];
}

export interface WorkspaceFileWriteResult {
  workspace_id: string;
  relative_path: string;
  bytes_written: number;
  replaced_existing: boolean;
  status: string;
}

export interface WorkspaceOverviewItem {
  workspace_id: string;
  name: string;
  project_path: string;
  assistant_mode: string;
  privacy_mode: string;
  created_at: string;
  archived_at: string | null;
  is_archived: boolean;
  readiness_status: string;
  quick_start_status: string;
  next_action_id: string | null;
  next_action_title: string | null;
  has_scan: boolean;
  detected_skills_count: number;
  index_status: string;
  commands_pending_count: number;
  last_event_title: string | null;
  last_event_type: string | null;
  last_event_at: string | null;
  storage_total_bytes: number;
  storage_breakdown: Record<string, number>;
  persistence: string;
  engine: string | null;
}

export interface WorkspacesOverview {
  total_workspaces: number;
  items: WorkspaceOverviewItem[];
}

export interface RuntimeMemoryModelInfo {
  name: string;
  size_bytes: number;
  size_vram_bytes: number;
}

export interface RuntimeMemory {
  runtime_reachable: boolean;
  total_ram_bytes: number;
  loaded_bytes: number;
  models: RuntimeMemoryModelInfo[];
}

export interface WorkspaceStorage {
  workspace_id: string;
  total_bytes: number;
  breakdown: Record<string, number>;
  computed_at: string | null;
}

export interface LocalDataBackupHint {
  label: string;
  command: string;
}

export interface StartupChecklistItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  detail: string;
  action_label: string | null;
  copy_command: string | null;
}

export interface DesktopStartupCommand {
  label: string;
  command: string;
  description: string;
}

export interface DatabaseBackup {
  filename: string;
  path: string;
  size_bytes: number;
  created_at: string;
  is_current_database: boolean;
}

export interface DatabaseMigrationTable {
  name: string;
  exists: boolean;
  row_count: number | null;
}

export interface RuntimeTroubleshootingStep {
  title: string;
  detail: string;
  copy_command: string | null;
}

export interface RuntimeTroubleshootingIssue {
  id: string;
  title: string;
  severity: string;
  component: string;
  summary: string;
  details: string;
  steps: RuntimeTroubleshootingStep[];
}

export interface FirstLaunchChecklistItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  detail: string;
  user_action: string | null;
}

export interface TauriSupervisorBridgeState {
  id: string;
  title: string;
  user_message: string;
  shell_behavior: string;
  backend_check: string | null;
}

export interface TauriSupervisorBridgeCommand {
  name: string;
  purpose: string;
  execution: string;
}

export interface TauriSupervisorStaticGateItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string;
}

export interface DesktopTechnologyOption {
  id: string;
  title: string;
  status: string;
  summary: string;
  strengths: string[];
  tradeoffs: string[];
}

export interface DesktopStackComponent {
  id: string;
  name: string;
  role: string;
  license_model: string;
  why_selected: string;
  maintenance_note: string;
}

export interface DesktopRuntimeFreezeMilestone {
  id: string;
  title: string;
  status: string;
  summary: string;
  exit_criteria: string[];
}

export interface WindowsPackagingArtifact {
  path: string;
  purpose: string;
  generated: boolean;
}

export interface WindowsPackagingPhase {
  id: string;
  title: string;
  status: string;
  summary: string;
  deliverables: string[];
}

export interface ReleaseCandidateAuditItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  detail: string;
  recommended_action: string | null;
}

export interface ReleaseCandidateAuditCommand {
  label: string;
  command: string;
  purpose: string;
}

export interface V01DemoStep {
  id: string;
  title: string;
  summary: string;
  expected_result: string;
  ui_location: string;
}

export interface V01RepositoryFile {
  path: string;
  purpose: string;
}

export interface V01ReleaseGateItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface V01UISmokeCheckItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  expected_result: string;
  ui_location: string;
  must_not_happen: string[];
}

export interface V01PublicationHandoffStep {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
  expected_result: string;
}

export interface FinalProductStage {
  id: string;
  title: string;
  status: string;
  summary: string;
  remaining_large_tasks: string;
}

export interface FirstLaunchReadiness {
  status: string;
  title: string;
  summary: string;
  checklist: FirstLaunchChecklistItem[];
  recommended_flow: string[];
  copy_commands: DesktopStartupCommand[];
  safety_note: string;
}

export interface DesktopPackagingDecision {
  id: string;
  title: string;
  decision: string;
  rationale: string;
}

export interface DesktopPackagingPhase {
  id: string;
  title: string;
  status: string;
  summary: string;
  deliverables: string[];
}

export interface MacOSAppPackageArtifact {
  name: string;
  purpose: string;
  path: string;
  included_in_generated_zip: boolean;
}

export interface MacOSAppSupervisorWiringStep {
  id: string;
  title: string;
  summary: string;
  user_message: string;
}

export interface MacOSAppSupervisorWiringFile {
  path: string;
  purpose: string;
  generated: boolean;
}

export interface BackendRuntimeBundleItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  path: string | null;
}

export interface BackendRuntimeBundleStep {
  id: string;
  title: string;
  summary: string;
  command: string | null;
}

export interface DesktopRuntimeReadinessItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string;
  next_action: string;
}

export interface DesktopRuntimePreflightItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string;
  fix_command: string | null;
}

export interface TauriShellScaffoldFile {
  path: string;
  purpose: string;
  generated: boolean;
}

export interface TauriShellScaffoldPhase {
  id: string;
  title: string;
  status: string;
  summary: string;
  deliverables: string[];
}

export interface DesktopSupervisorPortRule {
  id: string;
  title: string;
  rule: string;
  reason: string;
}

export interface DesktopSupervisorLogStream {
  id: string;
  title: string;
  path: string;
  purpose: string;
}

export interface DesktopSupervisorState {
  id: string;
  title: string;
  user_message: string;
  technical_behavior: string;
}

export interface ProductionReadinessItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  detail: string;
  recommended_action: string | null;
}

export interface PackagingOption {
  id: string;
  title: string;
  status: string;
  summary: string;
  steps: string[];
  copy_commands: string[];
}

export interface TimelineEvent {
  id: string;
  workspace_id: string;
  event_type: string;
  title: string;
  summary: string;
  metadata: Record<string, string>;
  created_at: string;
}

export interface RagSource {
  chunk_id: string;
  source_path: string;
  score: number;
  preview: string;
  metadata?: Record<string, string>;
}

export interface RagQualityWarning {
  code: string;
  message: string;
  severity: string;
  evidence: string[];
}

export interface SkillProfileItem {
  id: string;
  name: string;
  enabled: boolean;
  custom_instructions: string;
}

export interface WorkspaceSkillProfile {
  workspace_id: string;
  profile: string;
  skills: SkillProfileItem[];
  enabled_skills_count: number;
  updated_at: string | null;
  source: "saved" | "default" | string;
}

export interface WorkspaceSkillProfileRequest {
  profile: string;
  skills: SkillProfileItem[];
}

export interface SkillContextRequest {
  id: string;
  name: string;
  custom_instructions: string;
}

export interface LLMUsageMetrics {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  latency_ms?: number | null;
  tokens_per_second?: number | null;
  provider?: string | null;
  model?: string | null;
  estimated?: boolean;
  context_window?: number | null;
}

export interface AskSkillProfileAudit {
  source: string;
  profile: string;
  active_skills: string[];
  guidance_count: number;
  updated_at?: string | null;
}

export interface WorkspaceQuestionAnswer {
  workspace_id: string;
  conversation_id?: string | null;
  conversation_message_id?: string | null;
  question: string;
  answer: string;
  sources: RagSource[];
  used_context_chunks: number;
  project_memory_used?: number;
  project_facts_used?: number;
  llm_provider: string;
  llm_model: string | null;
  diagnostic_code?: string | null;
  diagnostic_message?: string | null;
  quality_warnings?: RagQualityWarning[];
  usage?: LLMUsageMetrics | null;
  skill_profile?: AskSkillProfileAudit | null;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  workspace_id: string;
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
  sources_count: number;
  used_context_chunks: number;
  llm_provider?: string | null;
  llm_model?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  latency_ms?: number | null;
  skill_profile_source?: string | null;
  skill_profile?: string | null;
  active_skills: string[];
  guidance_count: number;
  sources: RagSource[];
}

export interface ConversationExport {
  conversation_id: string;
  format: string;
  filename: string;
  content: string;
}

export interface ConversationAnswerNote {
  id: string;
  workspace_id: string;
  conversation_id: string;
  message_id: string;
  title: string;
  content: string;
  source_question?: string | null;
  source_paths: string[];
  created_at: string;
  updated_at: string;
  pinned_at?: string | null;
  is_pinned: boolean;
}

export interface ConversationContextPreview {
  conversation_id: string;
  title: string;
  questions_count: number;
  answers_count: number;
  notes_count: number;
  source_paths: string[];
  reusable_context: string;
  safety_note: string;
}

export interface WorkspaceConversation {
  id: string;
  workspace_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
  messages_count: number;
  user_messages_count: number;
  assistant_messages_count: number;
  total_tokens?: number | null;
  last_question?: string | null;
  last_answer_preview?: string | null;
  last_llm_provider?: string | null;
  last_llm_model?: string | null;
  last_skill_profile_source?: string | null;
  active_skills: string[];
  pinned_at?: string | null;
  archived_at?: string | null;
  is_pinned: boolean;
  is_archived: boolean;
}

export interface ReportSection {
  title: string;
  content: string;
  bullets: string[];
}

export interface ReportQualityCheck {
  id: string;
  label: string;
  status: string;
  detail: string;
}

export interface ReportQualitySummary {
  score: number;
  status: string;
  source_coverage_count: number;
  source_coverage_label: string;
  checks: ReportQualityCheck[];
  warnings: string[];
}

export interface WorkspaceReport {
  workspace_id: string;
  title: string;
  summary: string;
  sections: ReportSection[];
  generated_from: string[];
  report_type: string;
  export_markdown: string;
  safety_note: string;
  quality: ReportQualitySummary;
}

export interface ReportTemplate {
  id: string;
  title: string;
  description: string;
  best_for: string;
  requires_scan: boolean;
  output_style: string;
  source_strategy: string;
}

export interface ReportCatalog {
  workspace_id: string;
  templates: ReportTemplate[];
  safety_notes: string[];
}

export interface BuildCustomWorkspaceReportRequest {
  title?: string | null;
  summary?: string | null;
  report_type?: string;
  note_ids: string[];
  conversation_ids: string[];
  extra_context?: string | null;
}

export interface SaveEditedWorkspaceReportRequest {
  title: string;
  summary: string;
  report_type: string;
  sections: ReportSection[];
  generated_from: string[];
  export_markdown: string;
  safety_note: string;
}

export interface SavedWorkspaceReport {
  id: string;
  workspace_id: string;
  report_type: string;
  title: string;
  summary: string;
  export_markdown: string;
  export_text: string;
  report_json: Record<string, unknown>;
  generated_from: string[];
  created_at: string;
  updated_at: string;
  pinned_at?: string | null;
  is_pinned: boolean;
  quality: ReportQualitySummary;
}

export interface UpdateSavedWorkspaceReportRequest {
  title?: string;
  summary?: string;
  export_markdown?: string;
  export_text?: string;
  report_json?: Record<string, unknown>;
  generated_from?: string[];
}

export interface WorkspaceIndexStatus {
  workspace_id: string;
  status: string;
  indexed_files_count: number;
  chunks_count: number;
  skipped_files_count: number;
  last_indexed_at: string | null;
  last_error: string | null;
}

export interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  project_path: string;
  assistant_mode: string;
  privacy_mode: string;
  created_at: string;
  has_scan: boolean;
  detected_skills_count: number;
  index_status: WorkspaceIndexStatus;
  recent_events: TimelineEvent[];
}

export interface WorkspaceModelsDashboardSummary {
  workspace_id: string;
  overall_status: string;
  primary_next_action_id: string | null;
  primary_next_action_title: string | null;
  selected_llm: string | null;
  selected_embedding: string | null;
  active_llm: string;
  active_embedding: string;
  can_ask_with_selected_llm: boolean;
  can_search_with_selected_embedding: boolean;
  selected_embedding_matches_active_runtime: boolean;
  embedding_index_status: string;
  embedding_plan_status: string;
  top_recommended_model: string | null;
  top_recommended_model_score: number | null;
  performance_models_count: number;
  warnings_count: number;
  notes: string[];
}

export interface WorkspaceSelectedModel {
  provider: string;
  model: string;
  model_type: string;
  selected_at: string;
  selected_reason: string | null;
}

export interface WorkspaceModelSelection {
  workspace_id: string;
  selected_llm: WorkspaceSelectedModel | null;
  selected_embedding: WorkspaceSelectedModel | null;
  notes: string[];
}

export interface UpdateWorkspaceModelSelectionRequest {
  provider: string;
  model: string;
  model_type: "llm" | "embedding";
  selected_reason?: string;
}

export interface SelectedModelRuntimeStatus {
  model_type: string;
  selected_provider: string | null;
  selected_model: string | null;
  active_provider: string;
  active_model: string;
  matches_active_runtime: boolean;
  requires_backend_restart: boolean;
  requires_reindex: boolean;
  status: string;
  message: string;
}

export interface SelectedModelUsagePlan {
  can_ask_with_selected_llm: boolean;
  can_index_with_selected_embedding: boolean;
  can_search_with_selected_embedding: boolean;
  can_use_selected_models_fully: boolean;
  active_llm_provider: string;
  active_llm_model: string;
  active_embedding_provider: string;
  active_embedding_model: string;
  index_status: string;
  recommended_actions: string[];
  notes: string[];
}

export interface LocalModelDefinition {
  id: string;
  provider: string;
  model_name: string;
  model_type: string;
  display_name: string;
  description: string;
  capabilities: string[];
  quality_tier: string;
  speed_tier: string;
  notes: string[];
}

export interface WorkspaceModelRecommendation {
  model: LocalModelDefinition;
  catalog_score: number;
  performance_score: number | null;
  final_score: number;
  reasons: string[];
  warnings: string[];
  historical_signals: Record<string, string>;
}

export interface WorkspaceModelRecommendationResult {
  recommendations: WorkspaceModelRecommendation[];
  notes: string[];
}

export interface ModelPerformanceItem {
  provider: string;
  model: string;
  experiments_count: number;
  completed_runs_count: number;
  failed_runs_count: number;
  ratings_count: number;
  average_rating: number | null;
  preferred_votes: number;
  average_latency_ms: number | null;
  average_quality_warnings_count: number | null;
  average_sources_count: number | null;
  common_tags: string[];
  score: number;
  score_reasons: string[];
}

export interface ModelPerformanceSummary {
  items: ModelPerformanceItem[];
  notes: string[];
}

export interface WorkspaceModelsDashboard {
  workspace_id: string;
  selected_llm_provider: string | null;
  selected_llm_model: string | null;
  selected_embedding_provider: string | null;
  selected_embedding_model: string | null;
  overall_status: string;
  primary_next_action_id: string | null;
  primary_next_action_title: string | null;
  selection: {
    selected_llm: WorkspaceSelectedModel | null;
    selected_embedding: WorkspaceSelectedModel | null;
    notes: string[];
  };
  selection_status: {
    llm_status: SelectedModelRuntimeStatus;
    embedding_status: SelectedModelRuntimeStatus;
    overall_status: string;
    recommended_actions: string[];
    notes: string[];
  };
  usage_plan: SelectedModelUsagePlan;
  embedding_indexing_plan: {
    selected_provider: string | null;
    selected_model: string | null;
    active_provider: string;
    active_model: string;
    index_status: string;
    can_index_now: boolean;
    can_search_now: boolean;
    requires_backend_restart: boolean;
    requires_reindex: boolean;
    requires_new_vector_collection: boolean;
    plan_status: string;
    recommended_actions: string[];
    warnings: string[];
    notes: string[];
  };
  recommendations: WorkspaceModelRecommendationResult;
  performance_summary: ModelPerformanceSummary;
  notes: string[];
}

export interface ModelExperimentCandidateRequest {
  provider: string;
  model: string;
  model_type?: "llm";
}

export interface ModelExperimentPlanRequest {
  workspace_id: string;
  question: string;
  candidates: ModelExperimentCandidateRequest[];
  attached_documents?: { name: string; content: string }[];
}

export interface ModelExperimentPlanCandidate {
  provider: string;
  model: string;
  known_in_catalog: boolean;
  display_name: string;
  model_type: string;
  requires_reindex: boolean;
  requires_backend_restart: boolean;
  warnings: string[];
}

export interface ModelExperimentPlan {
  workspace_id: string;
  question: string;
  experiment_type: string;
  candidates: ModelExperimentPlanCandidate[];
  shared_context_strategy: string;
  requires_reindex: boolean;
  can_compare_without_reindex: boolean;
  recommended_actions: string[];
  notes: string[];
}

export interface ModelExperimentRunCandidate {
  provider: string;
  model: string;
  status: string;
  answer: string | null;
  error: string | null;
  llm_provider: string;
  llm_model: string | null;
  used_context_chunks: number;
  sources_count: number;
  quality_warnings_count: number;
  latency_ms: number | null;
}

export interface ModelExperimentRun {
  id: string;
  workspace_id: string;
  question: string;
  experiment_type: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  shared_context_sources_count: number;
  candidates: ModelExperimentRunCandidate[];
  notes: string[];
}

export interface ModelExperimentRatingRequest {
  provider: string;
  model: string;
  rating: number;
  is_preferred?: boolean;
  tags?: string[];
  comment?: string;
}

export interface ModelExperimentRating {
  id: string;
  experiment_id: string;
  provider: string;
  model: string;
  rating: number;
  is_preferred: boolean;
  tags: string[];
  comment: string | null;
  created_at: string;
}

export interface LocalAIActivationStep {
  id: string;
  title: string;
  description: string;
  command: string | null;
  commands: string[] | null;
  status: string;
  reason: string;
  category: string;
}

export interface LocalAIActivationGuide {
  workspace_id: string;
  overall_status: string;
  selected_llm: string | null;
  selected_embedding: string | null;
  active_llm: string;
  active_embedding: string;
  selected_vector_store: string | null;
  active_vector_store: string;
  steps: LocalAIActivationStep[];
  notes: string[];
}

export interface WorkspaceDashboard {
  workspace_id: string;
  workspace_name: string;
  assistant_mode: string;
  status: string;
  summary: WorkspaceSummary;
  quick_start: {
    workspace_id: string;
    status: string;
    next_action_id: string | null;
    next_action_title: string | null;
  };
  recent_events: TimelineEvent[];
  primary_next_action_id: string | null;
  primary_next_action_title: string | null;
  models_summary: WorkspaceModelsDashboardSummary | null;
}

export interface WorkspaceUIAction {
  id: string;
  title: string;
  description: string;
  method: string;
  endpoint: string;
  category: string;
  status: string;
  is_primary: boolean;
  mutates_data: boolean;
  reason: string;
}

export interface WorkspaceUIActionCatalog {
  workspace_id: string;
  primary_action_id: string | null;
  actions: WorkspaceUIAction[];
  notes: string[];
}

export interface WorkspaceDetailBundle {
  dashboard: WorkspaceDashboard;
  actions: WorkspaceUIActionCatalog;
  modelsSummary: WorkspaceModelsDashboardSummary;
}

export interface WorkspaceModelsDetailBundle {
  dashboard: WorkspaceModelsDashboard;
  activationGuide: LocalAIActivationGuide;
}

export interface WorkspaceJob {
  job_id: string;
  workspace_id: string;
  job_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | string;
  title: string;
  message: string | null;
  result_summary: Record<string, string>;
  request_summary: Record<string, string>;
  error: string | null;
  cancellation_requested: boolean;
  progress_current: number | null;
  progress_total: number | null;
  progress_percent: number | null;
  current_step: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface MCPServerTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  transport: string;
  command: string;
  args: string[];
  env_vars: string[];
  default_scope: string;
  risk_level: string;
  capabilities: string[];
  example_tools: string[];
  setup_notes: string[];
}

export interface MCPServerCatalog {
  summary: string;
  templates: MCPServerTemplate[];
  safety_note: string;
  recommended_flow: string[];
}

export interface MCPConfigPreviewRequest {
  template_id: string;
  workspace_id?: string | null;
  project_path?: string | null;
  env_overrides?: Record<string, string>;
}

export interface MCPServerConfigPreview {
  template_id: string;
  name: string;
  transport: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  config_json: Record<string, unknown>;
  risk_level: string;
  scope: string;
  allowed_by_default: boolean;
  guardrails: string[];
  setup_steps: string[];
  test_plan: string[];
  generated_at: string;
}

export interface MCPConnectionCheckRequest {
  template_id: string;
}

export interface MCPServerConnectionCheck {
  template_id: string;
  status: string;
  summary: string;
  checks: string[];
  warnings: string[];
  copy_commands: string[];
  safety_note: string;
}

export interface AgentCapability {
  provider: string;
  model: string;
  display_name: string;
  model_type: string;
  readiness: string;
  planning_supported: boolean;
  tool_calling_supported: boolean;
  json_mode_supported: boolean;
  safe_execution_supported: boolean;
  supported_agent_modes: string[];
  recommended_use: string;
  guardrails: string[];
  evidence: string[];
  limitations: string[];
}

export interface AgentCapabilityCatalog {
  summary: string;
  models: AgentCapability[];
  recommended_models: string[];
  safety_note: string;
  planning_modes: string[];
}

export interface AgentPlanningPreviewRequest {
  goal: string;
  provider?: string | null;
  model?: string | null;
}

export interface AgentPlanStep {
  order: number;
  title: string;
  description: string;
  requires_user_confirmation: boolean;
  allowed_execution: string;
  verification: string;
}

export interface AgentPlanningPreview {
  goal: string;
  selected_provider: string | null;
  selected_model: string | null;
  readiness: string;
  agent_mode: string;
  steps: AgentPlanStep[];
  unsupported_actions: string[];
  guardrails: string[];
  safety_note: string;
}

export interface AgentWorkflowStep {
  id: string;
  order: number;
  title: string;
  description: string;
  status: string;
  allowed_execution: string;
  verification: string;
  requires_user_confirmation: boolean;
  approval_status: string;
  approval_note: string | null;
  proposed_tool: string | null;
  tool_risk: string;
  execution_hint: string | null;
  evidence_hint: string | null;
  approved_at: string | null;
  evidence_status: string;
  evidence_summary: string | null;
  evidence_sources: string[];
  notes: string | null;
  updated_at: string | null;
}

export interface AgentWorkflow {
  id: string;
  workspace_id: string;
  title: string;
  goal: string;
  provider: string | null;
  model: string | null;
  readiness: string;
  agent_mode: string;
  status: string;
  steps: AgentWorkflowStep[];
  completed_steps_count: number;
  total_steps_count: number;
  progress_percent: number;
  approval_required_steps_count: number;
  approved_steps_count: number;
  pending_approval_steps_count: number;
  approval_readiness: string;
  guardrails: string[];
  unsupported_actions: string[];
  safety_note: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  is_archived: boolean;
}

export interface AgentWorkflowList {
  workspace_id: string;
  items: AgentWorkflow[];
  safety_note: string;
}

export interface CreateAgentWorkflowRequest {
  goal: string;
  provider?: string | null;
  model?: string | null;
}

export interface UpdateAgentWorkflowStepRequest {
  status: "todo" | "in_progress" | "done" | "skipped" | "needs_review";
  notes?: string | null;
}

export interface UpdateAgentWorkflowStepApprovalRequest {
  approval_status: "not_required" | "pending" | "approved" | "rejected" | "revoked";
  approval_note?: string | null;
}

export interface UpdateAgentWorkflowStepEvidenceRequest {
  evidence_status: "not_provided" | "provided" | "needs_review" | "verified";
  evidence_summary?: string | null;
  evidence_sources?: string[];
}

export interface AgentWorkflowStepApprovalPreview {
  workflow_id: string;
  step_id: string;
  title: string;
  approval_status: string;
  proposed_tool: string | null;
  tool_risk: string;
  allowed_execution: string;
  requires_user_confirmation: boolean;
  execution_hint: string;
  evidence_hint: string;
  approval_checklist: string[];
  blocked_actions: string[];
  safety_note: string;
}

export interface AgentWorkflowExecutionReadinessStep {
  step_id: string;
  title: string;
  proposed_tool: string | null;
  tool_status: string;
  tool_risk: string;
  approval_status: string;
  evidence_status: string;
  ready_for_manual_execution: boolean;
  blockers: string[];
  next_action: string;
}

export interface AgentWorkflowExecutionReadiness {
  workspace_id: string;
  workflow_id: string;
  status: string;
  approved_tools_count: number;
  risky_tools_count: number;
  ready_steps_count: number;
  blocked_steps_count: number;
  steps: AgentWorkflowExecutionReadinessStep[];
  guardrails: string[];
  safety_note: string;
}

export interface CreateWorkspaceMCPConfigRequest {
  template_id: string;
  project_path?: string | null;
  env_overrides?: Record<string, string>;
}

export interface UpdateWorkspaceMCPConfigRequest {
  enabled?: boolean | null;
  reviewed?: boolean | null;
  approved_tools?: string[] | null;
  denied_tools?: string[] | null;
}

export interface WorkspaceMCPServerConfig {
  id: string;
  workspace_id: string;
  template_id: string;
  name: string;
  category: string;
  transport: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  config_json: Record<string, unknown>;
  risk_level: string;
  scope: string;
  enabled: boolean;
  reviewed: boolean;
  available_tools: string[];
  approved_tools: string[];
  denied_tools: string[];
  guardrails: string[];
  status: string;
  available_tools_count: number;
  approved_tools_count: number;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMCPConfigList {
  workspace_id: string;
  items: WorkspaceMCPServerConfig[];
  safety_note: string;
}

export interface MCPToolInventory {
  workspace_id: string;
  configs_count: number;
  enabled_configs_count: number;
  approved_tools_count: number;
  read_only_tools_count: number;
  write_or_dangerous_tools_count: number;
  tools: Array<Record<string, string>>;
  safety_note: string;
  agent_readiness: string;
}

export interface MCPApprovalPreviewRequest {
  approved_tools: string[];
}

export interface MCPApprovalPreview {
  workspace_id: string;
  config_id: string;
  status: string;
  approved_tools: string[];
  denied_tools: string[];
  warnings: string[];
  guardrails: string[];
  safety_note: string;
}

export interface GuidedModelSetupOption {
  provider: string;
  model: string;
  model_type: "llm" | "embedding" | string;
  display_name: string;
  description: string;
  recommendation_label: string;
  recommended: boolean;
  local_only: boolean;
  quality_tier: string;
  speed_tier: string;
  estimated_size?: string | null;
  fit?: "comfortable" | "works_slower" | "too_big" | string | null;
  fit_label?: string | null;
  notes: string[];
}

export interface GuidedModelSetupSection {
  model_type: "llm" | "embedding" | string;
  title: string;
  purpose: string;
  recommendation_summary: string;
  custom_model_hint: string;
  options: GuidedModelSetupOption[];
}

export interface GuidedModelSetupGuide {
  workspace_id: string;
  title: string;
  summary: string;
  llm: GuidedModelSetupSection;
  embedding: GuidedModelSetupSection;
  packaging_notes: string[];
  safety_notes: string[];
}

export interface OllamaModelRole {
  id: string;
  title: string;
  model_type: string;
  default_model: string;
  purpose: string;
  why_it_matters: string;
}

export interface OllamaHardwareProfile {
  id: string;
  title: string;
  summary: string;
  recommended_llm: string;
  fallback_llm: string;
  recommended_embedding: string;
  notes: string[];
}

export interface OllamaModelRecommendationGuide {
  title: string;
  summary: string;
  default_profile_id: string;
  roles: OllamaModelRole[];
  profiles: OllamaHardwareProfile[];
  catalog_models: LocalModelDefinition[];
  safety_notes: string[];
  next_steps: string[];
}

export interface LocalModelInstallOption {
  provider: string;
  model: string;
  model_type: "llm" | "embedding" | string;
  display_name: string;
  purpose: string;
  estimated_size: string | null;
  recommended: boolean;
  install_command: string;
  verify_command: string;
  notes: string[];
}

export interface LocalModelInstallGuide {
  title: string;
  summary: string;
  status: string;
  options: LocalModelInstallOption[];
  safety_notes: string[];
  next_steps: string[];
}

export interface LocalModelStatusItem {
  provider: string;
  model: string;
  model_type: "llm" | "embedding" | string;
  display_name: string;
  recommended: boolean;
  status: "installed" | "missing" | "unknown" | string;
  detail: string;
  installed_as: string | null;
  size_bytes: number | null;
  modified_at: string | null;
  parameter_size: string | null;
  quantization_level: string | null;
  context_length: number | null;
  embedding_length: number | null;
  capabilities: string[];
  install_command: string;
}

export interface LocalModelInstallStatus {
  title: string;
  summary: string;
  status: string;
  provider: string;
  runtime_reachable: boolean;
  runtime_url: string;
  installed_count: number;
  items: LocalModelStatusItem[];
  safety_notes: string[];
}

export interface LocalModelDownloadWorkerStep {
  id: string;
  title: string;
  description: string;
  status: string;
}

export interface LocalModelDownloadWorkerGuardrail {
  id: string;
  label: string;
  detail: string;
}

export interface LocalModelDownloadWorkerPlan {
  title: string;
  summary: string;
  status: string;
  worker_enabled: boolean;
  execution_mode: string;
  approved_command_pattern: string;
  allowed_provider: string;
  steps: LocalModelDownloadWorkerStep[];
  guardrails: LocalModelDownloadWorkerGuardrail[];
  future_endpoints: string[];
  user_flow: string[];
}

export interface CommandProposal {
  id: string;
  workspace_id: string;
  command: string;
  cwd: string;
  reason: string;
  risk: string;
  status: string;
  created_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  executed_at: string | null;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  policy_allowed: boolean | null;
  policy_mode: string | null;
  policy_reason: string | null;
}

export interface CreateLocalModelInstallDraftRequest {
  workspace_id: string;
  provider: string;
  model: string;
  model_type?: string | null;
}

export interface LocalModelInstallDraft {
  workspace_id: string;
  provider: string;
  model: string;
  model_type: string;
  display_name: string;
  purpose: string;
  estimated_size: string | null;
  command: string;
  status: string;
  safety_summary: string;
  approval_required: boolean;
  execution_supported: boolean;
  next_steps: string[];
  command_proposal: CommandProposal;
}

export interface LocalModelDownloadJob {
  id: string;
  command_id: string;
  workspace_id: string;
  provider: string;
  model: string;
  display_name: string;
  status: string;
  progress_percent: number;
  progress_message: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  command_proposal: CommandProposal;
  stdout_preview: string | null;
  stderr_preview: string | null;
  exit_code: number | null;
  cancel_requested_at: string | null;
  cancellable: boolean;
  cancellation_summary: string;
  safety_summary: string;
  next_steps: string[];
}

export interface LocalModelDownloadJobList {
  jobs: LocalModelDownloadJob[];
  count: number;
  running_count: number;
  summary: string;
}

export interface LocalModelDownloadExecutionCapability {
  title: string;
  status: string;
  execution_enabled: boolean;
  execution_mode: string;
  safety_summary: string;
  requirements: string[];
  disabled_reason: string | null;
}

export interface LocalModelDownloadExecutionResult {
  command_id: string;
  workspace_id: string;
  provider: string;
  model: string;
  display_name: string;
  status: string;
  execution_status: string;
  safety_summary: string;
  command_proposal: CommandProposal;
  next_steps: string[];
}

export interface PyInstallerBackendRuntimeItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  path: string | null;
}

export interface RuntimeSelectionCandidate {
  id: string;
  title: string;
  status: string;
  path: string;
  selection_rule: string;
  fallback_rule: string;
}

export interface FrozenBackendSmokeItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface FrozenBackendStartupDiagnosticsItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface AppOwnedBackendStartupGateItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface AppOwnedBackendStartupImplementationItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string;
  command: string | null;
}

export interface AppOwnedBackendHealthReadinessItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string;
  command: string | null;
}

export interface MacOSTauriSmokeRunbookItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface MacOSPackagedAppSmokePreflightItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface TauriPackagedAppBuildItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface MacOSPackagedAppSmokeResultItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string | null;
  command: string | null;
}

export interface PackagedAppFrontendBootstrapItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  evidence: string | null;
  command: string | null;
}

export interface TauriRustStructureRegistryItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface TauriRustDependencyPinItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  command: string | null;
}

export interface StagedBackendRuntimeItem {
  id: string;
  title: string;
  status: string;
  summary: string;
  path: string | null;
}

// --- Project Intelligence (M1) ---

export interface ProjectIntelligenceSnapshot {
  id: string;
  workspace_id: string;
  created_at: string;
  entity_count: number;
  relation_count: number;
  finding_count: number;
  analyzers_run: string[];
  analyzers_skipped: string[];
  scan_signature: string | null;
}

export interface ProjectGraphEntity {
  id: string;
  type: string;
  name: string;
  status: string;
  confidence: string;
  source_file: string | null;
  analyzer: string;
  metadata: Record<string, string>;
}

export interface ProjectGraphPipeline extends ProjectGraphEntity {
  jobs: ProjectGraphEntity[];
}

export interface ProjectGraphFinding {
  id: string;
  category: string;
  severity: string;
  title: string;
  explanation: string;
  source_file: string | null;
  evidence: string[];
  confidence: string;
  recommendation: string | null;
  analyzer: string;
}

export interface ProjectIntelligenceQuestion {
  question: string;
  reason: string;
}

export interface ProjectIntelligenceView {
  role: string;
  role_label: string;
  section_order: string[];
  analyzers_run: string[];
  analyzers_skipped: string[];
  summary: {
    description: string;
    technology_chips: string[];
    counts: {
      services: number;
      environments: number;
      pipelines: number;
      infrastructure: number;
    };
  };
  infrastructure: { components: ProjectGraphEntity[]; images: ProjectGraphEntity[] };
  deployment: { pipelines: ProjectGraphPipeline[] };
  environments: { environments: ProjectGraphEntity[] };
  risks: { findings: ProjectGraphFinding[]; highlighted_categories: string[] };
  important_files: { files: { path: string; reason: string }[] };
  questions: { questions: ProjectIntelligenceQuestion[] };
}

export interface ProjectGraphNode {
  id: string;
  type: string;
  name: string;
  status: string;
  confidence: string;
  analyzer: string;
  source_file: string | null;
}

export interface ProjectGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export interface ProjectGraphPayload {
  nodes: ProjectGraphNode[];
  edges: ProjectGraphEdge[];
}

export interface ProjectDeploymentStage {
  key: string;
  label: string;
  count: number;
  detail: string;
}

export interface ProjectFlowGap {
  title: string;
  explanation: string;
}

export interface ProjectDeploymentFlow {
  stages: ProjectDeploymentStage[];
  gaps: ProjectFlowGap[];
}

export interface ProjectEnvironmentRow {
  name: string;
  analyzer: string;
  status: string;
  confidence: string;
  source_file: string | null;
  evidence_count: number;
}

export interface ProjectEnvironmentComparison {
  environments: ProjectEnvironmentRow[];
  summary: string;
  has_production: boolean;
}

export interface ProjectCloudService {
  service: string;
  resources: number;
  source_file: string | null;
}

export interface ProjectCloudProvider {
  provider: string;
  services: ProjectCloudService[];
  service_count: number;
}

export interface ProjectCloud {
  providers: ProjectCloudProvider[];
  total_services: number;
}

export interface ProjectReferenceItem {
  value: string;
  count: number;
  source_file: string | null;
}

export interface ProjectReferenceGroup {
  kind: string;
  items: ProjectReferenceItem[];
}

export interface ProjectReferences {
  groups: ProjectReferenceGroup[];
  total: number;
}

export interface ProjectCiWorkflow {
  name: string;
  jobs: string[];
  source_file: string | null;
  cron?: string[];
}

export interface ProjectCiScenario {
  key: string;
  label: string;
  workflows: ProjectCiWorkflow[];
}

export interface ProjectCi {
  has_data: boolean;
  scenarios: ProjectCiScenario[];
}

export interface ProjectIntelligenceResponse {
  built: boolean;
  role?: string;
  snapshot?: ProjectIntelligenceSnapshot;
  view?: ProjectIntelligenceView;
  graph?: ProjectGraphPayload;
  flow?: ProjectDeploymentFlow;
  environment_comparison?: ProjectEnvironmentComparison;
  cloud?: ProjectCloud;
  references?: ProjectReferences;
  ci?: ProjectCi;
}

export interface ProjectIntelligenceAnswer {
  answer: string;
  role: string;
}

export interface ProjectWatchHighlight {
  kind: string;
  text: string;
  severity?: string;
  entity_type?: string;
  source_file?: string | null;
}

export interface ProjectWatchDigest {
  baseline: boolean;
  has_changes: boolean;
  checked_at: string;
  previous_checked_at: string | null;
  summary: string;
  highlights: ProjectWatchHighlight[];
  counts: {
    entities_added: number;
    entities_removed: number;
    findings_added: number;
    findings_resolved: number;
  };
}

export interface ProjectWatchResponse {
  has_digest: boolean;
  digest?: ProjectWatchDigest;
}

export interface InvestigationStep {
  thought: string;
  tool: string;
  tool_input: string;
  observation: string;
}

export interface InvestigationResponse {
  answer: string;
  steps: InvestigationStep[];
  sources: string[];
  used_steps: number;
  stopped_reason: string;
  context_used?: { memory: number; facts: number };
}

export interface ProjectMemoryItem {
  id: string;
  kind: string;
  text: string;
  source: string;
  created_at: string;
  pinned: boolean;
}

export interface ProjectMemoryList {
  items: ProjectMemoryItem[];
}

export interface ProjectHandbookResponse {
  has_handbook: boolean;
  handbook?: string;
  created_at?: string;
}

export interface ProjectIntelligenceBuildResponse {
  built: boolean;
  snapshot: ProjectIntelligenceSnapshot;
}

export interface ProjectIntelligenceOverviewText {
  overview: string;
  role: string;
}

// --- Project groups (treat several repos as one project) ---

export interface ProjectGroupSummary {
  id: string;
  name: string;
  created_at: string;
  member_count: number;
  workspace_ids: string[];
}

export interface GroupMemberRef {
  workspace_id: string;
  name: string;
  project_path: string;
}

export interface ProjectGroupDetail extends ProjectGroupSummary {
  members: GroupMemberRef[];
}

export interface ProjectGroupListResponse {
  groups: ProjectGroupSummary[];
}

export interface GroupMemberRisk {
  workspace_id: string;
  workspace_name: string;
  severity: string;
  title: string;
}

export interface GroupMemberOverview {
  workspace_id: string;
  name: string;
  project_path: string;
  built: boolean;
  indexed: boolean;
  description: string;
  technology_chips: string[];
  counts: Record<string, number>;
  environments: string[];
  risk_counts: Record<string, number>;
  is_repo: boolean;
  branch: string | null;
  total_commits: number;
  contributors_count: number;
  commits_last_7_days: number;
  last_commit_subject: string | null;
}

export interface GroupOverviewResponse {
  group_id: string;
  name: string;
  member_count: number;
  totals: Record<string, number>;
  environments: string[];
  technologies: string[];
  risks: GroupMemberRisk[];
  members: GroupMemberOverview[];
}

export interface GroupAskSource {
  workspace_id: string;
  workspace_name: string;
  chunk_id: string;
  source_path: string;
  score: number;
  preview: string;
}

export interface GroupAskContribution {
  workspace_id: string;
  workspace_name: string;
  indexed: boolean;
  chunks_used: number;
}

export interface GroupAskResponse {
  group_id: string;
  question: string;
  answer: string;
  sources: GroupAskSource[];
  contributions: GroupAskContribution[];
  used_context_chunks: number;
  llm_provider: string;
  llm_model: string | null;
  memory_used: number;
  facts_used: number;
  diagnostic_code: string | null;
}

export interface GroupMemoryItem {
  id: string;
  kind: string;
  text: string;
  source: string;
  created_at: string;
  pinned: boolean;
}

export interface GroupMemoryListResponse {
  items: GroupMemoryItem[];
}

export interface GroupHandbookResponse {
  has_handbook: boolean;
  handbook?: string;
  created_at?: string;
}

// --- Answer ratings & nudges ---

export interface AnswerRatingNudge {
  kind: "model" | "retrieval" | string;
  title: string;
  detail: string;
  action: "open_models" | "rebuild_context" | string;
}

export interface AnswerRatingNudgesResponse {
  nudges: AnswerRatingNudge[];
}
