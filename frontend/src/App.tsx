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
import {
  WorkspaceActivity,
  WorkspaceDashboard,
} from "./components/WorkspaceDashboard";
import { WorkspaceList } from "./components/WorkspaceList";

type WorkspaceTab = "overview" | "models" | "actions" | "activity";

const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "models", label: "Models" },
  { id: "actions", label: "Actions" },
  { id: "activity", label: "Activity" },
];

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
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");

  const loadWorkspaceDetail = useCallback(async (workspaceId: string) => {
    if (selectedWorkspaceIdRef.current !== workspaceId) {
      setActiveTab("overview");
    }
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
            <nav className="workspace-tabs" aria-label="Workspace sections">
              <div role="tablist" aria-label="Workspace views">
                {workspaceTabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === tab.id}
                    aria-controls="workspace-tab-content"
                    className={activeTab === tab.id ? "is-selected" : ""}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                    {tab.id === "activity" ? (
                      <span>{detail.dashboard.recent_events.length}</span>
                    ) : null}
                  </button>
                ))}
              </div>
              <p>Read-only workspace views</p>
            </nav>

            <section
              id="workspace-tab-content"
              className="workspace-tab-content"
              role="tabpanel"
            >
              {activeTab === "overview" ? (
                <WorkspaceDashboard
                  dashboard={detail.dashboard}
                  modelsSummary={detail.modelsSummary}
                />
              ) : null}
              {activeTab === "models" ? (
                <div className="models-tab">
                  <header className="tab-section-heading">
                    <div>
                      <p className="eyebrow">Workspace models</p>
                      <h1>Selected and active models</h1>
                    </div>
                    <span
                      className={`status-badge status-${detail.modelsSummary.overall_status}`}
                    >
                      {formatLabel(detail.modelsSummary.overall_status)}
                    </span>
                  </header>
                  <div className="information-band">
                    <p>
                      <strong>Selected LLM:</strong> supported selections can be
                      used per request without changing the active backend
                      runtime.
                    </p>
                    <p>
                      <strong>Selected embedding:</strong> indexing and search
                      require the active embedding runtime to match, followed by
                      reindexing when the embedding space changes.
                    </p>
                  </div>
                  <ModelsSummaryCard summary={detail.modelsSummary} spacious />
                </div>
              ) : null}
              {activeTab === "actions" ? (
                <UIActionsPanel catalog={detail.actions} />
              ) : null}
              {activeTab === "activity" ? (
                <WorkspaceActivity dashboard={detail.dashboard} />
              ) : null}
            </section>
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

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

export default App;
