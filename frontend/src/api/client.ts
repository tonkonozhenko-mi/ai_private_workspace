import type {
  WorkspaceDashboard,
  WorkspaceModelsDashboardSummary,
  WorkspaceUIActionCatalog,
  WorkspacesOverview,
} from "./types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
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
