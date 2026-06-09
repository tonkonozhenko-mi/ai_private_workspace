import { useCallback, useEffect, useRef, useState } from "react";

import {
  API_BASE_URL,
  getLocalAIActivationGuide,
  getModelsDashboardSummary,
  getWorkspaceDashboard,
  getWorkspaceModelsDashboard,
  getWorkspacesOverview,
  getWorkspaceUIActions,
} from "./api/client";
import type {
  WorkspaceDetailBundle,
  WorkspaceModelsDetailBundle,
  WorkspaceOverviewItem,
} from "./api/types";
import { AskWorkspace } from "./components/AskWorkspace";
import { ModelsDetail } from "./components/ModelsDetail";
import { ModelsSummaryCard } from "./components/ModelsSummaryCard";
import { ActivityTimeline } from "./components/ActivityTimeline";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { LoadingState } from "./components/LoadingState";
import { UIActionsPanel } from "./components/UIActionsPanel";
import { WorkspaceDashboard } from "./components/WorkspaceDashboard";
import { WorkspaceList } from "./components/WorkspaceList";

type WorkspaceTab = "overview" | "ask" | "models" | "actions" | "activity";

const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "ask", label: "Ask" },
  { id: "models", label: "Models" },
  { id: "actions", label: "Capabilities" },
  { id: "activity", label: "Activity" },
];

function App() {
  const [workspaces, setWorkspaces] = useState<WorkspaceOverviewItem[]>([]);
  const [totalWorkspaces, setTotalWorkspaces] = useState(0);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(
    null,
  );
  const selectedWorkspaceIdRef = useRef<string | null>(null);
  const [detail, setDetail] = useState<WorkspaceDetailBundle | null>(null);
  const [workspacesLoading, setWorkspacesLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [modelsDetail, setModelsDetail] =
    useState<WorkspaceModelsDetailBundle | null>(null);
  const [modelsDetailLoading, setModelsDetailLoading] = useState(false);
  const [modelsDetailError, setModelsDetailError] = useState<string | null>(null);
  const [workspacesError, setWorkspacesError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");

  const loadModelsDetail = useCallback(async (workspaceId: string) => {
    setModelsDetail(null);
    setModelsDetailLoading(true);
    setModelsDetailError(null);
    try {
      const [dashboard, activationGuide] = await Promise.all([
        getWorkspaceModelsDashboard(workspaceId),
        getLocalAIActivationGuide(workspaceId),
      ]);
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setModelsDetail({ dashboard, activationGuide });
      }
    } catch (error) {
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setModelsDetailError(errorMessage(error));
      }
    } finally {
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setModelsDetailLoading(false);
      }
    }
  }, []);

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
      void loadModelsDetail(workspaceId);
    } catch (error) {
      setDetail(null);
      setModelsDetail(null);
      setDetailError(errorMessage(error));
    } finally {
      setDetailLoading(false);
    }
  }, [loadModelsDetail]);

  const loadWorkspaces = useCallback(async () => {
    setWorkspacesLoading(true);
    setWorkspacesError(null);
    try {
      const overview = await getWorkspacesOverview();
      setWorkspaces(overview.items);
      setTotalWorkspaces(overview.total_workspaces);
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

  const refreshWorkspaceReadOnlyState = useCallback(async (workspaceId: string) => {
    const [
      dashboard,
      actions,
      modelsSummary,
      modelsDashboard,
      activationGuide,
      overview,
    ] = await Promise.all([
      getWorkspaceDashboard(workspaceId),
      getWorkspaceUIActions(workspaceId),
      getModelsDashboardSummary(workspaceId),
      getWorkspaceModelsDashboard(workspaceId),
      getLocalAIActivationGuide(workspaceId),
      getWorkspacesOverview(),
    ]);

    if (selectedWorkspaceIdRef.current === workspaceId) {
      setDetail({ dashboard, actions, modelsSummary });
      setModelsDetail({ dashboard: modelsDashboard, activationGuide });
      setModelsDetailError(null);
      setWorkspaces(overview.items);
      setTotalWorkspaces(overview.total_workspaces);
    }
  }, []);

  const refreshAfterAsk = useCallback(async (workspaceId: string) => {
    try {
      const [dashboard, overview] = await Promise.all([
        getWorkspaceDashboard(workspaceId),
        getWorkspacesOverview(),
      ]);
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setDetail((current) =>
          current ? { ...current, dashboard } : current,
        );
        setWorkspaces(overview.items);
        setTotalWorkspaces(overview.total_workspaces);
      }
    } catch {
      // The submitted answer remains visible if the optional read-only refresh fails.
    }
  }, []);

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
            <div className="sidebar-title-line">
              <h2>Workspaces</h2>
              <span className="sidebar-workspace-count">{totalWorkspaces}</span>
            </div>
            <p className="sidebar-subtitle">Select a workspace to inspect</p>
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
          <LoadingState title="Loading workspaces" compact />
        ) : workspacesError ? (
          <ErrorState
            title="Backend unavailable"
            message={workspacesError}
            compact
            onRetry={loadWorkspaces}
          />
        ) : (
          <WorkspaceList
            workspaces={workspaces}
            selectedWorkspaceId={selectedWorkspaceId}
            onSelect={(workspaceId) => void loadWorkspaceDetail(workspaceId)}
          />
        )}

        <footer className="sidebar-footer">
          <span>Frontend is connected to local backend.</span>
          <code>{API_BASE_URL}</code>
        </footer>
      </aside>

      <main className="main-content">
        {detailLoading ? (
          <LoadingState
            title="Loading workspace dashboard"
            message="Collecting the latest read-only workspace state."
          />
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
            <header className="workspace-navigation-shell">
              <nav className="workspace-tabs" aria-label="Workspace sections">
                <div role="tablist" aria-label="Workspace views">
                  {workspaceTabs.map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      aria-selected={activeTab === tab.id}
                      aria-controls="workspace-tab-content"
                      data-tab-id={tab.id}
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
              </nav>
              <div className="workspace-context-chip" aria-label="Current workspace">
                <span>{detail.dashboard.workspace_name}</span>
                <strong>{detail.dashboard.status}</strong>
              </div>
            </header>

            <section
              id="workspace-tab-content"
              className="workspace-tab-content"
              role="tabpanel"
            >
              {activeTab === "overview" ? (
                <WorkspaceDashboard
                  dashboard={detail.dashboard}
                  modelsSummary={detail.modelsSummary}
                  onOpenAsk={() => setActiveTab("ask")}
                  onOpenModels={() => setActiveTab("models")}
                />
              ) : null}
              <div hidden={activeTab !== "ask"}>
                <AskWorkspace
                  key={detail.dashboard.workspace_id}
                  workspaceId={detail.dashboard.workspace_id}
                  onAsked={() => refreshAfterAsk(detail.dashboard.workspace_id)}
                />
              </div>
              {activeTab === "models" ? (
                <div className="models-tab">
                  <div className="information-band">
                    <p>
                      <strong>Chosen AI model:</strong> can be used per question without changing the backend default.
                    </p>
                    <p>
                      <strong>Chosen search model:</strong> powers workspace search. If it changes, rebuild the search context before asking questions.
                    </p>
                  </div>
                  {modelsDetailLoading ? (
                    <>
                      <LoadingState
                        title="Loading detailed model state"
                        message="The compact models summary remains available."
                        compact
                      />
                      <ModelsSummaryCard summary={detail.modelsSummary} spacious />
                    </>
                  ) : modelsDetailError ? (
                    <>
                      <ErrorState
                        title="Detailed model data is unavailable"
                        message={modelsDetailError}
                        compact
                        onRetry={
                          selectedWorkspaceId
                            ? () => loadModelsDetail(selectedWorkspaceId)
                            : undefined
                        }
                      />
                      <ModelsSummaryCard summary={detail.modelsSummary} spacious />
                    </>
                  ) : modelsDetail ? (
                    <ModelsDetail
                      workspaceId={detail.dashboard.workspace_id}
                      hasScan={detail.dashboard.summary.has_scan}
                      dashboard={modelsDetail.dashboard}
                      activationGuide={modelsDetail.activationGuide}
                      onSelectionUpdated={() =>
                        refreshWorkspaceReadOnlyState(detail.dashboard.workspace_id)
                      }
                    />
                  ) : (
                    <ModelsSummaryCard summary={detail.modelsSummary} spacious />
                  )}
                </div>
              ) : null}
              {activeTab === "actions" ? (
                <UIActionsPanel catalog={detail.actions} />
              ) : null}
              {activeTab === "activity" ? (
                <ActivityTimeline events={detail.dashboard.recent_events} />
              ) : null}
            </section>
          </div>
        ) : (
          <EmptyState
            title="Select a workspace"
            message="Choose a local project from the sidebar to inspect its dashboard, model status, and capabilities."
          />
        )}
      </main>
    </div>
  );
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected request error";
}

export default App;
