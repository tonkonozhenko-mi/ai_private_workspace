import { useCallback, useEffect, useRef, useState } from "react";

import {
  DEFAULT_API_BASE_URL,
  archiveWorkspace,
  restoreWorkspace,
  deleteWorkspace,
  clearWorkspaceIndex,
  getLocalAIActivationGuide,
  getModelsDashboardSummary,
  getWorkspaceDashboard,
  getWorkspaceModelsDashboard,
  getWorkspacesOverview,
  cancelWorkspaceJob,
  getWorkspaceJob,
  listWorkspaceJobs,
  startIndexWorkspaceJob,
  startScanWorkspaceJob,
  previewWorkspaceFileSelection,
  getWorkspaceIndexingRules,
  getWorkspaceSkillProfile,
  getWorkspaceUIActions,
  setApiBaseUrl,
} from "./api/client";
import type {
  WorkspaceDetailBundle,
  WorkspaceModelsDetailBundle,
  WorkspaceOverviewItem,
  WorkspaceJob,
  FileSelectionPreview,
  WorkspaceSkillProfile,
} from "./api/types";
import { AskWorkspace } from "./components/AskWorkspace";
import { CreateWorkspacePanel } from "./components/CreateWorkspacePanel";
import { ModelsDetail } from "./components/ModelsDetail";
import { RenderCrashBoundary } from "./components/RenderCrashBoundary";
import { ModelsSummaryCard } from "./components/ModelsSummaryCard";
import { ReportsPanel } from "./components/ReportsPanel";
import { ActivityTimeline } from "./components/ActivityTimeline";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { LoadingState } from "./components/LoadingState";
import { UIActionsPanel } from "./components/UIActionsPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { ensureAppOwnedBackendRuntime, isRunningInsideTauri, tauriBridgeDiagnostic } from "./desktopRuntime";
import { WorkspaceDashboard } from "./components/WorkspaceDashboard";
import { WorkspaceList } from "./components/WorkspaceList";
import {
  DEFAULT_FILE_INDEXING_PREFERENCES,
  normalizeFileIndexingPreferences,
  toFileSelectionRulesRequest,
  type FileIndexingPreferences,
} from "./components/fileIndexingPreferences";
import { DEFAULT_SKILL_PREFERENCES, normalizeSkillPreferences, skillPreferencesFromProfile, type SkillPreferences } from "./components/skillLibrary";
import UpdateNotice from "./components/UpdateNotice";

type WorkspaceTab = "overview" | "ask" | "models" | "reports" | "actions" | "activity" | "settings";

type ThemePreference = "system" | "light" | "dark";
type DensityPreference = "comfortable" | "compact";
type SourceSnippetPreference = 3 | 5 | 8 | 10;
type AccentColorPreference = "green" | "blue" | "purple" | "orange";
type DemoModePreference = "off" | "on";

export interface WorkbenchPreferences {
  theme: ThemePreference;
  density: DensityPreference;
  defaultSourceSnippets: SourceSnippetPreference;
  landingTab: WorkspaceTab;
  apiBaseUrl: string;
  brandInitials: string;
  productName: string;
  accentColor: AccentColorPreference;
  demoMode: DemoModePreference;
  developerMode: boolean;
  answerCreativity: AnswerCreativityPreference;
  skillPreferences: SkillPreferences;
  fileIndexingPreferences: FileIndexingPreferences;
}

export type AnswerCreativityPreference = "precise" | "balanced" | "creative";

export const ANSWER_CREATIVITY_TEMPERATURE: Record<AnswerCreativityPreference, number> = {
  precise: 0.1,
  balanced: 0.5,
  creative: 0.9,
};

const PREFERENCES_STORAGE_KEY = "ai-private-workspace.preferences.v1";
const LEGACY_PREFERENCES_STORAGE_KEY = "private-project-ai-workbench.preferences.v1";
const LAST_WORKSPACE_STORAGE_KEY = "ai-private-workspace.last-workspace-id.v1";
const DEFAULT_PREFERENCES: WorkbenchPreferences = {
  theme: "system",
  density: "comfortable",
  defaultSourceSnippets: 5,
  landingTab: "overview",
  apiBaseUrl: DEFAULT_API_BASE_URL,
  brandInitials: "AI",
  productName: "AI Private Workspace",
  accentColor: "green",
  demoMode: "off",
  developerMode: false,
  answerCreativity: "precise",
  skillPreferences: DEFAULT_SKILL_PREFERENCES,
  fileIndexingPreferences: DEFAULT_FILE_INDEXING_PREFERENCES,
};

const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Home" },
  { id: "ask", label: "Ask" },
  { id: "models", label: "Models" },
  { id: "settings", label: "Settings" },
];


async function waitForBackendApi(baseUrl: string, attempts = 20): Promise<boolean> {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${normalizedBaseUrl}/health`, {
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        return true;
      }
    } catch {
      // The packaged desktop backend may still be binding localhost.
    }
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
  return false;
}

function App() {
  const [workspaces, setWorkspaces] = useState<WorkspaceOverviewItem[]>([]);
  const [archivedWorkspaces, setArchivedWorkspaces] = useState<WorkspaceOverviewItem[]>([]);
  const [totalWorkspaces, setTotalWorkspaces] = useState(0);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(
    null,
  );
  const selectedWorkspaceIdRef = useRef<string | null>(null);
  const loadWorkspacesRequestIdRef = useRef(0);
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
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [archivingWorkspaceId, setArchivingWorkspaceId] = useState<string | null>(null);
  const [restoringWorkspaceId, setRestoringWorkspaceId] = useState<string | null>(null);
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState<string | null>(null);
  const [clearingIndexWorkspaceId, setClearingIndexWorkspaceId] = useState<string | null>(null);
  const [showArchivedWorkspaces, setShowArchivedWorkspaces] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<WorkbenchPreferences>(() =>
    loadStoredPreferences(),
  );
  const [activityJobs, setActivityJobs] = useState<WorkspaceJob[]>([]);
  const [activityJobsLoading, setActivityJobsLoading] = useState(false);
  const [activityJobsError, setActivityJobsError] = useState<string | null>(null);
  const [workspaceSkillProfile, setWorkspaceSkillProfile] = useState<WorkspaceSkillProfile | null>(null);
  const [resumeMessage, setResumeMessage] = useState<string | null>(null);
  const [desktopStartupMessage, setDesktopStartupMessage] = useState<string | null>(null);

  // Auto-dismiss successful startup messages so they don't linger over the UI.
  // Errors stay until something changes them.
  useEffect(() => {
    if (!desktopStartupMessage) {
      return;
    }
    const lower = desktopStartupMessage.toLowerCase();
    const isError =
      lower.includes("failed") ||
      lower.includes("unavailable") ||
      lower.includes("did not become") ||
      lower.includes("check ");
    if (isError) {
      return;
    }
    const timer = window.setTimeout(() => setDesktopStartupMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [desktopStartupMessage]);

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
      setActiveTab(preferences.landingTab);
    }
    selectedWorkspaceIdRef.current = workspaceId;
    setSelectedWorkspaceId(workspaceId);
    window.localStorage.setItem(LAST_WORKSPACE_STORAGE_KEY, workspaceId);
    setDetailLoading(true);
    setDetailError(null);
    try {
      const [dashboard, actions, modelsSummary, skillProfile] = await Promise.all([
        getWorkspaceDashboard(workspaceId),
        getWorkspaceUIActions(workspaceId),
        getModelsDashboardSummary(workspaceId),
        getWorkspaceSkillProfile(workspaceId),
      ]);
      setDetail({ dashboard, actions, modelsSummary });
      setWorkspaceSkillProfile(skillProfile);
      setPreferences((current) => ({
        ...current,
        skillPreferences: skillPreferencesFromProfile(skillProfile),
      }));
      void loadModelsDetail(workspaceId);
    } catch (error) {
      setDetail(null);
      setModelsDetail(null);
      setDetailError(errorMessage(error));
    } finally {
      setDetailLoading(false);
    }
  }, [loadModelsDetail, preferences.landingTab]);

  const loadWorkspaces = useCallback(async () => {
    const requestId = loadWorkspacesRequestIdRef.current + 1;
    loadWorkspacesRequestIdRef.current = requestId;
    setWorkspacesLoading(true);
    setWorkspacesError(null);
    try {
      const [overview, allOverview] = await Promise.all([
        getWorkspacesOverview(),
        getWorkspacesOverview({ includeArchived: true }),
      ]);
      if (loadWorkspacesRequestIdRef.current !== requestId) {
        return;
      }
      const archivedItems = allOverview.items.filter((workspace) => workspace.is_archived);
      setWorkspacesError(null);
      setWorkspaces(overview.items);
      setArchivedWorkspaces(archivedItems);
      setTotalWorkspaces(overview.total_workspaces);
      if (overview.items.length > 0) {
        const currentExists = overview.items.some(
          (workspace) =>
            workspace.workspace_id === selectedWorkspaceIdRef.current,
        );
        const storedWorkspaceId = window.localStorage.getItem(LAST_WORKSPACE_STORAGE_KEY);
        const storedExists = storedWorkspaceId
          ? overview.items.some((workspace) => workspace.workspace_id === storedWorkspaceId)
          : false;
        const nextWorkspaceId = currentExists
          ? selectedWorkspaceIdRef.current
          : storedExists
            ? storedWorkspaceId
            : overview.items[0].workspace_id;
        if (nextWorkspaceId) {
          await loadWorkspaceDetail(nextWorkspaceId);
          if (!currentExists && storedExists && loadWorkspacesRequestIdRef.current === requestId) {
            const restoredWorkspace = overview.items.find((workspace) => workspace.workspace_id === nextWorkspaceId);
            setResumeMessage(
              restoredWorkspace
                ? `Restored last workspace: ${restoredWorkspace.name}`
                : "Restored last workspace",
            );
          }
        }
      } else {
        selectedWorkspaceIdRef.current = null;
        setSelectedWorkspaceId(null);
        window.localStorage.removeItem(LAST_WORKSPACE_STORAGE_KEY);
        setDetail(null);
      }
    } catch (error) {
      if (loadWorkspacesRequestIdRef.current === requestId) {
        setWorkspacesError(errorMessage(error));
      }
    } finally {
      if (loadWorkspacesRequestIdRef.current === requestId) {
        setWorkspacesLoading(false);
      }
    }
  }, [loadWorkspaceDetail]);



  const loadActivityJobs = useCallback(async (workspaceId: string) => {
    setActivityJobsLoading(true);
    setActivityJobsError(null);
    try {
      const jobs = await listWorkspaceJobs(workspaceId);
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setActivityJobs(jobs);
      }
    } catch (error) {
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setActivityJobsError(errorMessage(error));
      }
    } finally {
      if (selectedWorkspaceIdRef.current === workspaceId) {
        setActivityJobsLoading(false);
      }
    }
  }, []);

  const refreshWorkspaceReadOnlyState = useCallback(async (workspaceId: string) => {
    const [
      dashboard,
      actions,
      modelsSummary,
      modelsDashboard,
      activationGuide,
      overview,
      indexingRules,
      skillProfile,
    ] = await Promise.all([
      getWorkspaceDashboard(workspaceId),
      getWorkspaceUIActions(workspaceId),
      getModelsDashboardSummary(workspaceId),
      getWorkspaceModelsDashboard(workspaceId),
      getLocalAIActivationGuide(workspaceId),
      getWorkspacesOverview(),
      getWorkspaceIndexingRules(workspaceId),
      getWorkspaceSkillProfile(workspaceId),
    ]);

    if (selectedWorkspaceIdRef.current === workspaceId) {
      setDetail({ dashboard, actions, modelsSummary });
      setModelsDetail({ dashboard: modelsDashboard, activationGuide });
      void loadActivityJobs(workspaceId);
      setModelsDetailError(null);
      setWorkspaces(overview.items);
      setTotalWorkspaces(overview.total_workspaces);
      setWorkspaceSkillProfile(skillProfile);
      setPreferences((current) => ({
        ...current,
        fileIndexingPreferences: {
          profile: indexingRules.profile === "source-first" || indexingRules.profile === "docs-first" ? indexingRules.profile : "balanced",
          includePatterns: indexingRules.include_patterns.join("\n"),
          excludePatterns: indexingRules.exclude_patterns.join("\n"),
        },
        skillPreferences: skillPreferencesFromProfile(skillProfile),
      }));
    }
  }, [loadActivityJobs]);

  const handleWorkspaceCreated = useCallback(async (workspaceId: string) => {
    setShowCreateWorkspace(false);
    await loadWorkspaces();
    await loadWorkspaceDetail(workspaceId);
    setActiveTab("overview");
  }, [loadWorkspaceDetail, loadWorkspaces]);


  const handleArchiveWorkspace = useCallback(async (workspace: WorkspaceOverviewItem) => {
    setArchivingWorkspaceId(workspace.workspace_id);
    setArchiveError(null);
    try {
      await archiveWorkspace(workspace.workspace_id);
      await loadWorkspaces();
    } catch (error) {
      setArchiveError(`Could not archive ${workspace.name}: ${errorMessage(error)}`);
    } finally {
      setArchivingWorkspaceId(null);
    }
  }, [loadWorkspaces]);

  const handleRestoreWorkspace = useCallback(async (workspace: WorkspaceOverviewItem) => {
    setRestoringWorkspaceId(workspace.workspace_id);
    setArchiveError(null);
    try {
      await restoreWorkspace(workspace.workspace_id);
      await loadWorkspaces();
      await loadWorkspaceDetail(workspace.workspace_id);
      setActiveTab("overview");
      setShowCreateWorkspace(false);
    } catch (error) {
      setArchiveError(`Could not restore ${workspace.name}: ${errorMessage(error)}`);
    } finally {
      setRestoringWorkspaceId(null);
    }
  }, [loadWorkspaceDetail, loadWorkspaces]);

  const handleDeleteWorkspace = useCallback(async (workspace: WorkspaceOverviewItem) => {
    setDeletingWorkspaceId(workspace.workspace_id);
    setArchiveError(null);
    try {
      await deleteWorkspace(workspace.workspace_id);
      await loadWorkspaces();
    } catch (error) {
      setArchiveError(`Could not delete ${workspace.name}: ${errorMessage(error)}`);
    } finally {
      setDeletingWorkspaceId(null);
    }
  }, [loadWorkspaces]);

  const handleClearWorkspaceIndex = useCallback(async (workspace: WorkspaceOverviewItem) => {
    setClearingIndexWorkspaceId(workspace.workspace_id);
    setArchiveError(null);
    try {
      await clearWorkspaceIndex(workspace.workspace_id);
      await loadWorkspaces();
      if (selectedWorkspaceIdRef.current === workspace.workspace_id) {
        await loadWorkspaceDetail(workspace.workspace_id);
      }
    } catch (error) {
      setArchiveError(
        `Could not clear the index for ${workspace.name}: ${errorMessage(error)}`,
      );
    } finally {
      setClearingIndexWorkspaceId(null);
    }
  }, [loadWorkspaceDetail, loadWorkspaces]);



  const handlePreviewFileSelection = useCallback((workspaceId: string): Promise<FileSelectionPreview> => {
    return previewWorkspaceFileSelection(
      workspaceId,
      toFileSelectionRulesRequest(preferences.fileIndexingPreferences),
    );
  }, [preferences.fileIndexingPreferences]);

  const handleStartScanJob = useCallback(async (workspaceId: string): Promise<WorkspaceJob> => {
    return startScanWorkspaceJob(workspaceId);
  }, []);

  const handleStartIndexJob = useCallback(async (workspaceId: string): Promise<WorkspaceJob> => {
    return startIndexWorkspaceJob(workspaceId);
  }, []);

  const handleGetWorkspaceJob = useCallback((workspaceId: string, jobId: string) => {
    return getWorkspaceJob(workspaceId, jobId);
  }, []);

  const handleListWorkspaceJobs = useCallback((workspaceId: string) => {
    return listWorkspaceJobs(workspaceId);
  }, []);

  const handleCancelWorkspaceJob = useCallback((workspaceId: string, jobId: string) => {
    return cancelWorkspaceJob(workspaceId, jobId);
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
    if (activeTab === "activity" && selectedWorkspaceId) {
      void loadActivityJobs(selectedWorkspaceId);
    }
  }, [activeTab, loadActivityJobs, selectedWorkspaceId]);

  useEffect(() => {
    window.localStorage.setItem(
      PREFERENCES_STORAGE_KEY,
      JSON.stringify(preferences),
    );
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.dataset.density = preferences.density;
    setApiBaseUrl(preferences.apiBaseUrl);
    document.documentElement.dataset.accent = preferences.accentColor;
    document.documentElement.dataset.demoMode = preferences.demoMode;
  }, [preferences]);

  useEffect(() => {
    let cancelled = false;

    async function startDesktopRuntimeAndLoadWorkspaces() {
      const bridgeDiagnostic = tauriBridgeDiagnostic();
      if (isRunningInsideTauri()) {
        setDesktopStartupMessage(`Starting local desktop backend… (${bridgeDiagnostic})`);
        try {
          const startup = await ensureAppOwnedBackendRuntime();
          if (!cancelled && startup) {
            setDesktopStartupMessage(startup.message);
          }
        } catch (error) {
          if (!cancelled) {
            setDesktopStartupMessage(`Desktop backend startup failed: ${errorMessage(error)}`);
            setWorkspacesError(errorMessage(error));
            setWorkspacesLoading(false);
          }
          return;
        }
      }

      if (!cancelled) {
        if (bridgeDiagnostic === "no-tauri-invoke-bridge" && window.location.protocol === "tauri:") {
          setDesktopStartupMessage("Desktop backend startup bridge is unavailable. Rebuild the app after enabling Tauri global invoke bridge.");
        }
        if (isRunningInsideTauri()) {
          const backendReady = await waitForBackendApi(preferences.apiBaseUrl);
          if (!cancelled && backendReady) {
            setWorkspacesError(null);
            setDesktopStartupMessage((current) => current ?? "Desktop backend is ready.");
          }
          if (!cancelled && !backendReady) {
            setDesktopStartupMessage("Desktop backend did not become reachable from the packaged UI. Check desktop-supervisor.log and backend.log.");
          }
        }
        await loadWorkspaces();
      }
    }

    void startDesktopRuntimeAndLoadWorkspaces();

    return () => {
      cancelled = true;
    };
  }, [loadWorkspaces, preferences.apiBaseUrl]);

  return (
    <div className={`app-shell${preferences.demoMode === "on" ? " is-demo-mode" : ""}`}>
      <UpdateNotice />
      <aside className="sidebar">
        <header className="brand">
          <img
            className="brand-mark-image"
            src="/app-icon.png"
            alt={preferences.productName}
            width={44}
            height={44}
          />
          <div>
            <strong>{preferences.productName}</strong>
            <span>Local-first</span>
          </div>
        </header>

        <div className="sidebar-heading">
          <div>
            <div className="sidebar-title-line">
              <h2>Workspaces</h2>
              <span className="sidebar-workspace-count">{totalWorkspaces}</span>
            </div>
            <p className="sidebar-subtitle">Your local projects</p>
          </div>
          <div className="sidebar-heading-actions">
            <button
              className="text-button"
              type="button"
              onClick={() => setShowCreateWorkspace(true)}
            >
              Add project
            </button>
            <button
              className="text-button"
              type="button"
              onClick={() => void loadWorkspaces()}
            >
              Refresh
            </button>
          </div>
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
          <>
            {archiveError ? (
              <div className="sidebar-alert" role="alert">
                {archiveError}
              </div>
            ) : null}
            <WorkspaceList
              workspaces={workspaces}
              selectedWorkspaceId={selectedWorkspaceId}
              archivedWorkspaces={archivedWorkspaces}
              showArchived={showArchivedWorkspaces}
              archivingWorkspaceId={archivingWorkspaceId}
              restoringWorkspaceId={restoringWorkspaceId}
              deletingWorkspaceId={deletingWorkspaceId}
              clearingIndexWorkspaceId={clearingIndexWorkspaceId}
              onToggleArchived={() => setShowArchivedWorkspaces((current) => !current)}
              onSelect={(workspaceId) => {
                setShowCreateWorkspace(false);
                setResumeMessage(null);
                void loadWorkspaceDetail(workspaceId);
              }}
              onArchive={(workspace) => void handleArchiveWorkspace(workspace)}
              onRestore={(workspace) => void handleRestoreWorkspace(workspace)}
              onDelete={(workspace) => void handleDeleteWorkspace(workspace)}
              onClearIndex={(workspace) => void handleClearWorkspaceIndex(workspace)}
            />
          </>
        )}

        <footer className="sidebar-footer sidebar-footer-simple">
          <span className="sidebar-privacy" title="Your project files are read and answered on this computer. Nothing is uploaded.">
            <svg className="sidebar-privacy-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
              <path
                d="M8 1.5a3 3 0 0 0-3 3V6H4.5A1.5 1.5 0 0 0 3 7.5v5A1.5 1.5 0 0 0 4.5 14h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 6H11V4.5a3 3 0 0 0-3-3Zm1.5 4.5h-3V4.5a1.5 1.5 0 0 1 3 0V6Z"
                fill="currentColor"
              />
            </svg>
            Private — your files stay on this computer
          </span>
          <span>Local backend ready</span>
          <span className="sidebar-version">Version {__APP_VERSION__}</span>
        </footer>
      </aside>

      <main className="main-content">
        {desktopStartupMessage ? (
          <div className="resume-workspace-banner desktop-startup-banner" role="status">
            <span>{desktopStartupMessage}</span>
          </div>
        ) : null}

        {showCreateWorkspace ? (
          <CreateWorkspacePanel
            onCreated={(workspace) => void handleWorkspaceCreated(workspace.id)}
            onCancel={() => setShowCreateWorkspace(false)}
          />
        ) : detailLoading ? (
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
                        <span>{detail.dashboard.recent_events.length + activityJobs.length}</span>
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

            {resumeMessage ? (
              <div className="resume-workspace-banner" role="status">
                <span>{resumeMessage}</span>
                <button type="button" className="ghost-button small" onClick={() => setResumeMessage(null)}>
                  Dismiss
                </button>
              </div>
            ) : null}

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
                  onOpenCapabilities={() => setActiveTab("actions")}
                  onPreviewSavedFileSelection={() => previewWorkspaceFileSelection(detail.dashboard.workspace_id)}
                  onPreviewDraftFileSelection={() => handlePreviewFileSelection(detail.dashboard.workspace_id)}
                  onStartScanJob={() => handleStartScanJob(detail.dashboard.workspace_id)}
                  onStartIndexJob={() => handleStartIndexJob(detail.dashboard.workspace_id)}
                  onGetWorkspaceJob={(jobId) => handleGetWorkspaceJob(detail.dashboard.workspace_id, jobId)}
                  onListWorkspaceJobs={() => handleListWorkspaceJobs(detail.dashboard.workspace_id)}
                  onCancelWorkspaceJob={(jobId) => handleCancelWorkspaceJob(detail.dashboard.workspace_id, jobId)}
                  onRefreshWorkspaceState={() => refreshWorkspaceReadOnlyState(detail.dashboard.workspace_id)}
                  onOpenSettings={() => setActiveTab("settings")}
                  skillPreferences={preferences.skillPreferences}
                  fileIndexingPreferences={preferences.fileIndexingPreferences}
                />
              ) : null}
              <div hidden={activeTab !== "ask"}>
                <AskWorkspace
                  key={detail.dashboard.workspace_id}
                  workspaceId={detail.dashboard.workspace_id}
                  assistantMode={detail.dashboard.assistant_mode}
                  defaultSourceSnippets={preferences.defaultSourceSnippets}
                  skillPreferences={preferences.skillPreferences}
                  skillProfileSource={workspaceSkillProfile?.source ?? "default"}
                  skillProfileUpdatedAt={workspaceSkillProfile?.updated_at ?? null}
                  developerMode={preferences.developerMode}
                  answerTemperature={ANSWER_CREATIVITY_TEMPERATURE[preferences.answerCreativity]}
                  onAsked={() => refreshAfterAsk(detail.dashboard.workspace_id)}
                />
              </div>
              {activeTab === "models" ? (
                <div className="models-tab">
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
                    <RenderCrashBoundary title="Models screen recovered safely">
                      <ModelsDetail
                        workspaceId={detail.dashboard.workspace_id}
                        hasScan={detail.dashboard.summary.has_scan}
                        developerMode={preferences.developerMode}
                        answerCreativity={preferences.answerCreativity}
                        onAnswerCreativityChange={(value) =>
                          setPreferences((current) => ({ ...current, answerCreativity: value }))
                        }
                        dashboard={modelsDetail.dashboard}
                        activationGuide={modelsDetail.activationGuide}
                        onSelectionUpdated={() =>
                          refreshWorkspaceReadOnlyState(detail.dashboard.workspace_id)
                        }
                        onStartIndexJob={() => handleStartIndexJob(detail.dashboard.workspace_id)}
                        onGetWorkspaceJob={(jobId) =>
                          handleGetWorkspaceJob(detail.dashboard.workspace_id, jobId)
                        }
                      />
                    </RenderCrashBoundary>
                  ) : (
                    <ModelsSummaryCard summary={detail.modelsSummary} spacious />
                  )}
                </div>
              ) : null}
              {activeTab === "reports" ? (
                <ReportsPanel
                  workspaceId={detail.dashboard.workspace_id}
                  hasScan={detail.dashboard.summary.has_scan}
                />
              ) : null}
              {activeTab === "actions" ? (
                <UIActionsPanel catalog={detail.actions} />
              ) : null}
              {activeTab === "activity" ? (
                <ActivityTimeline
                  events={detail.dashboard.recent_events}
                  jobs={activityJobs}
                  jobsLoading={activityJobsLoading}
                  jobsError={activityJobsError}
                  onRefreshJobs={() => loadActivityJobs(detail.dashboard.workspace_id)}
                />
              ) : null}
              {activeTab === "settings" ? (
                <SettingsPanel
                  dashboard={detail.dashboard}
                  modelsSummary={detail.modelsSummary}
                  preferences={preferences}
                  onPreferencesChange={setPreferences}
                  onResetPreferences={() => setPreferences(DEFAULT_PREFERENCES)}
                  onOpenModels={() => setActiveTab("models")}
                  onIndexingRulesSaved={() => refreshWorkspaceReadOnlyState(detail.dashboard.workspace_id)}
                  skillProfileSource={workspaceSkillProfile?.source ?? "default"}
                  skillProfileUpdatedAt={workspaceSkillProfile?.updated_at ?? null}
                  onSkillProfileSaved={() => refreshWorkspaceReadOnlyState(detail.dashboard.workspace_id)}
                />
              ) : null}
            </section>
          </div>
        ) : (
          <div className="empty-workspace-start">
            <EmptyState
              title="No projects yet"
              message="The desktop backend is running. Add your first local project to start onboarding."
            />
            <button
              className="primary-action"
              type="button"
              onClick={() => setShowCreateWorkspace(true)}
            >
              Add project
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

function loadStoredPreferences(): WorkbenchPreferences {
  try {
    const raw =
      window.localStorage.getItem(PREFERENCES_STORAGE_KEY) ??
      window.localStorage.getItem(LEGACY_PREFERENCES_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    const parsed = JSON.parse(raw) as Partial<WorkbenchPreferences>;
    return {
      theme: isThemePreference(parsed.theme)
        ? parsed.theme
        : DEFAULT_PREFERENCES.theme,
      density: isDensityPreference(parsed.density)
        ? parsed.density
        : DEFAULT_PREFERENCES.density,
      defaultSourceSnippets: isSourceSnippetPreference(
        parsed.defaultSourceSnippets,
      )
        ? parsed.defaultSourceSnippets
        : DEFAULT_PREFERENCES.defaultSourceSnippets,
      landingTab: isLandingTabPreference(parsed.landingTab)
        ? parsed.landingTab
        : DEFAULT_PREFERENCES.landingTab,
      apiBaseUrl: isApiBaseUrlPreference(parsed.apiBaseUrl)
        ? normalizeApiBaseUrl(parsed.apiBaseUrl)
        : DEFAULT_PREFERENCES.apiBaseUrl,
      brandInitials: isBrandInitialsPreference(parsed.brandInitials)
        ? normalizeBrandInitials(parsed.brandInitials)
        : DEFAULT_PREFERENCES.brandInitials,
      productName: isProductNamePreference(parsed.productName)
        ? normalizeProductName(parsed.productName)
        : DEFAULT_PREFERENCES.productName,
      accentColor: isAccentColorPreference(parsed.accentColor)
        ? parsed.accentColor
        : DEFAULT_PREFERENCES.accentColor,
      demoMode: isDemoModePreference(parsed.demoMode)
        ? parsed.demoMode
        : DEFAULT_PREFERENCES.demoMode,
      developerMode:
        typeof parsed.developerMode === "boolean"
          ? parsed.developerMode
          : DEFAULT_PREFERENCES.developerMode,
      answerCreativity:
        parsed.answerCreativity === "precise" ||
        parsed.answerCreativity === "balanced" ||
        parsed.answerCreativity === "creative"
          ? parsed.answerCreativity
          : DEFAULT_PREFERENCES.answerCreativity,
      skillPreferences: normalizeSkillPreferences(parsed.skillPreferences),
      fileIndexingPreferences: normalizeFileIndexingPreferences(
        parsed.fileIndexingPreferences,
      ),
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function isThemePreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

function isDensityPreference(value: unknown): value is DensityPreference {
  return value === "comfortable" || value === "compact";
}

function isSourceSnippetPreference(value: unknown): value is SourceSnippetPreference {
  return value === 3 || value === 5 || value === 8 || value === 10;
}

function isLandingTabPreference(value: unknown): value is WorkspaceTab {
  return workspaceTabs.some((tab) => tab.id === value);
}

function isApiBaseUrlPreference(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function normalizeApiBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function isProductNamePreference(value: unknown): value is string {
  return typeof value === "string" && normalizeProductName(value).length > 0;
}

function normalizeProductName(value: string): string {
  const normalized = value.trim().replace(/\s+/g, " ").slice(0, 48);
  return normalized || "AI Private Workspace";
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected request error";
}

export default App;


function isBrandInitialsPreference(value: unknown): value is string {
  return typeof value === "string" && normalizeBrandInitials(value).length > 0;
}

function normalizeBrandInitials(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 3) || "AI";
}

function isAccentColorPreference(value: unknown): value is AccentColorPreference {
  return value === "green" || value === "blue" || value === "purple" || value === "orange";
}

function isDemoModePreference(value: unknown): value is DemoModePreference {
  return value === "off" || value === "on";
}
