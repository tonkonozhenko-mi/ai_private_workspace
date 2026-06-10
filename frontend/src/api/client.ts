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
  WorkspaceConversation,
  SkillContextRequest,
  WorkspaceSkillProfile,
  WorkspaceSkillProfileRequest,
  WorkspaceUIActionCatalog,
  WorkspacesOverview,
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
): Promise<WorkspaceConversation[]> {
  return getJson<WorkspaceConversation[]>(`/workspaces/${workspaceId}/conversations`);
}

export function getWorkspaceConversation(
  workspaceId: string,
  conversationId: string,
): Promise<WorkspaceConversation> {
  return getJson<WorkspaceConversation>(`/workspaces/${workspaceId}/conversations/${conversationId}`);
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
