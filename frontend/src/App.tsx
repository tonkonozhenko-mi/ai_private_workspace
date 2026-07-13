import { useCallback, useEffect, useRef, useState } from "react";

import {
  DEFAULT_API_BASE_URL,
  archiveWorkspace,
  restoreWorkspace,
  deleteWorkspace,
  clearWorkspaceIndex,
  setWorkspacePersistence,
  purgeTemporaryWorkspaces,
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
  updateWorkspaceSkillProfile,
  getWorkspaceUIActions,
  setApiBaseUrl,
  listProjectGroups,
  createProjectGroup,
  addProjectGroupMember,
} from "./api/client";
import type {
  ProjectGroupSummary,
  WorkspaceDetailBundle,
  WorkspaceModelsDetailBundle,
  WorkspaceOverviewItem,
  WorkspaceJob,
  FileSelectionPreview,
  WorkspaceSkillProfile,
} from "./api/types";
import { AskWorkspace } from "./components/AskWorkspace";
import { ActiveDownloads } from "./components/ActiveDownloads";
import { CreateWorkspacePanel } from "./components/CreateWorkspacePanel";
import { ModelsDetail } from "./components/ModelsDetail";
import { ProjectIntelligence } from "./components/ProjectIntelligence";
import { GroupView } from "./components/GroupView";
import { CommandPalette, type PaletteItem } from "./components/CommandPalette";
import { FileInspector } from "./components/FileInspector";
import { RenderCrashBoundary } from "./components/RenderCrashBoundary";
import { ModelsSummaryCard } from "./components/ModelsSummaryCard";
import { ReportsPanel } from "./components/ReportsPanel";
import { ActivityTimeline } from "./components/ActivityTimeline";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { LoadingState } from "./components/LoadingState";
import { UIActionsPanel } from "./components/UIActionsPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { ensureAppOwnedBackendRuntime, isRunningInsideTauri, tauriBridgeDiagnostic, registerDesktopCloseGuard, closeDesktopWindow } from "./desktopRuntime";
import { WorkspaceDashboard } from "./components/WorkspaceDashboard";
import { WorkspaceGettingReady } from "./components/WorkspaceGettingReady";
import { WorkspaceList } from "./components/WorkspaceList";
import {
  DEFAULT_FILE_INDEXING_PREFERENCES,
  normalizeFileIndexingPreferences,
  toFileSelectionRulesRequest,
  type FileIndexingPreferences,
} from "./components/fileIndexingPreferences";
import { DEFAULT_CUSTOM_SKILLS, DEFAULT_SKILL_PREFERENCES, normalizeCustomSkills, normalizeSkillPreferences, skillPreferencesFromProfile, skillPreferencesForRole, toSkillProfileRequest, type CustomSkill, type SkillPreferences } from "./components/skillLibrary";
import UpdateNotice from "./components/UpdateNotice";
import {
  ANSWER_CREATIVITY_TEMPERATURE,
  DEFAULT_PREFERENCES,
  usePreferences,
  useResolvedTheme,
  type WorkbenchPreferences,
} from "./preferences";
import { useWorkspaceJobs } from "./hooks/useWorkspaceJobs";
import { useSidebarCollapsed } from "./hooks/useSidebarCollapsed";
import { useCommandPalette } from "./hooks/useCommandPalette";
import { errorMessage } from "./lib/errorMessage";
import { NavIcon, FirstRunWelcome } from "./components/AppChrome";
import { TabCaption, isTourDone, markTourDone } from "./components/StartHere";
import { SpotlightTour, type TourStep } from "./components/SpotlightTour";

// The guided first-run tour points at each workspace tab (they carry
// data-tab-id), so a new user learns what each section is for in place.
const WORKSPACE_TOUR_STEPS: TourStep[] = [
  {
    selector: '[data-tour-id="projects"]',
    title: "Your projects",
    body: "This button opens the list of your projects and groups. It's tucked away by default to keep things calm — click it anytime to switch projects, add a new one, or make a group.",
  },
  {
    selector: '[data-tab-id="overview"]',
    title: "Home",
    body: "Your project at a glance — status, what changed, and the next thing to do.",
  },
  {
    selector: '[data-tab-id="intelligence"]',
    title: "Intelligence",
    body: "The map of your project — architecture, risks and the environments the app found.",
  },
  {
    selector: '[data-tab-id="models"]',
    title: "Models",
    body: "Download, switch or remove the local AI models. Everything runs on your machine.",
  },
  {
    selector: '[data-tab-id="settings"]',
    title: "Settings",
    body: "Appearance and behaviour — tune the app to how you like to work.",
  },
  // End on the thing to do next, not a settings screen: the tour finishes on Ask
  // and closing it lands the user right in the composer with a first-question nudge.
  {
    selector: '[data-tab-id="ask"]',
    title: "Ask your first question",
    body: "Ask anything about your project in plain words — the suggestions here are built from your own files, and every answer stays on your machine. Finish to start.",
  },
];

import type { WorkspaceTab } from "./components/appTabs";
import { workspaceTabs } from "./components/appTabs";
export type { WorkspaceTab };

const LAST_WORKSPACE_STORAGE_KEY = "ai-private-workspace.last-workspace-id.v1";

// Preference types, defaults, persistence and the usePreferences hook moved to
// ./preferences. Re-exported here so existing imports (e.g. SettingsPanel) keep
// working through the App module.
export type {
  WorkbenchPreferences,
  AnswerCreativityPreference,
} from "./preferences";
export { ANSWER_CREATIVITY_TEMPERATURE } from "./preferences";




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
  const [groups, setGroups] = useState<ProjectGroupSummary[]>([]);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [dropTargetGroupId, setDropTargetGroupId] = useState<string | null>(null);
  // A freshly created group opens in rename mode so it can be named right away.
  const [autoRenameGroupId, setAutoRenameGroupId] = useState<string | null>(null);
  const [inspectFilePath, setInspectFilePath] = useState<string | null>(null);
  // A question pushed into Ask from a dashboard suggested-question chip.
  const [askSeed, setAskSeed] = useState<{ text: string; nonce: number } | null>(null);
  const openAskWithQuestion = (text: string) => {
    setAskSeed({ text, nonce: Date.now() });
    setActiveTab("ask");
  };

  // The workspace role and the Ask answer style are one thing: when the role is
  // changed (on Intelligence), make that role the single active skill and save
  // it, then reload so Ask, its focus panel, and the dashboard all match.
  const handleRolePersisted = async (workspaceId: string, mode: string) => {
    try {
      const nextSkills = skillPreferencesForRole(mode, preferences.skillPreferences);
      await updateWorkspaceSkillProfile(workspaceId, toSkillProfileRequest(nextSkills));
    } catch {
      // Persisting the skill is best-effort; the lens already changed.
    }
    await loadWorkspaceDetail(workspaceId);
  };

  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
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
  const [tourOpen, setTourOpen] = useState(false);
  const [setupTakeoverDismissed, setSetupTakeoverDismissed] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useSidebarCollapsed();
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [archivingWorkspaceId, setArchivingWorkspaceId] = useState<string | null>(null);
  const [restoringWorkspaceId, setRestoringWorkspaceId] = useState<string | null>(null);
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState<string | null>(null);
  const [clearingIndexWorkspaceId, setClearingIndexWorkspaceId] = useState<string | null>(null);
  const [keepingWorkspaceId, setKeepingWorkspaceId] = useState<string | null>(null);
  const [exitPrompt, setExitPrompt] = useState<{ count: number; context: "quit" | "launch" } | null>(null);
  const [purgingTemporary, setPurgingTemporary] = useState(false);
  const temporaryWorkspacesRef = useRef<WorkspaceOverviewItem[]>([]);
  const launchPromptShownRef = useRef(false);
  const [showArchivedWorkspaces, setShowArchivedWorkspaces] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const { preferences, setPreferences } = usePreferences();
  // Pick the logo that matches the appearance actually on screen (dark logo on
  // dark theme, light logo on light theme; follows the OS when theme = system).
  const brandLogoSrc =
    useResolvedTheme(preferences.theme) === "dark" ? "/app-icon-dark.png" : "/app-icon.png";
  const { activityJobs, activityJobsLoading, activityJobsError, loadActivityJobs } =
    useWorkspaceJobs({ activeTab, selectedWorkspaceId, selectedWorkspaceIdRef });
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

  // The "restored last workspace" note is a brief welcome-back confirmation;
  // fade it on its own instead of making the user dismiss it.
  useEffect(() => {
    if (!resumeMessage) {
      return;
    }
    const timer = window.setTimeout(() => setResumeMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [resumeMessage]);

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
      temporaryWorkspacesRef.current = allOverview.items.filter(
        (workspace) => workspace.persistence === "temporary",
      );
      // On the first load of an app session, surface any temporary projects left
      // over from a previous session so the user can keep or forget them. This is
      // the reliable counterpart to the (best-effort) window close guard.
      if (!launchPromptShownRef.current) {
        launchPromptShownRef.current = true;
        const leftoverTemporary = temporaryWorkspacesRef.current.length;
        if (leftoverTemporary > 0) {
          setExitPrompt({ count: leftoverTemporary, context: "launch" });
        }
      }
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
    setSelectedGroupId(null);
    await loadWorkspaces();
    await loadWorkspaceDetail(workspaceId);
    setActiveTab("overview");
  }, [loadWorkspaceDetail, loadWorkspaces]);

  // --- Project groups (several repos treated as one project) ---
  const loadGroups = useCallback(async () => {
    try {
      const res = await listProjectGroups();
      setGroups(res.groups);
    } catch {
      // Groups are optional; a backend without them shouldn't break the app.
    }
  }, []);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  const { paletteOpen, setPaletteOpen, paletteFiles } = useCommandPalette({
    selectedWorkspaceId,
    selectedGroupId,
  });

  const handleSelectGroup = useCallback((groupId: string) => {
    setShowCreateWorkspace(false);
    setResumeMessage(null);
    setSelectedGroupId(groupId);
    setSelectedWorkspaceId(null);
    selectedWorkspaceIdRef.current = null;
    setDetail(null);
  }, []);

  // Native window.prompt is disabled inside the Tauri webview (it returns null),
  // so group creation must use an in-app input rather than a browser prompt.
  const handleCreateGroup = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) return;
      try {
        const group = await createProjectGroup(trimmed, []);
        setNewGroupName("");
        setCreatingGroup(false);
        await loadGroups();
        handleSelectGroup(group.id);
      } catch {
        // Surface nothing destructive; creation failures are non-fatal here.
      }
    },
    [loadGroups, handleSelectGroup],
  );

  const handleAddWorkspaceToGroup = useCallback(
    async (workspace: WorkspaceOverviewItem, groupId: string) => {
      const group = groups.find((g) => g.id === groupId);
      // Already a member — just open the group instead of a redundant call.
      if (group && group.workspace_ids.includes(workspace.workspace_id)) {
        handleSelectGroup(groupId);
        return;
      }
      try {
        await addProjectGroupMember(groupId, workspace.workspace_id);
        await loadGroups();
        handleSelectGroup(groupId);
      } catch {
        // non-fatal
      }
    },
    [groups, loadGroups, handleSelectGroup],
  );

  const handleCreateGroupWith = useCallback(
    async (workspace: WorkspaceOverviewItem) => {
      try {
        const group = await createProjectGroup(`${workspace.name} group`, [workspace.workspace_id]);
        await loadGroups();
        setAutoRenameGroupId(group.id);
        handleSelectGroup(group.id);
      } catch {
        // non-fatal
      }
    },
    [loadGroups, handleSelectGroup],
  );

  // Drag one project onto another → make a group containing both. If a group
  // already contains *both* projects, don't create a duplicate — just open it.
  // The check uses a *fresh* group list (not React state, which can be empty if
  // the initial load lost a race with backend startup) so it never duplicates.
  const handleDropWorkspaceOnWorkspace = useCallback(
    async (sourceWorkspaceId: string, targetWorkspaceId: string) => {
      let current = groups;
      try {
        current = (await listProjectGroups()).groups;
        setGroups(current);
      } catch {
        // fall back to whatever is in state
      }
      const existing = current.find(
        (g) =>
          g.workspace_ids.includes(sourceWorkspaceId) &&
          g.workspace_ids.includes(targetWorkspaceId),
      );
      if (existing) {
        handleSelectGroup(existing.id);
        return;
      }
      const target = workspaces.find((w) => w.workspace_id === targetWorkspaceId);
      const name = target ? `${target.name} group` : "New group";
      try {
        const group = await createProjectGroup(name, [targetWorkspaceId, sourceWorkspaceId]);
        await loadGroups();
        setAutoRenameGroupId(group.id);
        handleSelectGroup(group.id);
      } catch {
        // non-fatal
      }
    },
    [groups, workspaces, loadGroups, handleSelectGroup],
  );

  // Drag a project onto an existing group chip → add it there (skip if already in).
  const handleDropWorkspaceOnGroup = useCallback(
    async (groupId: string, workspaceId: string) => {
      const group = groups.find((g) => g.id === groupId);
      if (group && group.workspace_ids.includes(workspaceId)) {
        handleSelectGroup(groupId);
        return;
      }
      try {
        await addProjectGroupMember(groupId, workspaceId);
        await loadGroups();
        handleSelectGroup(groupId);
      } catch {
        // non-fatal
      }
    },
    [loadGroups, handleSelectGroup],
  );


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

  const handleKeepWorkspace = useCallback(async (workspace: WorkspaceOverviewItem) => {
    setKeepingWorkspaceId(workspace.workspace_id);
    setArchiveError(null);
    try {
      await setWorkspacePersistence(workspace.workspace_id, "saved");
      await loadWorkspaces();
    } catch (error) {
      setArchiveError(`Could not keep ${workspace.name}: ${errorMessage(error)}`);
    } finally {
      setKeepingWorkspaceId(null);
    }
  }, [loadWorkspaces]);

  // Ask before quitting when there are temporary projects to forget.
  useEffect(() => {
    let unlisten: (() => void) | null = null;
    let active = true;
    void registerDesktopCloseGuard((event) => {
      const temporaries = temporaryWorkspacesRef.current;
      if (temporaries.length === 0) {
        return; // nothing to forget — let the window close normally
      }
      event.preventDefault();
      setExitPrompt({ count: temporaries.length, context: "quit" });
    }).then((fn) => {
      if (!active && fn) {
        fn();
      } else {
        unlisten = fn;
      }
    });
    return () => {
      active = false;
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  const handleDeleteTemporaryAndQuit = useCallback(async () => {
    setPurgingTemporary(true);
    try {
      await purgeTemporaryWorkspaces();
    } catch {
      // Even if purge fails, honor the quit; data stays marked temporary.
    } finally {
      setPurgingTemporary(false);
      setExitPrompt(null);
      await closeDesktopWindow();
    }
  }, []);

  const handleKeepTemporaryAndQuit = useCallback(async () => {
    setExitPrompt(null);
    await closeDesktopWindow();
  }, []);

  // Launch-time prompt: forget leftover temporary projects now, or keep them.
  const handleForgetTemporaryNow = useCallback(async () => {
    setPurgingTemporary(true);
    try {
      await purgeTemporaryWorkspaces();
      await loadWorkspaces();
    } catch (error) {
      setArchiveError(`Could not delete temporary projects: ${errorMessage(error)}`);
    } finally {
      setPurgingTemporary(false);
      setExitPrompt(null);
    }
  }, [loadWorkspaces]);



  const handlePreviewFileSelection = useCallback((workspaceId: string): Promise<FileSelectionPreview> => {
    return previewWorkspaceFileSelection(
      workspaceId,
      toFileSelectionRulesRequest(preferences.fileIndexingPreferences),
    );
  }, [preferences.fileIndexingPreferences]);

  // Poll a scan/index job to completion and then refresh the workspace so the
  // Home cards update on their own — robust even for jobs that finish too fast
  // for the on-screen poller to catch.
  const pollSetupJobThenRefresh = useCallback(
    async (workspaceId: string, jobId: string) => {
      for (let attempt = 0; attempt < 600; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        try {
          const job = await getWorkspaceJob(workspaceId, jobId);
          if (["completed", "failed", "cancelled"].includes(job.status)) {
            if (selectedWorkspaceIdRef.current === workspaceId) {
              await refreshWorkspaceReadOnlyState(workspaceId);
            }
            return;
          }
        } catch {
          // transient error: keep polling for a while before giving up
        }
      }
    },
    [refreshWorkspaceReadOnlyState],
  );

  const handleStartScanJob = useCallback(async (workspaceId: string): Promise<WorkspaceJob> => {
    const job = await startScanWorkspaceJob(workspaceId);
    void pollSetupJobThenRefresh(workspaceId, job.job_id);
    return job;
  }, [pollSetupJobThenRefresh]);

  const handleStartIndexJob = useCallback(async (workspaceId: string): Promise<WorkspaceJob> => {
    const job = await startIndexWorkspaceJob(workspaceId);
    void pollSetupJobThenRefresh(workspaceId, job.job_id);
    return job;
  }, [pollSetupJobThenRefresh]);

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
        // Load groups only once the backend is reachable — the early mount-time
        // load can fire before the desktop backend is up and fail silently,
        // leaving the groups list empty until something else refreshes it.
        if (!cancelled) await loadGroups();
      }
    }

    void startDesktopRuntimeAndLoadWorkspaces();

    return () => {
      cancelled = true;
    };
  }, [loadWorkspaces, loadGroups, preferences.apiBaseUrl]);

  // A newly selected/created workspace should re-engage the immersive setup
  // takeover (a previous "Skip for now" must not leak across workspaces).
  useEffect(() => {
    setSetupTakeoverDismissed(false);
    setSetupCelebration(false);
    takeoverWasActiveRef.current = false;
  }, [selectedWorkspaceId]);


  const setupComplete = detail
    ? detail.dashboard.summary.has_scan &&
      detail.dashboard.summary.index_status.status === "indexed" &&
      detail.modelsSummary.can_search_with_selected_embedding &&
      detail.modelsSummary.can_ask_with_selected_llm
    : true;

  // The immersive setup takeover is for a *brand-new* workspace that has not been
  // scanned and indexed yet. Once a project has been indexed at least once, things
  // like switching the search model (which needs a one-off reindex) must NOT yank
  // the user back into the full-screen flow — they stay in the app and use the
  // in-tab "rebuild context" prompt instead.
  const needsInitialSetup = detail
    ? !detail.dashboard.summary.has_scan ||
      detail.dashboard.summary.index_status.status !== "indexed"
    : false;

  // When the immersive setup finishes, don't yank the takeover away mid-frame:
  // keep it mounted one more beat so the "Everything's set — ask anything"
  // completion screen actually shows (it existed but was never visible —
  // needsInitialSetup flipped false and unmounted it instantly). Ask is
  // prepared behind it; the user leaves by pressing the CTA.
  const takeoverWasActiveRef = useRef(false);
  const [setupCelebration, setSetupCelebration] = useState(false);
  useEffect(() => {
    if (setupComplete && takeoverWasActiveRef.current) {
      takeoverWasActiveRef.current = false;
      setSidebarCollapsed(true);
      // First landing after setup: run the guided tour once. Otherwise celebrate
      // and drop the user straight into Ask, as before.
      if (!isTourDone()) {
        setActiveTab("overview");
        setTourOpen(true);
      } else {
        setSetupCelebration(true);
        setActiveTab("ask");
      }
    }
  }, [setupComplete]);

  const closeTour = () => {
    markTourDone();
    setTourOpen(false);
    // The tour ends on Ask, so leave the user there — pointed at the action, not
    // back on whatever tab was open when it started.
    setActiveTab("ask");
  };

  // Replay the guided tour on demand (command palette or the Settings link). Starts
  // from Home with the sidebar collapsed so the very first step can spotlight the
  // projects button, exactly like the first-run autostart.
  const startTour = () => {
    setActiveTab("overview");
    setSidebarCollapsed(true);
    setTourOpen(true);
  };

  // Also run the guided tour the first time an *already-set-up* project is opened
  // (the effect above only fires right after fresh setup). Once per app session and
  // only until the tour is finished or skipped, so it never nags. The "Take a quick
  // tour" link on Home replays it anytime.
  const autoTourTriedRef = useRef(false);
  useEffect(() => {
    if (autoTourTriedRef.current) return;
    if (!detail || selectedGroupId || needsInitialSetup) return;
    if (isTourDone()) return;
    autoTourTriedRef.current = true;
    setActiveTab("overview");
    setSidebarCollapsed(true); // so the projects step can spotlight the reveal button
    setTourOpen(true);
  }, [detail, selectedGroupId, needsInitialSetup, setSidebarCollapsed]);

  const isFirstRun =
    !workspacesLoading &&
    !workspacesError &&
    workspaces.length === 0 &&
    archivedWorkspaces.length === 0 &&
    !showCreateWorkspace;

  if (isFirstRun) {
    return (
      <FirstRunWelcome
        productName={preferences.productName}
        onOpen={() => setShowCreateWorkspace(true)}
        logoSrc={brandLogoSrc}
      />
    );
  }

  // Creating a workspace is a focused, full-window task — hide the sidebar
  // (which only says "no projects" at this point and adds no value).
  if (showCreateWorkspace) {
    return (
      <div className="setup-takeover">
        <UpdateNotice />
        <div className="setup-takeover-body create-takeover-body">
          <CreateWorkspacePanel
            onCreated={(workspace) => void handleWorkspaceCreated(workspace.id)}
            onCancel={() => setShowCreateWorkspace(false)}
          />
        </div>
      </div>
    );
  }

  // ---- Full-window setup takeover ---------------------------------------
  // A brand-new / not-yet-ready workspace gets an immersive, distraction-free
  // setup flow (no sidebar, no tabs) — like the first-run screen. A subtle
  // "Skip for now" returns to the full app shell.
  if (
    detail &&
    !detailLoading &&
    !detailError &&
    (needsInitialSetup || setupCelebration) &&
    !setupTakeoverDismissed &&
    !exitPrompt
  ) {
    if (needsInitialSetup) takeoverWasActiveRef.current = true;
    const ws = detail.dashboard.workspace_id;
    return (
      <div className="setup-takeover">
        <UpdateNotice />
        <div className="setup-takeover-bar">
          <div className="setup-takeover-brand">
            <img src={brandLogoSrc} alt={preferences.productName} width={28} height={28} />
            <span>{detail.dashboard.workspace_name}</span>
          </div>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setSetupTakeoverDismissed(true);
              setSetupCelebration(false);
            }}
          >
            Skip for now
          </button>
        </div>
        <div className="setup-takeover-body">
          <WorkspaceGettingReady
            dashboard={detail.dashboard}
            modelsSummary={detail.modelsSummary}
            onOpenAsk={() => {
              setSetupTakeoverDismissed(true);
              setSetupCelebration(false);
              setActiveTab("ask");
            }}
            onOpenModels={() => {
              setSetupTakeoverDismissed(true);
              setSetupCelebration(false);
              setActiveTab("models");
            }}
            onStartScanJob={() => handleStartScanJob(ws)}
            onStartIndexJob={() => handleStartIndexJob(ws)}
            onRefreshWorkspaceState={() => refreshWorkspaceReadOnlyState(ws)}
          />
        </div>
      </div>
    );
  }

  const selectWorkspaceFromPalette = (workspaceId: string) => {
    setShowCreateWorkspace(false);
    setResumeMessage(null);
    setSelectedGroupId(null);
    void loadWorkspaceDetail(workspaceId);
  };

  const paletteItems: PaletteItem[] = [
    ...(selectedWorkspaceId && !selectedGroupId
      ? workspaceTabs.map((t) => ({
          id: t.id,
          kind: "tab" as const,
          label: t.label,
          sub: "section",
          run: () => setActiveTab(t.id),
        }))
      : []),
    ...(selectedWorkspaceId && !selectedGroupId
      ? [
          {
            id: "__take_tour__",
            kind: "tab" as const,
            label: "Take a quick tour",
            sub: "help",
            run: startTour,
          },
        ]
      : []),
    ...workspaces.map((w) => ({
      id: w.workspace_id,
      kind: "repo" as const,
      label: w.name,
      sub: w.project_path,
      run: () => selectWorkspaceFromPalette(w.workspace_id),
    })),
    ...groups.map((g) => ({
      id: g.id,
      kind: "group" as const,
      label: g.name,
      sub: `${g.member_count} ${g.member_count === 1 ? "repo" : "repos"}`,
      run: () => handleSelectGroup(g.id),
    })),
    ...(selectedWorkspaceId && !selectedGroupId
      ? paletteFiles.map((p) => ({
          id: p,
          kind: "file" as const,
          label: p.split("/").pop() ?? p,
          sub: p,
          run: () => setInspectFilePath(p),
        }))
      : []),
  ];

  return (
    <div
      className={`app-shell${preferences.demoMode === "on" ? " is-demo-mode" : ""}${
        sidebarCollapsed ? " is-sidebar-collapsed" : ""
      }`}
    >
      <UpdateNotice />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={paletteItems} />
      {inspectFilePath && selectedWorkspaceId ? (
        <FileInspector
          workspaceId={selectedWorkspaceId}
          path={inspectFilePath}
          role={detail?.dashboard.assistant_mode}
          onClose={() => setInspectFilePath(null)}
        />
      ) : null}
      {tourOpen && detail && !selectedGroupId ? (
        <SpotlightTour steps={WORKSPACE_TOUR_STEPS} onClose={closeTour} />
      ) : null}
      {sidebarCollapsed ? (
        <button
          className="sidebar-reveal"
          type="button"
          title="Show projects"
          aria-label="Show projects"
          data-tour-id="projects"
          onClick={() => setSidebarCollapsed(false)}
        >
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      ) : null}
      <aside className="sidebar">
        <header className="brand">
          <img
            className="brand-mark-image"
            src={brandLogoSrc}
            alt={preferences.productName}
            width={44}
            height={44}
          />
          <div>
            <strong>{preferences.productName}</strong>
            <span>Local-first</span>
          </div>
          <button
            className="sidebar-collapse-button"
            type="button"
            title="Hide sidebar"
            aria-label="Hide sidebar"
            onClick={() => setSidebarCollapsed(true)}
          >
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M15 6l-6 6 6 6" />
            </svg>
          </button>
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
              className="icon-button"
              type="button"
              data-tip="Refresh projects"
              aria-label="Refresh projects"
              onClick={() => void loadWorkspaces()}
            >
              <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                <path d="M21 4v5h-5" />
              </svg>
            </button>
            <button
              className="icon-button sidebar-new-project-icon"
              type="button"
              data-tip="New project"
              data-tip-align="end"
              aria-label="New project"
              onClick={() => setShowCreateWorkspace(true)}
            >
              <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
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
              keepingWorkspaceId={keepingWorkspaceId}
              groups={groups}
              onAddToGroup={(workspace, groupId) => void handleAddWorkspaceToGroup(workspace, groupId)}
              onCreateGroupWith={(workspace) => void handleCreateGroupWith(workspace)}
              onDropWorkspaceOnWorkspace={(sourceId, targetId) => void handleDropWorkspaceOnWorkspace(sourceId, targetId)}
              onToggleArchived={() => setShowArchivedWorkspaces((current) => !current)}
              onSelect={(workspaceId) => {
                setShowCreateWorkspace(false);
                setResumeMessage(null);
                setSelectedGroupId(null);
                void loadWorkspaceDetail(workspaceId);
              }}
              onArchive={(workspace) => void handleArchiveWorkspace(workspace)}
              onRestore={(workspace) => void handleRestoreWorkspace(workspace)}
              onDelete={(workspace) => void handleDeleteWorkspace(workspace)}
              onClearIndex={(workspace) => void handleClearWorkspaceIndex(workspace)}
              onKeep={(workspace) => void handleKeepWorkspace(workspace)}
            />
          </>
        )}

        <div className="sidebar-groups">
          <div className="sidebar-groups-head">
            <span className="sidebar-groups-title">Groups</span>
            <button
              type="button"
              className="icon-button"
              data-tip="New group"
              aria-label="New group"
              onClick={() => {
                setCreatingGroup((v) => !v);
                setNewGroupName("");
              }}
            >
              <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </div>
          {creatingGroup ? (
            <div className="sidebar-group-create">
              <input
                className="sidebar-group-input"
                type="text"
                value={newGroupName}
                autoFocus
                placeholder="Group name…"
                onChange={(e) => setNewGroupName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleCreateGroup(newGroupName);
                  if (e.key === "Escape") {
                    setCreatingGroup(false);
                    setNewGroupName("");
                  }
                }}
              />
              <button
                type="button"
                className="sidebar-group-create-btn"
                disabled={newGroupName.trim().length === 0}
                onClick={() => void handleCreateGroup(newGroupName)}
              >
                Create
              </button>
            </div>
          ) : null}
          {groups.length === 0 ? (
            <p className="sidebar-groups-empty">Combine repositories into one project.</p>
          ) : (
            <ul className="sidebar-groups-list">
              {groups.map((group) => (
                <li key={group.id}>
                  <button
                    type="button"
                    className={`sidebar-group${selectedGroupId === group.id ? " is-active" : ""}${dropTargetGroupId === group.id ? " is-drop-target" : ""}`}
                    onClick={() => handleSelectGroup(group.id)}
                    onDragOver={(e) => {
                      if (!e.dataTransfer.types.includes("application/x-aiworkspace-id")) return;
                      e.preventDefault();
                      setDropTargetGroupId(group.id);
                    }}
                    onDragLeave={() => setDropTargetGroupId((id) => (id === group.id ? null : id))}
                    onDrop={(e) => {
                      setDropTargetGroupId(null);
                      const workspaceId = e.dataTransfer.getData("application/x-aiworkspace-id");
                      if (workspaceId) {
                        e.preventDefault();
                        void handleDropWorkspaceOnGroup(group.id, workspaceId);
                      }
                    }}
                  >
                    <span className="sidebar-group-name">{group.name}</span>
                    <span className="sidebar-group-count">{group.member_count}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <ActiveDownloads />

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
        ) : selectedGroupId ? (
          <GroupView
            key={selectedGroupId}
            groupId={selectedGroupId}
            groupName={groups.find((g) => g.id === selectedGroupId)?.name ?? "Group"}
            allWorkspaces={workspaces.map((w) => ({ id: w.workspace_id, name: w.name }))}
            autoRename={autoRenameGroupId === selectedGroupId}
            onChanged={() => void loadGroups()}
            onDeleted={() => setSelectedGroupId(null)}
            onAutoRenameHandled={() => setAutoRenameGroupId(null)}
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
                      <NavIcon id={tab.id} />
                      {tab.label}
                      {tab.id === "activity" ? (
                        <span>{detail.dashboard.recent_events.length + activityJobs.length}</span>
                      ) : null}
                    </button>
                  ))}
                </div>
              </nav>
              <div
                className="workspace-context-chip"
                aria-label={`Current project: ${detail.dashboard.workspace_name}, ${
                  detail.modelsSummary.can_ask_with_selected_llm ? "ready to chat" : "not ready"
                }`}
                title={
                  detail.modelsSummary.can_ask_with_selected_llm
                    ? "Ready to chat with the local AI"
                    : "Not ready — finish setup to chat"
                }
              >
                <span
                  className={`ws-status-dot${
                    detail.modelsSummary.can_ask_with_selected_llm ? " is-ready" : " is-offline"
                  }`}
                  aria-hidden="true"
                />
                <span className="ws-chip-name">{detail.dashboard.workspace_name}</span>
              </div>
            </header>

            <TabCaption tab={activeTab} />

            {resumeMessage ? (
              <div className="resume-workspace-banner" role="status">
                <span>{resumeMessage}</span>
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
                  onInspectFile={(p) => setInspectFilePath(p)}
                  onOpenAsk={() => setActiveTab("ask")}
                  onAskQuestion={openAskWithQuestion}
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
              {activeTab === "intelligence" ? (
                <ProjectIntelligence
                  dashboard={detail.dashboard}
                  onInspectFile={(p) => setInspectFilePath(p)}
                  onAskQuestion={openAskWithQuestion}
                  onRolePersisted={(mode) =>
                    handleRolePersisted(detail.dashboard.workspace_id, mode)
                  }
                />
              ) : null}
              <div hidden={activeTab !== "ask"}>
                <AskWorkspace
                  key={detail.dashboard.workspace_id}
                  workspaceId={detail.dashboard.workspace_id}
                  assistantMode={detail.dashboard.assistant_mode}
                  defaultSourceSnippets={preferences.defaultSourceSnippets}
                  skillPreferences={preferences.skillPreferences}
                  customSkills={preferences.customSkills}
                  skillProfileSource={workspaceSkillProfile?.source ?? "default"}
                  skillProfileUpdatedAt={workspaceSkillProfile?.updated_at ?? null}
                  developerMode={preferences.developerMode}
                  answerTemperature={ANSWER_CREATIVITY_TEMPERATURE[preferences.answerCreativity]}
                  defaultReasoning={preferences.defaultReasoning}
                  defaultStreaming={preferences.defaultStreaming}
                  onAsked={() => refreshAfterAsk(detail.dashboard.workspace_id)}
                  onOpenModels={() => setActiveTab("models")}
                  onOpenOverview={() => setActiveTab("overview")}
                  seedQuestion={askSeed}
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
                  onStartTour={startTour}
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
      {exitPrompt ? (
        <div className="exit-prompt-backdrop" role="presentation">
          <div
            className="exit-prompt"
            role="dialog"
            aria-modal="true"
            aria-labelledby="exit-prompt-title"
          >
            <h2 id="exit-prompt-title">
              {exitPrompt.context === "launch"
                ? "Temporary projects from last session"
                : "Before you quit"}
            </h2>
            <p>
              You have {exitPrompt.count} temporary{" "}
              {exitPrompt.count === 1 ? "project" : "projects"}. Temporary projects
              are meant to be forgotten between sessions. What would you like to do?
            </p>
            {exitPrompt.context === "launch" ? (
              <div className="exit-prompt-actions">
                <button
                  type="button"
                  className="primary-action is-danger"
                  disabled={purgingTemporary}
                  onClick={() => void handleForgetTemporaryNow()}
                >
                  {purgingTemporary ? "Forgetting…" : "Forget them"}
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  disabled={purgingTemporary}
                  onClick={() => setExitPrompt(null)}
                >
                  Keep for now
                </button>
              </div>
            ) : (
              <div className="exit-prompt-actions">
                <button
                  type="button"
                  className="primary-action is-danger"
                  disabled={purgingTemporary}
                  onClick={() => void handleDeleteTemporaryAndQuit()}
                >
                  {purgingTemporary ? "Deleting…" : "Delete & quit"}
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  disabled={purgingTemporary}
                  onClick={() => void handleKeepTemporaryAndQuit()}
                >
                  Keep & quit
                </button>
                <button
                  type="button"
                  className="text-button"
                  disabled={purgingTemporary}
                  onClick={() => setExitPrompt(null)}
                >
                  Cancel
                </button>
              </div>
            )}
            {exitPrompt.context === "launch" ? (
              <p className="exit-prompt-hint">
                Tip: open Manage on a project and choose “Keep forever” to make it
                permanent.
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;

