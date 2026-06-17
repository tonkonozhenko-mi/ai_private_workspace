import type {
  LocalAIActivationGuide,
  ModelExperimentPlan,
  ModelExperimentPlanRequest,
  ModelExperimentRating,
  ModelExperimentRatingRequest,
  ModelExperimentRun,
  CreateWorkspaceRequest,
  CreatedWorkspace,
  WorkspaceFileWriteResult,
  GgufCatalogItem,
  GgufDownloadJob,
  LlamaRuntimeStatus,
  GitInsightsResponse,
  ProjectScanResponse,
  ProjectTodosResponse,
  ProjectUnderstandingResponse,
  ScanChanges,
  FileSelectionPreview,
  FileSelectionRulesRequest,
  WorkspaceIndexingRules,
  WorkspaceDashboard,
  WorkspaceIndexResponse,
  WorkspaceJob,
  WorkspaceModelsDashboard,
  UpdateWorkspaceModelSelectionRequest,
  WorkspaceModelSelection,
  WorkspaceModelsDashboardSummary,
  WorkspaceQuestionAnswer,
  ConversationAnswerNote,
  ConversationContextPreview,
  ConversationExport,
  WorkspaceConversation,
  SkillContextRequest,
  WorkspaceSkillProfile,
  WorkspaceSkillProfileRequest,
  WorkspaceUIActionCatalog,
  WorkspacesOverview,
  WorkspaceStorage,
  PurgeTemporaryResult,
  ReportCatalog,
  WorkspaceReport,
  BuildCustomWorkspaceReportRequest,
  SaveEditedWorkspaceReportRequest,
  SavedWorkspaceReport,
  UpdateSavedWorkspaceReportRequest,
  CreateDatabaseBackupResponse,
  DatabaseBackupList,
  DatabaseMigrationSafety,
  DatabaseRestorePlan,
  LocalDataSafety,
  RuntimeMemory,
  StartupChecklist,
  RuntimeTroubleshooting,
  SafeUpdateWorkflow,
  DesktopStartupExperience,
  DesktopPackagingDesign,
  MacOSAppPackageFoundation,
  DesktopSupervisorContract,
  MacOSAppSupervisorWiring,
  BackendRuntimeBundlePlan,
  DesktopRuntimeReadiness,
  DesktopRuntimePreflight,
  TauriShellScaffold,
  TauriSupervisorBridge,
  TauriSupervisorStaticGate,
  DesktopTechnologyDecision,
  DesktopStackAndRuntimeContract,
  StagedBackendRuntimeContract,
  PyInstallerBackendRuntimeContract,
  FrozenBackendRuntimeSelection,
  FrozenBackendSmokeContract,
  FrozenBackendStartupDiagnostics,
  AppOwnedBackendStartupGate,
  AppOwnedBackendStartupImplementation,
  AppOwnedBackendHealthReadiness,
  MacOSTauriSmokeRunbook,
  MacOSPackagedAppSmokePreflight,
  TauriPackagedAppBuildReadiness,
  MacOSPackagedAppSmokeResult,
  PackagedAppFrontendBootstrap,
  TauriRustStructureRegistry,
  TauriRustDependencyPins,
  WindowsPackagingFoundation,
  ReleaseCandidateAudit,
  V01Handoff,
  V01ReleaseGate,
  V01UISmokeCheck,
  V01PublicationHandoff,
  FinalProductStatus,
  FirstLaunchReadiness,
  ProductionReadiness,
  AgentCapabilityCatalog,
  AgentPlanningPreview,
  AgentPlanningPreviewRequest,
  AgentWorkflow,
  AgentWorkflowList,
  AgentWorkflowExecutionReadiness,
  AgentWorkflowStepApprovalPreview,
  CreateAgentWorkflowRequest,
  UpdateAgentWorkflowStepApprovalRequest,
  UpdateAgentWorkflowStepEvidenceRequest,
  UpdateAgentWorkflowStepRequest,
  MCPServerCatalog,
  MCPConfigPreviewRequest,
  MCPServerConfigPreview,
  MCPConnectionCheckRequest,
  MCPServerConnectionCheck,
  CreateWorkspaceMCPConfigRequest,
  UpdateWorkspaceMCPConfigRequest,
  WorkspaceMCPConfigList,
  WorkspaceMCPServerConfig,
  MCPToolInventory,
  MCPApprovalPreviewRequest,
  MCPApprovalPreview,
  GuidedModelSetupGuide,
  CreateLocalModelInstallDraftRequest,
  LocalModelInstallDraft,
  LocalModelInstallGuide,
  OllamaModelRecommendationGuide,
  LocalModelInstallStatus,
  LocalModelDownloadWorkerPlan,
  LocalModelDownloadExecutionCapability,
  LocalModelDownloadExecutionResult,
  LocalModelDownloadJob,
  LocalModelDownloadJobList,
} from "./types";

export const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

let apiBaseUrl = DEFAULT_API_BASE_URL;

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

export function setApiBaseUrl(nextBaseUrl: string): void {
  apiBaseUrl = nextBaseUrl.replace(/\/+$/, "");
}

async function getJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  return requestJson<T>(path, {
    ...init,
    headers: {
      Accept: "application/json",
    },
  });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  await assertOk(response);

  return (await response.json()) as T;
}

async function requestWithoutBody(path: string, init: RequestInit): Promise<void> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  await assertOk(response);
}

async function assertOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }

  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // Preserve the HTTP status when the backend did not return JSON.
  }
  throw new Error(detail);
}

export function getLocalDataSafety(): Promise<LocalDataSafety> {
  return getJson<LocalDataSafety>("/runtime/local-data");
}

export function getRuntimeMemory(): Promise<RuntimeMemory> {
  return getJson<RuntimeMemory>("/models/runtime-memory");
}

export function getStartupChecklist(): Promise<StartupChecklist> {
  return getJson<StartupChecklist>("/runtime/startup-checklist");
}

export function getRuntimeTroubleshooting(): Promise<RuntimeTroubleshooting> {
  return getJson<RuntimeTroubleshooting>("/runtime/troubleshooting");
}

export function getSafeUpdateWorkflow(): Promise<SafeUpdateWorkflow> {
  return getJson<SafeUpdateWorkflow>("/runtime/update-safety");
}

export function getDesktopStartupExperience(): Promise<DesktopStartupExperience> {
  return getJson<DesktopStartupExperience>("/runtime/desktop-startup");
}

export function getProductionReadiness(): Promise<ProductionReadiness> {
  return getJson<ProductionReadiness>("/runtime/production-readiness");
}

export function getDesktopPackagingDesign(): Promise<DesktopPackagingDesign> {
  return getJson<DesktopPackagingDesign>("/runtime/desktop-packaging-design");
}

export function getMacOSAppPackageFoundation(): Promise<MacOSAppPackageFoundation> {
  return getJson<MacOSAppPackageFoundation>("/runtime/macos-app-package-foundation");
}

export function getDesktopSupervisorContract(): Promise<DesktopSupervisorContract> {
  return getJson<DesktopSupervisorContract>("/runtime/desktop-supervisor-contract");
}

export function getMacOSAppSupervisorWiring(): Promise<MacOSAppSupervisorWiring> {
  return getJson<MacOSAppSupervisorWiring>("/runtime/macos-app-supervisor-wiring");
}

export function getBackendRuntimeBundlePlan(): Promise<BackendRuntimeBundlePlan> {
  return getJson<BackendRuntimeBundlePlan>("/runtime/backend-runtime-bundle-plan");
}

export function getDesktopRuntimeReadiness(): Promise<DesktopRuntimeReadiness> {
  return getJson<DesktopRuntimeReadiness>("/runtime/desktop-runtime-readiness");
}

export function getDesktopRuntimePreflight(): Promise<DesktopRuntimePreflight> {
  return getJson<DesktopRuntimePreflight>("/runtime/desktop-runtime-preflight");
}

export function getTauriShellScaffold(): Promise<TauriShellScaffold> {
  return getJson<TauriShellScaffold>("/runtime/tauri-shell-scaffold");
}

export function getTauriSupervisorBridge(): Promise<TauriSupervisorBridge> {
  return getJson<TauriSupervisorBridge>("/runtime/tauri-supervisor-bridge");
}

export function getTauriSupervisorStaticGate(): Promise<TauriSupervisorStaticGate> {
  return getJson<TauriSupervisorStaticGate>("/runtime/tauri-supervisor-static-gate");
}

export function getDesktopTechnologyDecision(): Promise<DesktopTechnologyDecision> {
  return getJson<DesktopTechnologyDecision>("/runtime/desktop-technology-decision");
}

export function getDesktopStackAndRuntimeContract(): Promise<DesktopStackAndRuntimeContract> {
  return getJson<DesktopStackAndRuntimeContract>("/runtime/desktop-stack-runtime-contract");
}

export function getStagedBackendRuntimeContract(): Promise<StagedBackendRuntimeContract> {
  return getJson<StagedBackendRuntimeContract>("/runtime/staged-backend-runtime-contract");
}

export function getPyInstallerBackendRuntimeContract(): Promise<PyInstallerBackendRuntimeContract> {
  return getJson<PyInstallerBackendRuntimeContract>("/runtime/pyinstaller-backend-runtime-contract");
}

export function getFrozenBackendRuntimeSelection(): Promise<FrozenBackendRuntimeSelection> {
  return getJson<FrozenBackendRuntimeSelection>("/runtime/frozen-backend-runtime-selection");
}

export function getFrozenBackendSmokeContract(): Promise<FrozenBackendSmokeContract> {
  return getJson<FrozenBackendSmokeContract>("/runtime/frozen-backend-smoke-contract");
}

export function getFrozenBackendStartupDiagnostics(): Promise<FrozenBackendStartupDiagnostics> {
  return getJson<FrozenBackendStartupDiagnostics>("/runtime/frozen-backend-startup-diagnostics");
}

export function getAppOwnedBackendStartupGate(): Promise<AppOwnedBackendStartupGate> {
  return getJson<AppOwnedBackendStartupGate>("/runtime/app-owned-backend-startup-gate");
}

export function getAppOwnedBackendStartupImplementation(): Promise<AppOwnedBackendStartupImplementation> {
  return getJson<AppOwnedBackendStartupImplementation>("/runtime/app-owned-backend-startup-implementation");
}

export function getAppOwnedBackendHealthReadiness(): Promise<AppOwnedBackendHealthReadiness> {
  return getJson<AppOwnedBackendHealthReadiness>("/runtime/app-owned-backend-health-readiness");
}

export function getMacOSTauriSmokeRunbook(): Promise<MacOSTauriSmokeRunbook> {
  return getJson<MacOSTauriSmokeRunbook>("/runtime/macos-tauri-smoke-runbook");
}

export function getMacOSPackagedAppSmokePreflight(): Promise<MacOSPackagedAppSmokePreflight> {
  return getJson<MacOSPackagedAppSmokePreflight>("/runtime/macos-packaged-app-smoke-preflight");
}


export function getTauriPackagedAppBuildReadiness(): Promise<TauriPackagedAppBuildReadiness> {
  return getJson<TauriPackagedAppBuildReadiness>("/runtime/tauri-packaged-app-build-readiness");
}

export function getMacOSPackagedAppSmokeResult(): Promise<MacOSPackagedAppSmokeResult> {
  return getJson<MacOSPackagedAppSmokeResult>("/runtime/macos-packaged-app-smoke-result");
}

export function getPackagedAppFrontendBootstrap(): Promise<PackagedAppFrontendBootstrap> {
  return getJson<PackagedAppFrontendBootstrap>("/runtime/packaged-app-frontend-bootstrap");
}

export function getTauriRustStructureRegistry(): Promise<TauriRustStructureRegistry> {
  return getJson<TauriRustStructureRegistry>("/runtime/tauri-rust-structure-registry");
}

export function getTauriRustDependencyPins(): Promise<TauriRustDependencyPins> {
  return getJson<TauriRustDependencyPins>("/runtime/tauri-rust-dependency-pins");
}

export function getWindowsPackagingFoundation(): Promise<WindowsPackagingFoundation> {
  return getJson<WindowsPackagingFoundation>("/runtime/windows-packaging-foundation");
}

export function getReleaseCandidateAudit(): Promise<ReleaseCandidateAudit> {
  return getJson<ReleaseCandidateAudit>("/runtime/release-candidate-audit");
}

export function getV01Handoff(): Promise<V01Handoff> {
  return getJson<V01Handoff>("/runtime/v0.1-handoff");
}

export function getV01ReleaseGate(): Promise<V01ReleaseGate> {
  return getJson<V01ReleaseGate>("/runtime/v0.1-release-gate");
}

export function getV01UISmokeCheck(): Promise<V01UISmokeCheck> {
  return getJson<V01UISmokeCheck>("/runtime/v0.1-ui-smoke-check");
}

export function getV01PublicationHandoff(): Promise<V01PublicationHandoff> {
  return getJson<V01PublicationHandoff>("/runtime/v0.1-publication-handoff");
}

export function getFinalProductStatus(): Promise<FinalProductStatus> {
  return getJson<FinalProductStatus>("/runtime/final-product-status");
}

export function getFirstLaunchReadiness(): Promise<FirstLaunchReadiness> {
  return getJson<FirstLaunchReadiness>("/runtime/first-launch-readiness");
}


export function getDatabaseBackups(): Promise<DatabaseBackupList> {
  return getJson<DatabaseBackupList>("/runtime/database-backups");
}

export function createDatabaseBackup(): Promise<CreateDatabaseBackupResponse> {
  return requestJson<CreateDatabaseBackupResponse>("/runtime/database-backups", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getDatabaseRestorePlan(backupFilename: string): Promise<DatabaseRestorePlan> {
  return requestJson<DatabaseRestorePlan>("/runtime/database-restore-plan", {
    method: "POST",
    body: JSON.stringify({ backup_filename: backupFilename }),
  });
}

export function getDatabaseMigrationSafety(): Promise<DatabaseMigrationSafety> {
  return getJson<DatabaseMigrationSafety>("/runtime/database-migration-safety");
}

export function getWorkspacesOverview(
  options: { includeArchived?: boolean } = {},
): Promise<WorkspacesOverview> {
  const query = options.includeArchived ? "?include_archived=true" : "";
  return getJson<WorkspacesOverview>(`/workspaces/overview${query}`);
}

export function createWorkspace(
  request: CreateWorkspaceRequest,
): Promise<CreatedWorkspace> {
  return requestJson<CreatedWorkspace>("/workspaces", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function writeWorkspaceFile(
  workspaceId: string,
  request: { relative_path: string; content: string; overwrite: boolean },
): Promise<WorkspaceFileWriteResult> {
  return requestJson<WorkspaceFileWriteResult>(
    `/workspaces/${workspaceId}/files/write`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export function archiveWorkspace(workspaceId: string): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/archive`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}

export function restoreWorkspace(workspaceId: string): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/restore`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}

export function deleteWorkspace(workspaceId: string): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });
}

export function clearWorkspaceIndex(
  workspaceId: string,
): Promise<WorkspaceStorage> {
  return requestJson<WorkspaceStorage>(`/workspaces/${workspaceId}/index/clear`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}

export function getWorkspaceStorage(
  workspaceId: string,
  options: { recompute?: boolean } = {},
): Promise<WorkspaceStorage> {
  const query = options.recompute ? "?recompute=true" : "";
  return getJson<WorkspaceStorage>(`/workspaces/${workspaceId}/storage${query}`);
}

export function setWorkspacePersistence(
  workspaceId: string,
  persistence: "saved" | "temporary",
): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/persistence`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ persistence }),
  });
}

export function purgeTemporaryWorkspaces(): Promise<PurgeTemporaryResult> {
  return requestJson<PurgeTemporaryResult>("/workspaces/temporary/purge", {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}


export function getWorkspaceSkillProfile(
  workspaceId: string,
): Promise<WorkspaceSkillProfile> {
  return getJson<WorkspaceSkillProfile>(`/workspaces/${workspaceId}/skill-profile`);
}

export function updateWorkspaceSkillProfile(
  workspaceId: string,
  profile: WorkspaceSkillProfileRequest,
): Promise<WorkspaceSkillProfile> {
  return requestJson<WorkspaceSkillProfile>(`/workspaces/${workspaceId}/skill-profile`, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profile),
  });
}


export function getWorkspaceIndexingRules(
  workspaceId: string,
): Promise<WorkspaceIndexingRules> {
  return getJson<WorkspaceIndexingRules>(`/workspaces/${workspaceId}/indexing-rules`);
}

export function updateWorkspaceIndexingRules(
  workspaceId: string,
  fileRules: FileSelectionRulesRequest,
): Promise<WorkspaceIndexingRules> {
  return requestJson<WorkspaceIndexingRules>(`/workspaces/${workspaceId}/indexing-rules`, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(fileRules),
  });
}

export function previewWorkspaceFileSelection(
  workspaceId: string,
  fileRules?: FileSelectionRulesRequest,
): Promise<FileSelectionPreview> {
  return requestJson<FileSelectionPreview>(`/workspaces/${workspaceId}/files/preview`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(fileRules ? { "Content-Type": "application/json" } : {}),
    },
    ...(fileRules ? { body: JSON.stringify({ file_rules: fileRules }) } : {}),
  });
}

export function scanWorkspace(
  workspaceId: string,
  fileRules?: FileSelectionRulesRequest,
  options: { signal?: AbortSignal } = {},
): Promise<ProjectScanResponse> {
  return requestJson<ProjectScanResponse>(`/workspaces/${workspaceId}/scan`, {
    signal: options.signal,
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(fileRules ? { "Content-Type": "application/json" } : {}),
    },
    ...(fileRules ? { body: JSON.stringify({ file_rules: fileRules }) } : {}),
  });
}

// Read-only fetch of the latest scan result (detected skills + files) without
// re-scanning. Used by the project-understanding home screen.
export function getWorkspaceLatestScan(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<ProjectScanResponse> {
  return requestJson<ProjectScanResponse>(`/workspaces/${workspaceId}/scan`, {
    signal: options.signal,
    method: "GET",
    headers: { Accept: "application/json" },
  });
}

// Read-only check: have project files on disk changed since the last scan?
export function getWorkspaceScanChanges(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<ScanChanges> {
  return requestJson<ScanChanges>(`/workspaces/${workspaceId}/scan/changes`, {
    signal: options.signal,
    method: "GET",
    headers: { Accept: "application/json" },
  });
}

// --- llama.cpp (Ollama-free) GGUF model catalog + downloads ---
export function getGgufCatalog(
  modelType?: "llm" | "embedding",
): Promise<GgufCatalogItem[]> {
  const query = modelType ? `?model_type=${modelType}` : "";
  return getJson<GgufCatalogItem[]>(`/models/gguf-catalog${query}`);
}

export function startGgufDownload(body: {
  model_id?: string;
  repo_id?: string;
  filename?: string;
}): Promise<GgufDownloadJob> {
  return requestJson<GgufDownloadJob>(`/models/gguf-downloads`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
}

export function getGgufDownload(jobId: string): Promise<GgufDownloadJob> {
  return getJson<GgufDownloadJob>(`/models/gguf-downloads/${jobId}`);
}

export function cancelGgufDownload(jobId: string): Promise<GgufDownloadJob> {
  return requestJson<GgufDownloadJob>(`/models/gguf-downloads/${jobId}/cancel`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
}

export function getLlamaRuntimeStatus(): Promise<LlamaRuntimeStatus> {
  return getJson<LlamaRuntimeStatus>(`/models/llama-runtime/status`);
}

export function startLlamaRuntime(): Promise<LlamaRuntimeStatus> {
  return requestJson<LlamaRuntimeStatus>(`/models/llama-runtime/start`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
}

export function stopLlamaRuntime(): Promise<LlamaRuntimeStatus> {
  return requestJson<LlamaRuntimeStatus>(`/models/llama-runtime/stop`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
}

// Switch the built-in engine's answer model to another already-downloaded GGUF
// — by catalog id, or by a custom Hugging Face repo + filename.
export function switchLlamaRuntimeLlm(
  ref: { model_id?: string; repo_id?: string; filename?: string },
): Promise<LlamaRuntimeStatus> {
  return requestJson<LlamaRuntimeStatus>(`/models/llama-runtime/llm`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(ref),
  });
}

// Auto-pick a usable GGUF filename from a Hugging Face repo (so the user only
// needs to paste the repo id, like llama.cpp's -hf shorthand).
export function resolveGgufModel(
  repoId: string,
  quant?: string,
): Promise<{ repo_id: string; filename: string; name: string }> {
  return requestJson<{ repo_id: string; filename: string; name: string }>(
    `/models/gguf-resolve`,
    {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, quant: quant || null }),
    },
  );
}

// Delete a downloaded GGUF model file (catalog id or custom repo/filename).
export function deleteGgufModel(
  ref: { model_id?: string; repo_id?: string; filename?: string },
): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/models/gguf-delete`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(ref),
  });
}

// Re-activate the engine a workspace uses (active backend is app-global). Call
// when opening a workspace so its embeddings/answers run on the right engine.
export function activateWorkspaceRuntime(
  workspaceId: string,
): Promise<{ active_backend: string }> {
  return requestJson<{ active_backend: string }>(
    `/models/workspace-runtime/${encodeURIComponent(workspaceId)}`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
}

// Switch the app-wide embedding engine (Ollama vs llama.cpp) so search matches
// the chosen backend. Index after switching to keep vectors consistent.
export function setActiveBackend(backend: "ollama" | "llamacpp"): Promise<{ active_backend: string }> {
  return requestJson<{ active_backend: string }>(`/models/active-backend`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ backend }),
  });
}

// Read-only git history snapshot for the project folder. Returns is_repo=false
// when the folder is not a git repo or git is unavailable.
export function getWorkspaceGitInsights(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<GitInsightsResponse> {
  return requestJson<GitInsightsResponse>(`/workspaces/${workspaceId}/git-insights`, {
    signal: options.signal,
    method: "GET",
    headers: { Accept: "application/json" },
  });
}

// Deterministic TODO/FIXME inventory read directly from project files.
export function getWorkspaceTodos(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<ProjectTodosResponse> {
  return requestJson<ProjectTodosResponse>(`/workspaces/${workspaceId}/todos`, {
    signal: options.signal,
    method: "GET",
    headers: { Accept: "application/json" },
  });
}

// Project understanding (deep analysis). GET returns the cached result (404 if
// none yet); POST generates a fresh one with the workspace's selected LLM.
export function getProjectUnderstanding(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<ProjectUnderstandingResponse> {
  return requestJson<ProjectUnderstandingResponse>(`/workspaces/${workspaceId}/understanding`, {
    signal: options.signal,
    method: "GET",
    headers: { Accept: "application/json" },
  });
}

export function generateProjectUnderstanding(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<ProjectUnderstandingResponse> {
  return requestJson<ProjectUnderstandingResponse>(`/workspaces/${workspaceId}/understanding`, {
    signal: options.signal,
    method: "POST",
    headers: { Accept: "application/json" },
  });
}

export function indexWorkspace(
  workspaceId: string,
  options: { signal?: AbortSignal } = {},
): Promise<WorkspaceIndexResponse> {
  return requestJson<WorkspaceIndexResponse>(`/workspaces/${workspaceId}/index`, {
    signal: options.signal,
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}


export function startScanWorkspaceJob(
  workspaceId: string,
  fileRules?: FileSelectionRulesRequest,
): Promise<WorkspaceJob> {
  return requestJson<WorkspaceJob>(`/workspaces/${workspaceId}/jobs/scan`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(fileRules ? { "Content-Type": "application/json" } : {}),
    },
    ...(fileRules ? { body: JSON.stringify({ file_rules: fileRules }) } : {}),
  });
}

export function startIndexWorkspaceJob(workspaceId: string): Promise<WorkspaceJob> {
  return requestJson<WorkspaceJob>(`/workspaces/${workspaceId}/jobs/index`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}


export function listWorkspaceJobs(workspaceId: string): Promise<WorkspaceJob[]> {
  return getJson<WorkspaceJob[]>(`/workspaces/${workspaceId}/jobs`);
}

export function getWorkspaceJob(
  workspaceId: string,
  jobId: string,
): Promise<WorkspaceJob> {
  return getJson<WorkspaceJob>(`/workspaces/${workspaceId}/jobs/${jobId}`);
}

export function cancelWorkspaceJob(
  workspaceId: string,
  jobId: string,
): Promise<WorkspaceJob> {
  return requestJson<WorkspaceJob>(`/workspaces/${workspaceId}/jobs/${jobId}/cancel`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });
}

export function getWorkspaceDashboard(
  workspaceId: string,
): Promise<WorkspaceDashboard> {
  return getJson<WorkspaceDashboard>(`/workspaces/${workspaceId}/dashboard`);
}

export function getWorkspaceUIActions(
  workspaceId: string,
): Promise<WorkspaceUIActionCatalog> {
  return getJson<WorkspaceUIActionCatalog>(
    `/workspaces/${workspaceId}/ui-actions`,
  );
}


export function getWorkspaceReportCatalog(
  workspaceId: string,
): Promise<ReportCatalog> {
  return getJson<ReportCatalog>(`/workspaces/${workspaceId}/reports/catalog`);
}

export function generateWorkspaceReport(
  workspaceId: string,
  reportType: string,
): Promise<WorkspaceReport> {
  return getJson<WorkspaceReport>(`/workspaces/${workspaceId}/reports/${reportType}`);
}



export function buildCustomWorkspaceReport(
  workspaceId: string,
  request: BuildCustomWorkspaceReportRequest,
): Promise<WorkspaceReport> {
  return requestJson<WorkspaceReport>(`/workspaces/${workspaceId}/reports/custom-preview`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function saveCustomWorkspaceReport(
  workspaceId: string,
  request: BuildCustomWorkspaceReportRequest,
): Promise<SavedWorkspaceReport> {
  return requestJson<SavedWorkspaceReport>(`/workspaces/${workspaceId}/reports/custom-save`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}


export function saveEditedWorkspaceReport(
  workspaceId: string,
  request: SaveEditedWorkspaceReportRequest,
): Promise<SavedWorkspaceReport> {
  return requestJson<SavedWorkspaceReport>(`/workspaces/${workspaceId}/reports/draft-save`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function saveWorkspaceReport(
  workspaceId: string,
  reportType: string,
): Promise<SavedWorkspaceReport> {
  return requestJson<SavedWorkspaceReport>(`/workspaces/${workspaceId}/reports/${reportType}/save`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
}

export function listSavedWorkspaceReports(
  workspaceId: string,
  options: { search?: string; reportType?: string; pinnedOnly?: boolean } = {},
): Promise<SavedWorkspaceReport[]> {
  const params = new URLSearchParams();
  if (options.search?.trim()) params.set("search", options.search.trim());
  if (options.reportType?.trim()) params.set("report_type", options.reportType.trim());
  if (options.pinnedOnly) params.set("pinned_only", "true");
  const query = params.toString();
  return getJson<SavedWorkspaceReport[]>(`/workspaces/${workspaceId}/reports/saved${query ? `?${query}` : ""}`);
}

export function updateSavedWorkspaceReport(
  workspaceId: string,
  reportId: string,
  request: UpdateSavedWorkspaceReportRequest,
): Promise<SavedWorkspaceReport> {
  return requestJson<SavedWorkspaceReport>(`/workspaces/${workspaceId}/reports/saved/${reportId}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function pinSavedWorkspaceReport(
  workspaceId: string,
  reportId: string,
  pinned: boolean,
): Promise<SavedWorkspaceReport> {
  return requestJson<SavedWorkspaceReport>(`/workspaces/${workspaceId}/reports/saved/${reportId}/pin`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ pinned }),
  });
}

export function deleteSavedWorkspaceReport(workspaceId: string, reportId: string): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/reports/saved/${reportId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}




export function listAgentWorkflows(
  workspaceId: string,
  options: { includeArchived?: boolean } = {},
): Promise<AgentWorkflowList> {
  const query = options.includeArchived ? "?include_archived=true" : "";
  return getJson<AgentWorkflowList>(`/workspaces/${workspaceId}/agent-workflows${query}`);
}

export function createAgentWorkflow(
  workspaceId: string,
  request: CreateAgentWorkflowRequest,
): Promise<AgentWorkflow> {
  return requestJson<AgentWorkflow>(`/workspaces/${workspaceId}/agent-workflows`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function updateAgentWorkflowStep(
  workspaceId: string,
  workflowId: string,
  stepId: string,
  request: UpdateAgentWorkflowStepRequest,
): Promise<AgentWorkflow> {
  return requestJson<AgentWorkflow>(
    `/workspaces/${workspaceId}/agent-workflows/${workflowId}/steps/${stepId}`,
    {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export function previewAgentWorkflowStepApproval(
  workspaceId: string,
  workflowId: string,
  stepId: string,
): Promise<AgentWorkflowStepApprovalPreview> {
  return requestJson<AgentWorkflowStepApprovalPreview>(
    `/workspaces/${workspaceId}/agent-workflows/${workflowId}/steps/${stepId}/approval-preview`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
}

export function updateAgentWorkflowStepApproval(
  workspaceId: string,
  workflowId: string,
  stepId: string,
  request: UpdateAgentWorkflowStepApprovalRequest,
): Promise<AgentWorkflow> {
  return requestJson<AgentWorkflow>(
    `/workspaces/${workspaceId}/agent-workflows/${workflowId}/steps/${stepId}/approval`,
    {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}


export function updateAgentWorkflowStepEvidence(
  workspaceId: string,
  workflowId: string,
  stepId: string,
  request: UpdateAgentWorkflowStepEvidenceRequest,
): Promise<AgentWorkflow> {
  return requestJson<AgentWorkflow>(
    `/workspaces/${workspaceId}/agent-workflows/${workflowId}/steps/${stepId}/evidence`,
    {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export function getAgentWorkflowExecutionReadiness(
  workspaceId: string,
  workflowId: string,
): Promise<AgentWorkflowExecutionReadiness> {
  return getJson<AgentWorkflowExecutionReadiness>(
    `/workspaces/${workspaceId}/agent-workflows/${workflowId}/execution-readiness`,
  );
}

export function archiveAgentWorkflow(
  workspaceId: string,
  workflowId: string,
  archived: boolean,
): Promise<AgentWorkflow> {
  return requestJson<AgentWorkflow>(
    `/workspaces/${workspaceId}/agent-workflows/${workflowId}/archive`,
    {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ archived }),
    },
  );
}

export function deleteAgentWorkflow(workspaceId: string, workflowId: string): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/agent-workflows/${workflowId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}


export function getMCPServerCatalog(): Promise<MCPServerCatalog> {
  return getJson<MCPServerCatalog>("/mcp/catalog");
}

export function createMCPConfigPreview(
  request: MCPConfigPreviewRequest,
): Promise<MCPServerConfigPreview> {
  return requestJson<MCPServerConfigPreview>("/mcp/config-preview", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function createMCPConnectionCheck(
  request: MCPConnectionCheckRequest,
): Promise<MCPServerConnectionCheck> {
  return requestJson<MCPServerConnectionCheck>("/mcp/connection-check", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}


export function listWorkspaceMCPConfigs(workspaceId: string): Promise<WorkspaceMCPConfigList> {
  return getJson<WorkspaceMCPConfigList>(`/mcp/workspaces/${workspaceId}/configs`);
}

export function createWorkspaceMCPConfig(
  workspaceId: string,
  request: CreateWorkspaceMCPConfigRequest,
): Promise<WorkspaceMCPServerConfig> {
  return requestJson<WorkspaceMCPServerConfig>(`/mcp/workspaces/${workspaceId}/configs`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function updateWorkspaceMCPConfig(
  workspaceId: string,
  configId: string,
  request: UpdateWorkspaceMCPConfigRequest,
): Promise<WorkspaceMCPServerConfig> {
  return requestJson<WorkspaceMCPServerConfig>(`/mcp/workspaces/${workspaceId}/configs/${configId}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function deleteWorkspaceMCPConfig(workspaceId: string, configId: string): Promise<void> {
  return requestWithoutBody(`/mcp/workspaces/${workspaceId}/configs/${configId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

export function getWorkspaceMCPToolInventory(workspaceId: string): Promise<MCPToolInventory> {
  return getJson<MCPToolInventory>(`/mcp/workspaces/${workspaceId}/tool-inventory`);
}

export function previewWorkspaceMCPApproval(
  workspaceId: string,
  configId: string,
  request: MCPApprovalPreviewRequest,
): Promise<MCPApprovalPreview> {
  return requestJson<MCPApprovalPreview>(`/mcp/workspaces/${workspaceId}/configs/${configId}/approval-preview`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function getAgentCapabilities(): Promise<AgentCapabilityCatalog> {
  return getJson<AgentCapabilityCatalog>("/models/agent-capabilities");
}

export function createAgentPlanningPreview(
  request: AgentPlanningPreviewRequest,
): Promise<AgentPlanningPreview> {
  return requestJson<AgentPlanningPreview>("/models/agent-planning-preview", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function getModelsDashboardSummary(
  workspaceId: string,
): Promise<WorkspaceModelsDashboardSummary> {
  return getJson<WorkspaceModelsDashboardSummary>(
    `/workspaces/${workspaceId}/models/dashboard/summary`,
  );
}

export function getWorkspaceModelsDashboard(
  workspaceId: string,
): Promise<WorkspaceModelsDashboard> {
  return getJson<WorkspaceModelsDashboard>(
    `/workspaces/${workspaceId}/models/dashboard`,
  );
}

export function getLocalAIActivationGuide(
  workspaceId: string,
): Promise<LocalAIActivationGuide> {
  return getJson<LocalAIActivationGuide>(
    `/workspaces/${workspaceId}/local-ai/activation-guide`,
  );
}


export function createWorkspaceConversation(
  workspaceId: string,
  title?: string,
): Promise<WorkspaceConversation> {
  return requestJson<WorkspaceConversation>(`/workspaces/${workspaceId}/conversations`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title }),
  });
}

export function listWorkspaceConversations(
  workspaceId: string,
  options: { search?: string; includeArchived?: boolean; pinnedOnly?: boolean } = {},
): Promise<WorkspaceConversation[]> {
  const params = new URLSearchParams();
  if (options.search?.trim()) {
    params.set("search", options.search.trim());
  }
  if (options.includeArchived) {
    params.set("include_archived", "true");
  }
  if (options.pinnedOnly) {
    params.set("pinned_only", "true");
  }
  const query = params.toString();
  return getJson<WorkspaceConversation[]>(`/workspaces/${workspaceId}/conversations${query ? `?${query}` : ""}`);
}

export function getWorkspaceConversation(
  workspaceId: string,
  conversationId: string,
): Promise<WorkspaceConversation> {
  return getJson<WorkspaceConversation>(`/workspaces/${workspaceId}/conversations/${conversationId}`);
}

export function updateWorkspaceConversationTitle(
  workspaceId: string,
  conversationId: string,
  title: string,
): Promise<WorkspaceConversation> {
  return requestJson<WorkspaceConversation>(`/workspaces/${workspaceId}/conversations/${conversationId}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title }),
  });
}

export function updateWorkspaceConversationPinned(
  workspaceId: string,
  conversationId: string,
  pinned: boolean,
): Promise<WorkspaceConversation> {
  return requestJson<WorkspaceConversation>(`/workspaces/${workspaceId}/conversations/${conversationId}/pin`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ pinned }),
  });
}

export function updateWorkspaceConversationArchived(
  workspaceId: string,
  conversationId: string,
  archived: boolean,
): Promise<WorkspaceConversation> {
  return requestJson<WorkspaceConversation>(`/workspaces/${workspaceId}/conversations/${conversationId}/archive`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ archived }),
  });
}

export function exportWorkspaceConversation(
  workspaceId: string,
  conversationId: string,
  format: "markdown" | "text" | "json" = "markdown",
): Promise<ConversationExport> {
  const params = new URLSearchParams({ format });
  return getJson<ConversationExport>(
    `/workspaces/${workspaceId}/conversations/${conversationId}/export?${params.toString()}`,
  );
}

export function listWorkspaceAnswerNotes(
  workspaceId: string,
  options: { search?: string; pinnedOnly?: boolean; sourcePath?: string } = {},
): Promise<ConversationAnswerNote[]> {
  const params = new URLSearchParams();
  if (options.search?.trim()) {
    params.set("search", options.search.trim());
  }
  if (options.pinnedOnly) {
    params.set("pinned_only", "true");
  }
  if (options.sourcePath?.trim()) {
    params.set("source_path", options.sourcePath.trim());
  }
  const query = params.toString();
  return getJson<ConversationAnswerNote[]>(`/workspaces/${workspaceId}/answer-notes${query ? `?${query}` : ""}`);
}

export function saveConversationAnswerNote(
  workspaceId: string,
  conversationId: string,
  messageId: string,
  request: { title?: string; content?: string } = {},
): Promise<ConversationAnswerNote> {
  return requestJson<ConversationAnswerNote>(
    `/workspaces/${workspaceId}/conversations/${conversationId}/messages/${messageId}/note`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export function updateWorkspaceAnswerNote(
  workspaceId: string,
  noteId: string,
  request: { title?: string | null; content?: string | null; pinned?: boolean | null },
): Promise<ConversationAnswerNote> {
  return requestJson<ConversationAnswerNote>(`/workspaces/${workspaceId}/answer-notes/${noteId}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function updateWorkspaceAnswerNotePinned(
  workspaceId: string,
  noteId: string,
  pinned: boolean,
): Promise<ConversationAnswerNote> {
  return requestJson<ConversationAnswerNote>(`/workspaces/${workspaceId}/answer-notes/${noteId}/pin`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ pinned }),
  });
}

export function getConversationContextPreview(
  workspaceId: string,
  conversationId: string,
): Promise<ConversationContextPreview> {
  return getJson<ConversationContextPreview>(`/workspaces/${workspaceId}/conversations/${conversationId}/context-preview`);
}

export function deleteWorkspaceAnswerNote(
  workspaceId: string,
  noteId: string,
): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/answer-notes/${noteId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

export function deleteWorkspaceConversation(
  workspaceId: string,
  conversationId: string,
): Promise<void> {
  return requestWithoutBody(`/workspaces/${workspaceId}/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

export type AttachedDocumentInput = {
  name: string;
  content: string;
};

export function askSelectedWorkspace(
  workspaceId: string,
  question: string,
  limit: number,
  skillContext: SkillContextRequest[] = [],
  options: {
    signal?: AbortSignal;
    conversationId?: string | null;
    images?: string[];
    temperature?: number | null;
    think?: boolean | null;
    attachedDocuments?: AttachedDocumentInput[];
  } = {},
): Promise<WorkspaceQuestionAnswer> {
  return requestJson<WorkspaceQuestionAnswer>(
    `/workspaces/${workspaceId}/ask-selected`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        limit,
        skill_context: skillContext,
        conversation_id: options.conversationId ?? null,
        images: options.images ?? [],
        temperature: options.temperature ?? null,
        think: options.think ?? null,
        attached_documents: options.attachedDocuments ?? [],
      }),
      signal: options.signal,
    },
  );
}

export async function askSelectedWorkspaceStream(
  workspaceId: string,
  question: string,
  limit: number,
  skillContext: SkillContextRequest[] = [],
  options: {
    signal?: AbortSignal;
    conversationId?: string | null;
    images?: string[];
    temperature?: number | null;
    think?: boolean | null;
    attachedDocuments?: AttachedDocumentInput[];
    onToken?: (text: string) => void;
  } = {},
): Promise<WorkspaceQuestionAnswer> {
  const response = await fetch(
    `${apiBaseUrl}/workspaces/${workspaceId}/ask-selected/stream`,
    {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        limit,
        skill_context: skillContext,
        conversation_id: options.conversationId ?? null,
        images: options.images ?? [],
        temperature: options.temperature ?? null,
        think: options.think ?? null,
        attached_documents: options.attachedDocuments ?? [],
      }),
      signal: options.signal,
    },
  );
  await assertOk(response);
  if (!response.body) {
    throw new Error("Streaming is not supported in this environment.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalAnswer: WorkspaceQuestionAnswer | null = null;
  let errorDetail: string | null = null;

  const handleEvent = (rawEvent: string): void => {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }
    const data = dataLines.join("\n");
    if (!data) {
      return;
    }
    if (eventName === "token") {
      const parsed = JSON.parse(data) as { text?: string };
      if (parsed.text) {
        options.onToken?.(parsed.text);
      }
    } else if (eventName === "final") {
      finalAnswer = JSON.parse(data) as WorkspaceQuestionAnswer;
    } else if (eventName === "error") {
      const parsed = JSON.parse(data) as { detail?: string };
      errorDetail = parsed.detail ?? "Streaming failed.";
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      handleEvent(rawEvent);
      separatorIndex = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) {
    handleEvent(buffer);
  }

  if (errorDetail) {
    throw new Error(errorDetail);
  }
  if (!finalAnswer) {
    throw new Error("The streaming response ended without a final answer.");
  }
  return finalAnswer;
}


export function updateWorkspaceModelSelection(
  workspaceId: string,
  selection: UpdateWorkspaceModelSelectionRequest,
): Promise<WorkspaceModelSelection> {
  return requestJson<WorkspaceModelSelection>(
    `/workspaces/${workspaceId}/models/selection`,
    {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(selection),
    },
  );
}

export function planModelExperiment(
  request: ModelExperimentPlanRequest,
): Promise<ModelExperimentPlan> {
  return requestJson<ModelExperimentPlan>("/models/experiments/plan", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function runModelExperiment(
  request: ModelExperimentPlanRequest,
): Promise<ModelExperimentRun> {
  return requestJson<ModelExperimentRun>("/models/experiments/run", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}



export function getWorkspaceModelExperiments(
  workspaceId: string,
): Promise<ModelExperimentRun[]> {
  return getJson<ModelExperimentRun[]>(
    `/workspaces/${workspaceId}/model-experiments`,
  );
}

export function getModelExperimentRatings(
  experimentId: string,
): Promise<ModelExperimentRating[]> {
  return getJson<ModelExperimentRating[]>(
    `/models/experiments/${experimentId}/ratings`,
  );
}

export function saveModelExperimentRating(
  experimentId: string,
  rating: ModelExperimentRatingRequest,
): Promise<ModelExperimentRating> {
  return requestJson<ModelExperimentRating>(
    `/models/experiments/${experimentId}/ratings`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(rating),
    },
  );
}

export function getGuidedModelSetup(
  workspaceId: string,
): Promise<GuidedModelSetupGuide> {
  return getJson<GuidedModelSetupGuide>(`/workspaces/${workspaceId}/models/setup-guide`);
}


export function getLocalModelInstallGuide(): Promise<LocalModelInstallGuide> {
  return getJson<LocalModelInstallGuide>("/models/local-install-guide");
}

export function getOllamaModelRecommendations(): Promise<OllamaModelRecommendationGuide> {
  return getJson<OllamaModelRecommendationGuide>("/models/ollama-recommendations");
}

export function getLocalModelInstallStatus(): Promise<LocalModelInstallStatus> {
  return getJson<LocalModelInstallStatus>("/models/local-install-status");
}

export function deleteInstalledModel(
  name: string,
): Promise<{ deleted: string; runtime_url: string }> {
  return requestJson<{ deleted: string; runtime_url: string }>(
    "/models/local-install/delete",
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name }),
    },
  );
}

export function getLocalModelDownloadWorkerPlan(): Promise<LocalModelDownloadWorkerPlan> {
  return getJson<LocalModelDownloadWorkerPlan>("/models/local-download-worker-plan");
}

export function createLocalModelInstallDraft(
  request: CreateLocalModelInstallDraftRequest,
): Promise<LocalModelInstallDraft> {
  return requestJson<LocalModelInstallDraft>("/models/local-install-drafts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export function getLocalModelDownloadExecutionCapability(): Promise<LocalModelDownloadExecutionCapability> {
  return getJson<LocalModelDownloadExecutionCapability>("/models/local-download-execution-capability");
}


export function startLocalModelDownloadJob(commandId: string): Promise<LocalModelDownloadJob> {
  return requestJson<LocalModelDownloadJob>(`/models/local-install-drafts/${commandId}/jobs`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });
}

export function getLocalModelDownloadJob(jobId: string): Promise<LocalModelDownloadJob> {
  return getJson<LocalModelDownloadJob>(`/models/local-download-jobs/${jobId}`);
}

export function listLocalModelDownloadJobs(workspaceId?: string): Promise<LocalModelDownloadJobList> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return getJson<LocalModelDownloadJobList>(`/models/local-download-jobs${query}`);
}

export function cancelLocalModelDownloadJob(jobId: string): Promise<LocalModelDownloadJob> {
  return requestJson<LocalModelDownloadJob>(`/models/local-download-jobs/${jobId}/cancel`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });
}

export function runLocalModelInstallDraft(commandId: string): Promise<LocalModelDownloadExecutionResult> {
  return requestJson<LocalModelDownloadExecutionResult>(`/models/local-install-drafts/${commandId}/run`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });
}
