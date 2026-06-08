import { useCallback, useEffect, useRef, useState } from "react";

import {
  API_BASE_URL,
  getModelsDashboardSummary,
  getWorkspaceDashboard,
  getWorkspacesOverview,
  getWorkspaceUIActions,
} from "./api/client";
import type {
  WorkspaceDetailBundle,
  WorkspaceOverviewItem,
} from "./api/types";
import { ModelsSummaryCard } from "./components/ModelsSummaryCard";
import { UIActionsPanel } from "./components/UIActionsPanel";
import { WorkspaceDashboard } from "./components/WorkspaceDashboard";
import { WorkspaceList } from "./components/WorkspaceList";

function App() {
  const [workspaces, setWorkspaces] = useState<WorkspaceOverviewItem[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(
    null,
  );
  const selectedWorkspaceIdRef = useRef<string | null>(null);
  const [detail, setDetail] = useState<WorkspaceDetailBundle | null>(null);
  const [workspacesLoading, setWorkspacesLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [workspacesError, setWorkspacesError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadWorkspaceDetail = useCallback(async (workspaceId: string) => {
    selectedWorkspaceIdRef.current = workspaceId;
    setSelectedWorkspaceId(workspaceId);
    setDetailLoading(true);
    setDetailError(null);
    try {
      const [dashboard, actions, modelsSummary] = await Promise.all([
        getWorkspaceDashboard(workspaceId),
        getWorkspaceUIActions(workspaceId),
        getModelsDashboardSummary(workspaceId),
      ]);
      setDetail({ dashboard, actions, modelsSummary });
    } catch (error) {
      setDetail(null);
      setDetailError(errorMessage(error));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const loadWorkspaces = useCallback(async () => {
    setWorkspacesLoading(true);
    setWorkspacesError(null);
    try {
      const overview = await getWorkspacesOverview();
      setWorkspaces(overview.items);
      if (overview.items.length > 0) {
        const currentExists = overview.items.some(
          (workspace) =>
            workspace.workspace_id === selectedWorkspaceIdRef.current,
        );
        const nextWorkspaceId = currentExists
          ? selectedWorkspaceIdRef.current
          : overview.items[0].workspace_id;
        if (nextWorkspaceId) {
          await loadWorkspaceDetail(nextWorkspaceId);
        }
      } else {
        selectedWorkspaceIdRef.current = null;
        setSelectedWorkspaceId(null);
        setDetail(null);
      }
    } catch (error) {
      setWorkspacesError(errorMessage(error));
    } finally {
      setWorkspacesLoading(false);
    }
  }, [loadWorkspaceDetail]);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <header className="brand">
          <span className="brand-mark" aria-hidden="true">
            PW
          </span>
          <div>
            <strong>Private Project</strong>
            <span>AI Workbench</span>
          </div>
        </header>

        <div className="sidebar-heading">
          <div>
            <p className="eyebrow">Local workspaces</p>
            <h2>Projects</h2>
          </div>
          <button
            className="text-button"
            type="button"
            onClick={() => void loadWorkspaces()}
          >
            Refresh
          </button>
        </div>

        {workspacesLoading && workspaces.length === 0 ? (
          <LoadingState label="Loading workspaces" compact />
        ) : workspacesError ? (
          <ErrorState message={workspacesError} compact onRetry={loadWorkspaces} />
        ) : (
          <WorkspaceList
            workspaces={workspaces}
            selectedWorkspaceId={selectedWorkspaceId}
            onSelect={(workspaceId) => void loadWorkspaceDetail(workspaceId)}
          />
        )}

        <footer className="sidebar-footer">
          <span>Backend</span>
          <code>{API_BASE_URL}</code>
        </footer>
      </aside>

      <main className="main-content">
        {detailLoading ? (
          <LoadingState label="Loading workspace dashboard" />
        ) : detailError ? (
          <ErrorState
            message={detailError}
            onRetry={
              selectedWorkspaceId
                ? () => loadWorkspaceDetail(selectedWorkspaceId)
                : loadWorkspaces
            }
          />
        ) : detail ? (
          <div className="dashboard-layout">
            <WorkspaceDashboard dashboard={detail.dashboard} />
            <div className="dashboard-columns">
              <ModelsSummaryCard summary={detail.modelsSummary} />
              <UIActionsPanel catalog={detail.actions} />
            </div>
          </div>
        ) : (
          <section className="welcome-state">
            <div className="welcome-mark" aria-hidden="true">
              PW
            </div>
            <p className="eyebrow">Private Project AI Workbench</p>
            <h1>Select a workspace</h1>
            <p>
              Choose a local project from the sidebar to inspect its dashboard,
              models status, and read-only action catalog.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

function LoadingState({
  label,
  compact = false,
}: {
  label: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`loading-state${compact ? " is-compact" : ""}`}
      aria-live="polite"
    >
      <span className="loading-indicator" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

function ErrorState({
  message,
  compact = false,
  onRetry,
}: {
  message: string;
  compact?: boolean;
  onRetry: () => void | Promise<void>;
}) {
  return (
    <div className={`error-state${compact ? " is-compact" : ""}`} role="alert">
      <strong>Could not load data</strong>
      <span>{message}</span>
      <button
        className="primary-button"
        type="button"
        onClick={() => void onRetry()}
      >
        Retry
      </button>
    </div>
  );
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected request error";
}

export default App;
