import type {
  LocalAIActivationGuide,
  ModelExperimentPlan,
  ModelExperimentPlanRequest,
  ModelExperimentRating,
  ModelExperimentRatingRequest,
  ModelExperimentRun,
  CreateWorkspaceRequest,
  CreatedWorkspace,
  ProjectScanResponse,
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
  ReportCatalog,
  WorkspaceReport,
  BuildCustomWorkspaceReportRequest,
  SaveEditedWorkspaceReportRequest,
  SavedWorkspaceReport,
  UpdateSavedWorkspaceReportRequest,
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

export function askSelectedWorkspace(
  workspaceId: string,
  question: string,
  limit: number,
  skillContext: SkillContextRequest[] = [],
  options: { signal?: AbortSignal; conversationId?: string | null } = {},
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
      }),
      signal: options.signal,
    },
  );
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
