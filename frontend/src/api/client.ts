import type {
  LocalAIActivationGuide,
  ModelExperimentPlan,
  ModelExperimentPlanRequest,
  WorkspaceDashboard,
  WorkspaceModelsDashboard,
  UpdateWorkspaceModelSelectionRequest,
  WorkspaceModelSelection,
  WorkspaceModelsDashboardSummary,
  WorkspaceQuestionAnswer,
  WorkspaceUIActionCatalog,
  WorkspacesOverview,
} from "./types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path, {
    headers: {
      Accept: "application/json",
    },
  });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
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

  return (await response.json()) as T;
}

export function getWorkspacesOverview(): Promise<WorkspacesOverview> {
  return getJson<WorkspacesOverview>("/workspaces/overview");
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

export function askSelectedWorkspace(
  workspaceId: string,
  question: string,
  limit: number,
): Promise<WorkspaceQuestionAnswer> {
  return requestJson<WorkspaceQuestionAnswer>(
    `/workspaces/${workspaceId}/ask-selected`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, limit }),
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
