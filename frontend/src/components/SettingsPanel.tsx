import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { WorkbenchPreferences } from "../App";
import { DEFAULT_API_BASE_URL } from "../api/client";
import { createDatabaseBackup, getDatabaseBackups, getDatabaseMigrationSafety, getDatabaseRestorePlan, getDesktopStartupExperience, getProductionReadiness, getLocalDataSafety, getRuntimeTroubleshooting, getSafeUpdateWorkflow, getStartupChecklist, previewWorkspaceFileSelection, updateWorkspaceIndexingRules, updateWorkspaceSkillProfile } from "../api/client";
import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
  FileSelectionPreview,
  DatabaseBackupList,
  DatabaseMigrationSafety,
  DatabaseRestorePlan,
  LocalDataSafety,
  StartupChecklist,
  RuntimeTroubleshooting,
  SafeUpdateWorkflow,
  DesktopStartupExperience,
  ProductionReadiness,
} from "../api/types";
import {
  DEFAULT_FILE_INDEXING_PREFERENCES,
  countPatterns,
  normalizeFileIndexingPreferences,
  normalizePatternText,
  toFileSelectionRulesRequest,
} from "./fileIndexingPreferences";
import { StatusBadge } from "./StatusBadge";
import {
  DEFAULT_SKILL_PREFERENCES,
  SKILL_PRESETS,
  SKILL_PROFILE_TEMPLATES,
  applySkillProfileTemplate,
  normalizeSkillPreferences,
  toSkillProfileRequest,
  type SkillPresetId,
  type SkillPreferences,
  type SkillProfileTemplateId,
} from "./skillLibrary";

type BrandingPresetId = "default" | "company_coe" | "devops_lab" | "client_demo";

interface BrandingPreset {
  id: BrandingPresetId;
  label: string;
  description: string;
  productName: string;
  brandInitials: string;
  accentColor: WorkbenchPreferences["accentColor"];
}

const BRANDING_PRESETS: BrandingPreset[] = [
  {
    id: "default",
    label: "AI Private",
    description: "Neutral product identity for local personal use.",
    productName: "AI Private Workspace",
    brandInitials: "AI",
    accentColor: "green",
  },
  {
    id: "company_coe",
    label: "Company CoE",
    description: "Calm blue preset for internal demos and enablement sessions.",
    productName: "CoE AI Workspace",
    brandInitials: "CoE",
    accentColor: "blue",
  },
  {
    id: "devops_lab",
    label: "DevOps Lab",
    description: "Purple technical workspace preset for engineering reviews.",
    productName: "DevOps AI Workspace",
    brandInitials: "DO",
    accentColor: "purple",
  },
  {
    id: "client_demo",
    label: "Client Demo",
    description: "Orange preset for temporary demo environments.",
    productName: "Private Client Workspace",
    brandInitials: "CD",
    accentColor: "orange",
  },
];

interface SettingsPanelProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  preferences: WorkbenchPreferences;
  onPreferencesChange: (preferences: WorkbenchPreferences) => void;
  onResetPreferences: () => void;
  onOpenModels: () => void;
  onIndexingRulesSaved?: () => void;
  skillProfileSource?: string;
  skillProfileUpdatedAt?: string | null;
  onSkillProfileSaved?: () => void;
}

export function SettingsPanel({
  dashboard,
  modelsSummary,
  preferences,
  onPreferencesChange,
  onResetPreferences,
  onOpenModels,
  onIndexingRulesSaved,
  skillProfileSource = "default",
  skillProfileUpdatedAt = null,
  onSkillProfileSaved,
}: SettingsPanelProps) {
  const summary = dashboard.summary;
  const contextReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
  const [resetRequested, setResetRequested] = useState(false);
  const [savedMessage, setSavedMessage] = useState("Saved in this browser");
  const [importDraft, setImportDraft] = useState("");
  const [transferMessage, setTransferMessage] = useState(
    "Backup tools are hidden until needed.",
  );
  const [backupToolsVisible, setBackupToolsVisible] = useState(false);
  const [backendUrlDraft, setBackendUrlDraft] = useState(
    preferences.apiBaseUrl,
  );
  const [connectionMessage, setConnectionMessage] = useState(
    "Saved in this browser. Use Refresh after changing the backend URL.",
  );
  const [instructionDrafts, setInstructionDrafts] = useState<
    Record<SkillPresetId, string>
  >(() => buildInstructionDrafts(preferences.skillPreferences));
  const [savedSkillPreferences, setSavedSkillPreferences] = useState<SkillPreferences>(
    preferences.skillPreferences,
  );
  const [savedSkillId, setSavedSkillId] = useState<SkillPresetId | null>(null);
  const [skillProfileMessage, setSkillProfileMessage] = useState("Saved workspace skill profile is used by Ask.");
  const [skillGuidancePreviewVisible, setSkillGuidancePreviewVisible] = useState(false);
  const [savingSkillProfile, setSavingSkillProfile] = useState(false);
  const [selectedSkillTemplateId, setSelectedSkillTemplateId] = useState<SkillProfileTemplateId>("devops_review");
  const [skillTemplatePreviewVisible, setSkillTemplatePreviewVisible] = useState(false);
  const [fileRulesDraft, setFileRulesDraft] = useState(() => ({
    includePatterns: preferences.fileIndexingPreferences.includePatterns,
    excludePatterns: preferences.fileIndexingPreferences.excludePatterns,
  }));
  const [fileRulesMessage, setFileRulesMessage] = useState("File rules saved in workspace.");
  const [savingFileRules, setSavingFileRules] = useState(false);
  const [fileRulesPreview, setFileRulesPreview] = useState<FileSelectionPreview | null>(null);
  const [fileRulesPreviewMode, setFileRulesPreviewMode] = useState<"saved" | "draft" | null>(null);
  const [previewingFileRules, setPreviewingFileRules] = useState(false);
  const [localDataSafety, setLocalDataSafety] = useState<LocalDataSafety | null>(null);
  const [localDataSafetyError, setLocalDataSafetyError] = useState<string | null>(null);
  const [localDataSafetyLoading, setLocalDataSafetyLoading] = useState(false);
  const [startupChecklist, setStartupChecklist] = useState<StartupChecklist | null>(null);
  const [startupChecklistError, setStartupChecklistError] = useState<string | null>(null);
  const [startupChecklistLoading, setStartupChecklistLoading] = useState(false);
  const [databaseBackups, setDatabaseBackups] = useState<DatabaseBackupList | null>(null);
  const [databaseBackupsError, setDatabaseBackupsError] = useState<string | null>(null);
  const [databaseBackupsLoading, setDatabaseBackupsLoading] = useState(false);
  const [creatingDatabaseBackup, setCreatingDatabaseBackup] = useState(false);
  const [selectedBackupFilename, setSelectedBackupFilename] = useState("");
  const [databaseRestorePlan, setDatabaseRestorePlan] = useState<DatabaseRestorePlan | null>(null);
  const [databaseRestorePlanError, setDatabaseRestorePlanError] = useState<string | null>(null);
  const [databaseMigrationSafety, setDatabaseMigrationSafety] = useState<DatabaseMigrationSafety | null>(null);
  const [databaseMigrationSafetyError, setDatabaseMigrationSafetyError] = useState<string | null>(null);
  const [databaseMigrationSafetyLoading, setDatabaseMigrationSafetyLoading] = useState(false);
  const [runtimeTroubleshooting, setRuntimeTroubleshooting] = useState<RuntimeTroubleshooting | null>(null);
  const [runtimeTroubleshootingError, setRuntimeTroubleshootingError] = useState<string | null>(null);
  const [runtimeTroubleshootingLoading, setRuntimeTroubleshootingLoading] = useState(false);

  const [safeUpdateWorkflow, setSafeUpdateWorkflow] = useState<SafeUpdateWorkflow | null>(null);
  const [safeUpdateWorkflowError, setSafeUpdateWorkflowError] = useState<string | null>(null);
  const [safeUpdateWorkflowLoading, setSafeUpdateWorkflowLoading] = useState(false);
  const [desktopStartup, setDesktopStartup] = useState<DesktopStartupExperience | null>(null);
  const [desktopStartupError, setDesktopStartupError] = useState<string | null>(null);
  const [desktopStartupLoading, setDesktopStartupLoading] = useState(false);
  const [productionReadiness, setProductionReadiness] = useState<ProductionReadiness | null>(null);
  const [productionReadinessError, setProductionReadinessError] = useState<string | null>(null);
  const [productionReadinessLoading, setProductionReadinessLoading] = useState(false);


  useEffect(() => {
    setBackendUrlDraft(preferences.apiBaseUrl);
  }, [preferences.apiBaseUrl]);


  useEffect(() => {
    let cancelled = false;
    setProductionReadinessLoading(true);
    setProductionReadinessError(null);
    getProductionReadiness()
      .then((readiness) => {
        if (!cancelled) {
          setProductionReadiness(readiness);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setProductionReadinessError(error instanceof Error ? error.message : "Could not load production readiness");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProductionReadinessLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);

  useEffect(() => {
    let cancelled = false;
    setDesktopStartupLoading(true);
    setDesktopStartupError(null);
    getDesktopStartupExperience()
      .then((experience) => {
        if (!cancelled) {
          setDesktopStartup(experience);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDesktopStartupError(error instanceof Error ? error.message : "Could not load desktop startup guidance");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDesktopStartupLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);

  useEffect(() => {
    let cancelled = false;
    setLocalDataSafetyLoading(true);
    setLocalDataSafetyError(null);
    getLocalDataSafety()
      .then((diagnostics) => {
        if (!cancelled) {
          setLocalDataSafety(diagnostics);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLocalDataSafetyError(error instanceof Error ? error.message : "Could not load local data diagnostics");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLocalDataSafetyLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);

  useEffect(() => {
    let cancelled = false;
    setStartupChecklistLoading(true);
    setStartupChecklistError(null);
    getStartupChecklist()
      .then((checklist) => {
        if (!cancelled) {
          setStartupChecklist(checklist);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStartupChecklistError(error instanceof Error ? error.message : "Could not load startup checklist");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setStartupChecklistLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);


  useEffect(() => {
    let cancelled = false;
    setSafeUpdateWorkflowLoading(true);
    setSafeUpdateWorkflowError(null);
    getSafeUpdateWorkflow()
      .then((workflow) => {
        if (!cancelled) {
          setSafeUpdateWorkflow(workflow);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setSafeUpdateWorkflowError(error instanceof Error ? error.message : "Could not load safe update workflow");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSafeUpdateWorkflowLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);


  useEffect(() => {
    let cancelled = false;
    setRuntimeTroubleshootingLoading(true);
    setRuntimeTroubleshootingError(null);
    getRuntimeTroubleshooting()
      .then((diagnostics) => {
        if (!cancelled) {
          setRuntimeTroubleshooting(diagnostics);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setRuntimeTroubleshootingError(error instanceof Error ? error.message : "Could not load runtime troubleshooting");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setRuntimeTroubleshootingLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);

  useEffect(() => {
    refreshDatabaseBackups();
    let cancelled = false;
    setDatabaseMigrationSafetyLoading(true);
    setDatabaseMigrationSafetyError(null);
    getDatabaseMigrationSafety()
      .then((diagnostics) => {
        if (!cancelled) {
          setDatabaseMigrationSafety(diagnostics);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDatabaseMigrationSafetyError(error instanceof Error ? error.message : "Could not load migration safety diagnostics");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDatabaseMigrationSafetyLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);


  useEffect(() => {
    setInstructionDrafts(buildInstructionDrafts(preferences.skillPreferences));
    setSavedSkillPreferences(preferences.skillPreferences);
  }, [dashboard.workspace_id, skillProfileUpdatedAt]);

  useEffect(() => {
    setFileRulesDraft({
      includePatterns: preferences.fileIndexingPreferences.includePatterns,
      excludePatterns: preferences.fileIndexingPreferences.excludePatterns,
    });
  }, [preferences.fileIndexingPreferences]);

  const preferencesJson = useMemo(
    () => JSON.stringify(preferences, null, 2),
    [preferences],
  );

  useEffect(() => {
    setSavedMessage("Saved just now");
    const timeoutId = window.setTimeout(() => {
      setSavedMessage("Saved in this browser");
    }, 1800);
    return () => window.clearTimeout(timeoutId);
  }, [preferences]);

  function updatePreference<K extends keyof WorkbenchPreferences>(
    key: K,
    value: WorkbenchPreferences[K],
  ) {
    setResetRequested(false);
    onPreferencesChange({ ...preferences, [key]: value });
  }

  function applyBrandingPreset(preset: BrandingPreset) {
    setResetRequested(false);
    onPreferencesChange({
      ...preferences,
      productName: normalizeProductName(preset.productName),
      brandInitials: normalizeBrandInitials(preset.brandInitials),
      accentColor: preset.accentColor,
    });
  }

  function updateSkillPreference(
    skillId: keyof WorkbenchPreferences["skillPreferences"],
    patch: Partial<
      WorkbenchPreferences["skillPreferences"][keyof WorkbenchPreferences["skillPreferences"]]
    >,
  ) {
    setResetRequested(false);
    onPreferencesChange({
      ...preferences,
      skillPreferences: {
        ...preferences.skillPreferences,
        [skillId]: {
          ...preferences.skillPreferences[skillId],
          ...patch,
        },
      },
    });
  }

  function updateInstructionDraft(skillId: SkillPresetId, value: string) {
    setSavedSkillId(null);
    setInstructionDrafts((current) => ({
      ...current,
      [skillId]: value.slice(0, 1200),
    }));
  }

  function saveSkillInstruction(skillId: SkillPresetId) {
    updateSkillPreference(skillId, {
      customInstructions: instructionDrafts[skillId] ?? "",
    });
    setSavedSkillId(skillId);
  }

  function resetSkillInstruction(
    skillId: keyof WorkbenchPreferences["skillPreferences"],
  ) {
    const defaultInstruction =
      DEFAULT_SKILL_PREFERENCES[skillId].customInstructions;
    setInstructionDrafts((current) => ({
      ...current,
      [skillId]: defaultInstruction,
    }));
    updateSkillPreference(skillId, {
      customInstructions: defaultInstruction,
    });
    setSavedSkillId(skillId);
  }

  function applySelectedSkillTemplateToDraft() {
    const nextPreferences = applySkillProfileTemplate(
      selectedSkillTemplateId,
      preferences.skillPreferences,
    );
    setSavedSkillId(null);
    setInstructionDrafts(buildInstructionDrafts(nextPreferences));
    updatePreference("skillPreferences", nextPreferences);
    setSkillProfileMessage(
      "Template applied to draft only. Review the guidance, then save the workspace profile to use it in Ask.",
    );
  }

  async function saveWorkspaceSkillProfile() {
    const nextPreferences = normalizeSkillPreferences(
      SKILL_PRESETS.reduce((current, preset) => {
        current[preset.id] = {
          enabled: preferences.skillPreferences[preset.id]?.enabled ?? false,
          customInstructions:
            instructionDrafts[preset.id]?.trim() ||
            preferences.skillPreferences[preset.id]?.customInstructions ||
            preset.defaultInstructions,
        };
        return current;
      }, {} as Partial<Record<SkillPresetId, { enabled: boolean; customInstructions: string }>>),
    );
    setSavingSkillProfile(true);
    setSkillProfileMessage("Saving workspace skill profile...");
    try {
      await updateWorkspaceSkillProfile(
        dashboard.workspace_id,
        toSkillProfileRequest(nextPreferences),
      );
      updatePreference("skillPreferences", nextPreferences);
      setInstructionDrafts(buildInstructionDrafts(nextPreferences));
      setSavedSkillPreferences(nextPreferences);
      setSavedSkillId(null);
      setSkillProfileMessage("Workspace skill profile saved. Ask will use this saved profile.");
      onSkillProfileSaved?.();
    } catch (error) {
      setSkillProfileMessage(`Could not save skill profile: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setSavingSkillProfile(false);
    }
  }

  function updateFileRulesDraft(
    key: "includePatterns" | "excludePatterns",
    value: string,
  ) {
    setResetRequested(false);
    setFileRulesDraft((current) => ({
      ...current,
      [key]: value.slice(0, 4000),
    }));
    setFileRulesMessage("Unsaved file rule changes.");
  }

  const hasUnsavedFileRules =
    fileRulesDraft.includePatterns !== preferences.fileIndexingPreferences.includePatterns ||
    fileRulesDraft.excludePatterns !== preferences.fileIndexingPreferences.excludePatterns;
  const skillProfileDiff = useMemo(
    () => buildSkillProfileDiff(savedSkillPreferences, preferences.skillPreferences, instructionDrafts),
    [savedSkillPreferences, preferences.skillPreferences, instructionDrafts],
  );
  const hasUnsavedSkillProfile = skillProfileDiff.totalChanges > 0;
  const draftActiveSkillNames = useMemo(
    () => getActiveSkillNames(preferences.skillPreferences),
    [preferences.skillPreferences],
  );
  const savedActiveSkillNames = useMemo(
    () => getActiveSkillNames(savedSkillPreferences),
    [savedSkillPreferences],
  );

  function resetSkillDraftToSaved() {
    const nextPreferences = normalizeSkillPreferences(savedSkillPreferences);
    setSavedSkillId(null);
    setInstructionDrafts(buildInstructionDrafts(nextPreferences));
    updatePreference("skillPreferences", nextPreferences);
    setSkillProfileMessage("Draft reset to the saved workspace skill profile.");
  }

  function resetSkillDraftToDefault() {
    const nextPreferences = normalizeSkillPreferences(DEFAULT_SKILL_PREFERENCES);
    setSavedSkillId(null);
    setInstructionDrafts(buildInstructionDrafts(nextPreferences));
    updatePreference("skillPreferences", nextPreferences);
    setSkillProfileMessage("Draft reset to the safe default profile. Save it to replace the workspace profile.");
  }

  async function previewFileRules(mode: "saved" | "draft") {
    setPreviewingFileRules(true);
    setFileRulesPreviewMode(mode);
    setFileRulesMessage(
      mode === "saved"
        ? "Previewing saved workspace rules."
        : "Previewing unsaved draft rules. Save them before scan/index if this looks right.",
    );
    try {
      const draftPreferences = {
        ...preferences.fileIndexingPreferences,
        includePatterns: normalizePatternText(
          fileRulesDraft.includePatterns,
          DEFAULT_FILE_INDEXING_PREFERENCES.includePatterns,
        ),
        excludePatterns: normalizePatternText(
          fileRulesDraft.excludePatterns,
          DEFAULT_FILE_INDEXING_PREFERENCES.excludePatterns,
        ),
      };
      setFileRulesPreview(
        mode === "saved"
          ? await previewWorkspaceFileSelection(dashboard.workspace_id)
          : await previewWorkspaceFileSelection(
              dashboard.workspace_id,
              toFileSelectionRulesRequest(draftPreferences),
            ),
      );
      setFileRulesMessage(
        mode === "saved"
          ? "Saved rules preview loaded."
          : "Draft preview loaded. Save rules before scan/index to apply them.",
      );
    } catch (error) {
      setFileRulesMessage(
        `Could not preview file rules: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    } finally {
      setPreviewingFileRules(false);
    }
  }

  async function saveFileRules() {
    const nextPreferences = {
      ...preferences.fileIndexingPreferences,
      includePatterns: normalizePatternText(
        fileRulesDraft.includePatterns,
        DEFAULT_FILE_INDEXING_PREFERENCES.includePatterns,
      ),
      excludePatterns: normalizePatternText(
        fileRulesDraft.excludePatterns,
        DEFAULT_FILE_INDEXING_PREFERENCES.excludePatterns,
      ),
    };
    setSavingFileRules(true);
    try {
      await updateWorkspaceIndexingRules(
        dashboard.workspace_id,
        toFileSelectionRulesRequest(nextPreferences),
      );
      updatePreference("fileIndexingPreferences", nextPreferences);
      setFileRulesDraft({
        includePatterns: nextPreferences.includePatterns,
        excludePatterns: nextPreferences.excludePatterns,
      });
      setFileRulesPreview(null);
      setFileRulesPreviewMode(null);
      setFileRulesMessage("File rules saved to this workspace. Preview saved rules before scan/index.");
      onIndexingRulesSaved?.();
    } catch (error) {
      setFileRulesMessage(`Could not save workspace file rules: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setSavingFileRules(false);
    }
  }

  function resetFileRules() {
    setFileRulesDraft({
      includePatterns: DEFAULT_FILE_INDEXING_PREFERENCES.includePatterns,
      excludePatterns: DEFAULT_FILE_INDEXING_PREFERENCES.excludePatterns,
    });
    setFileRulesPreview(null);
    setFileRulesPreviewMode(null);
    setFileRulesMessage("Draft reset to safe defaults. Save to apply these rules to the workspace.");
  }

  async function handleCopyPreferences() {
    setResetRequested(false);
    try {
      await navigator.clipboard.writeText(preferencesJson);
      setTransferMessage("Preferences JSON copied.");
    } catch {
      setTransferMessage(
        "Copy is unavailable. Select the JSON and copy it manually.",
      );
    }
  }

  function handleSaveBackendUrl() {
    setResetRequested(false);
    const normalizedUrl = normalizeApiBaseUrl(backendUrlDraft);
    if (!isValidHttpUrl(normalizedUrl)) {
      setConnectionMessage("Enter a valid http:// or https:// URL.");
      return;
    }
    updatePreference("apiBaseUrl", normalizedUrl);
    setBackendUrlDraft(normalizedUrl);
    setConnectionMessage(
      "Connection saved. Use Refresh to reload workspaces from this address.",
    );
  }

  function handleResetBackendUrl() {
    setResetRequested(false);
    setBackendUrlDraft(DEFAULT_API_BASE_URL);
    updatePreference("apiBaseUrl", DEFAULT_API_BASE_URL);
    setConnectionMessage(
      "Connection reset to the app default. Use Refresh to reload workspaces.",
    );
  }

  function handleLoadCurrentPreferences() {
    setResetRequested(false);
    setImportDraft(preferencesJson);
    setTransferMessage("Current preferences loaded into the import box.");
  }

  function handleImportPreferences() {
    setResetRequested(false);
    const parsedPreferences = parseImportedPreferences(
      importDraft,
      preferences,
    );
    if (!parsedPreferences) {
      setTransferMessage(
        "Import failed. Paste valid preferences JSON with supported values.",
      );
      return;
    }
    onPreferencesChange(parsedPreferences);
    setImportDraft("");
    setTransferMessage("Preferences imported and saved in this browser.");
  }

  function handleResetClick() {
    if (!resetRequested) {
      setResetRequested(true);
      return;
    }
    onResetPreferences();
    setImportDraft("");
    setTransferMessage("Preferences reset to defaults in this browser.");
    setResetRequested(false);
  }


  function refreshDatabaseBackups() {
    setDatabaseBackupsLoading(true);
    setDatabaseBackupsError(null);
    getDatabaseBackups()
      .then((backups) => {
        setDatabaseBackups(backups);
        setSelectedBackupFilename((current) => current || backups.backups[0]?.filename || "");
      })
      .catch((error) => {
        setDatabaseBackupsError(error instanceof Error ? error.message : "Could not load database backups");
      })
      .finally(() => {
        setDatabaseBackupsLoading(false);
      });
  }

  function handleCreateDatabaseBackup() {
    setCreatingDatabaseBackup(true);
    setDatabaseBackupsError(null);
    createDatabaseBackup()
      .then(() => {
        refreshDatabaseBackups();
      })
      .catch((error) => {
        setDatabaseBackupsError(error instanceof Error ? error.message : "Could not create database backup");
      })
      .finally(() => {
        setCreatingDatabaseBackup(false);
      });
  }

  function handleBuildRestorePlan() {
    if (!selectedBackupFilename) {
      setDatabaseRestorePlanError("Select a backup first.");
      return;
    }
    setDatabaseRestorePlanError(null);
    getDatabaseRestorePlan(selectedBackupFilename)
      .then(setDatabaseRestorePlan)
      .catch((error) => {
        setDatabaseRestorePlanError(error instanceof Error ? error.message : "Could not build restore plan");
      });
  }

  return (
    <div className="settings-page">
      <section className="panel settings-hero-panel">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>AI Private Workspace settings</h1>
          <p>
            Tune browser-local preferences for branding, display, workspace
            questions, and startup behavior. Project setup and model runtime
            stay manual.
          </p>
        </div>
        <div className="settings-save-status">
          <StatusBadge label={savedMessage} tone="info" size="md" />
          <span>Browser-local only</span>
        </div>
      </section>

      <section className="panel settings-focus-panel">
        <div>
          <p className="eyebrow">Current workspace</p>
          <h2>{dashboard.workspace_name}</h2>
          <p>{summary.project_path}</p>
        </div>
        <div className="settings-focus-status">
          <StatusBadge label={dashboard.status} />
          <span>{formatMode(dashboard.assistant_mode)} mode</span>
        </div>
      </section>

      <div className="settings-grid">
        <SettingsSection
          eyebrow="Connection"
          title="Local backend"
          description="Choose the local API address for this browser. Change this only when your backend runs on a different host or port."
          badge="Browser-local"
        >
          <PreferenceGroup label="Backend URL">
            <div className="settings-url-editor">
              <input
                type="url"
                value={backendUrlDraft}
                onChange={(event) => {
                  setBackendUrlDraft(event.target.value);
                  setConnectionMessage("Unsaved backend URL change.");
                }}
                placeholder="http://127.0.0.1:8000"
                aria-label="Backend URL"
              />
              <div className="settings-url-actions">
                <button
                  type="button"
                  className="primary-button"
                  disabled={
                    normalizeApiBaseUrl(backendUrlDraft) ===
                    preferences.apiBaseUrl
                  }
                  onClick={handleSaveBackendUrl}
                >
                  Save URL
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={
                    preferences.apiBaseUrl === DEFAULT_API_BASE_URL &&
                    backendUrlDraft === DEFAULT_API_BASE_URL
                  }
                  onClick={handleResetBackendUrl}
                >
                  Reset default
                </button>
              </div>
              <p>{connectionMessage}</p>
            </div>
          </PreferenceGroup>
          <SettingsRow
            label="Current target"
            value={preferences.apiBaseUrl}
            code
          />
          <SettingsRow
            label="Default target"
            value={DEFAULT_API_BASE_URL}
            code
          />
          <SettingsRow label="Scope" value="Local browser to local API" />
          <p className="settings-helper-note">
            After changing this address, use Refresh in the sidebar to load
            workspaces from the new backend.
          </p>
        </SettingsSection>

        <SettingsSection
          eyebrow="Appearance"
          title="Display"
          description="Choose how the workbench looks on this computer. These choices are stored only in this browser."
          badge="Local"
          tone="info"
        >
          <PreferenceGroup label="Theme">
            <SegmentedChoice
              value={preferences.theme}
              options={[
                { value: "system", label: "System" },
                { value: "light", label: "Light" },
                { value: "dark", label: "Dark" },
              ]}
              onChange={(value) => updatePreference("theme", value)}
            />
          </PreferenceGroup>
          <PreferenceGroup label="Density">
            <SegmentedChoice
              value={preferences.density}
              options={[
                { value: "comfortable", label: "Comfortable" },
                { value: "compact", label: "Compact" },
              ]}
              onChange={(value) => updatePreference("density", value)}
            />
          </PreferenceGroup>
        </SettingsSection>

        <SettingsSection
          eyebrow="Branding"
          title="Workspace identity"
          description="Personalize the local UI for demos or company use. These choices stay in this browser."
          badge="Local"
          tone="info"
        >
          <PreferenceGroup label="Brand presets">
            <div className="branding-preset-grid">
              {BRANDING_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className={`branding-preset-card${
                    preferences.productName === preset.productName &&
                    preferences.brandInitials === preset.brandInitials &&
                    preferences.accentColor === preset.accentColor
                      ? " is-selected"
                      : ""
                  }`}
                  onClick={() => applyBrandingPreset(preset)}
                >
                  <span className="brand-mark settings-brand-preview" aria-hidden="true">
                    {preset.brandInitials}
                  </span>
                  <strong>{preset.label}</strong>
                  <small>{preset.description}</small>
                </button>
              ))}
            </div>
          </PreferenceGroup>
          <PreferenceGroup label="Product name">
            <input
              className="text-input"
              value={preferences.productName}
              onChange={(event) =>
                updatePreference("productName", normalizeProductName(event.target.value))
              }
              maxLength={48}
              aria-label="Product name"
            />
          </PreferenceGroup>
          <PreferenceGroup label="Logo initials">
            <div className="settings-brand-editor">
              <span
                className="brand-mark settings-brand-preview"
                aria-hidden="true"
              >
                {preferences.brandInitials}
              </span>
              <input
                value={preferences.brandInitials}
                onChange={(event) =>
                  updatePreference(
                    "brandInitials",
                    normalizeBrandInitials(event.target.value),
                  )
                }
                maxLength={3}
                aria-label="Logo initials"
              />
            </div>
          </PreferenceGroup>
          <PreferenceGroup label="Accent color">
            <SegmentedChoice
              value={preferences.accentColor}
              options={[
                { value: "green", label: "Green" },
                { value: "blue", label: "Blue" },
                { value: "purple", label: "Purple" },
                { value: "orange", label: "Orange" },
              ]}
              onChange={(value) => updatePreference("accentColor", value)}
            />
          </PreferenceGroup>
          <SettingsRow label="Scope" value="Browser-local visual identity only" />
        </SettingsSection>

        <SettingsSection
          eyebrow="Ask defaults"
          title="Workspace questions"
          description="Choose safe defaults for new questions. Asking still only happens when you press Ask."
          badge={contextReady ? "Ready" : "Needs context"}
          tone={contextReady ? "success" : "warning"}
        >
          <PreferenceGroup label="Default source snippets">
            <SegmentedChoice
              value={String(preferences.defaultSourceSnippets)}
              options={[
                { value: "3", label: "3" },
                { value: "5", label: "5" },
                { value: "8", label: "8" },
                { value: "10", label: "10" },
              ]}
              onChange={(value) =>
                updatePreference(
                  "defaultSourceSnippets",
                  Number(
                    value,
                  ) as WorkbenchPreferences["defaultSourceSnippets"],
                )
              }
            />
          </PreferenceGroup>
          <PreferenceGroup label="Open workspace on">
            <SegmentedChoice
              value={preferences.landingTab}
              options={[
                { value: "overview", label: "Overview" },
                { value: "ask", label: "Ask" },
                { value: "models", label: "Models" },
                { value: "settings", label: "Settings" },
              ]}
              onChange={(value) =>
                updatePreference(
                  "landingTab",
                  value as WorkbenchPreferences["landingTab"],
                )
              }
            />
          </PreferenceGroup>
          <SettingsRow label="Answer mode" value="Source-backed local answer" />
          <SettingsRow label="Storage" value="Saved draft in this browser" />
        </SettingsSection>


        <SettingsSection
          eyebrow="File selection"
          title="Files and search context"
          description="Save workspace file rules before rebuilding search context. Scan and index jobs use the saved rules unless you explicitly send temporary rules."
          badge="Workspace rules"
          tone="info"
        >
          <div className="settings-file-rule-summary">
            <div>
              <strong>{countPatterns(preferences.fileIndexingPreferences.includePatterns)}</strong>
              <span>saved include rules</span>
            </div>
            <div>
              <strong>{countPatterns(preferences.fileIndexingPreferences.excludePatterns)}</strong>
              <span>saved exclude rules</span>
            </div>
            <div>
              <strong>{countPatterns(fileRulesDraft.includePatterns)}</strong>
              <span>draft include rules</span>
            </div>
            <div>
              <strong>{countPatterns(fileRulesDraft.excludePatterns)}</strong>
              <span>draft exclude rules</span>
            </div>
          </div>
          <div className="file-rules-draft-state">
            <StatusBadge
              label={hasUnsavedFileRules ? "Unsaved draft" : "Saved draft"}
              tone={hasUnsavedFileRules ? "warning" : "success"}
            />
            <span>Scan and Build context use saved workspace rules. Draft changes are ignored until you save them.</span>
          </div>
          <PreferenceGroup label="Include patterns">
            <textarea
              className="settings-pattern-box"
              value={fileRulesDraft.includePatterns}
              onChange={(event) =>
                updateFileRulesDraft("includePatterns", event.target.value)
              }
              rows={8}
              aria-label="File include patterns"
            />
          </PreferenceGroup>
          <PreferenceGroup label="Exclude patterns">
            <textarea
              className="settings-pattern-box"
              value={fileRulesDraft.excludePatterns}
              onChange={(event) =>
                updateFileRulesDraft("excludePatterns", event.target.value)
              }
              rows={8}
              aria-label="File exclude patterns"
            />
          </PreferenceGroup>
          <div className="settings-inline-actions">
            <button type="button" className="primary-button" onClick={() => void saveFileRules()} disabled={savingFileRules || !hasUnsavedFileRules}>
              {savingFileRules ? "Saving..." : "Save file rules"}
            </button>
            <button type="button" className="ghost-button" onClick={() => void previewFileRules("saved")} disabled={previewingFileRules}>
              {previewingFileRules && fileRulesPreviewMode === "saved" ? "Previewing..." : "Preview saved rules"}
            </button>
            <button type="button" className="ghost-button" onClick={() => void previewFileRules("draft")} disabled={previewingFileRules}>
              {previewingFileRules && fileRulesPreviewMode === "draft" ? "Previewing..." : "Preview draft rules"}
            </button>
            <button type="button" className="ghost-button" onClick={resetFileRules}>
              Reset draft
            </button>
            <span>{fileRulesMessage}</span>
          </div>
          {fileRulesPreview ? (
            <SettingsFilePreviewResult
              preview={fileRulesPreview}
              mode={fileRulesPreviewMode ?? "saved"}
            />
          ) : null}
          <p className="settings-helper-note">
            Flow: edit draft → preview draft → save rules → preview saved rules → scan/index manually. Nothing rebuilds automatically.
          </p>
        </SettingsSection>

        <SettingsSection
          eyebrow="AI defaults"
          title="Models"
          description="Settings shows the current workspace model defaults. Change or compare models from the Models tab."
          badge={localAIReady ? "Ready" : "Review"}
          tone={localAIReady ? "success" : "warning"}
        >
          <SettingsRow
            label="AI answer model"
            value={modelsSummary.selected_llm ?? "Not selected"}
            code
          />
          <SettingsRow
            label="Search context model"
            value={modelsSummary.selected_embedding ?? "Not selected"}
            code
          />
          <div className="settings-inline-actions">
            <button
              type="button"
              className="ghost-button"
              onClick={onOpenModels}
            >
              Open Models
            </button>
            <span>
              Use Models when you want to review, compare, or change workspace
              model choices.
            </span>
          </div>
        </SettingsSection>
      </div>

      <section className="panel skill-library-settings-panel">
        <div className="settings-transfer-heading">
          <div>
            <p className="eyebrow">Skill library</p>
            <h2>Assistant skills</h2>
            <p>
              Start from safe presets, then save the workspace profile. Ask uses the saved profile as guidance only; project claims still come from retrieved sources.
            </p>
          </div>
          <div className="settings-heading-actions">
            <StatusBadge
              label={hasUnsavedSkillProfile ? `${skillProfileDiff.totalChanges} draft changes` : `${draftActiveSkillNames.length} active`}
              tone={hasUnsavedSkillProfile ? "warning" : "info"}
            />
            <button
              type="button"
              className="ghost-button"
              onClick={() => setSkillGuidancePreviewVisible((current) => !current)}
            >
              {skillGuidancePreviewVisible ? "Hide guidance" : "Preview prompt guidance"}
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={resetSkillDraftToSaved}
              disabled={!hasUnsavedSkillProfile}
            >
              Reset to saved
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={resetSkillDraftToDefault}
            >
              Reset to default
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={() => void saveWorkspaceSkillProfile()}
              disabled={savingSkillProfile || !hasUnsavedSkillProfile}
            >
              {savingSkillProfile ? "Saving..." : "Save workspace profile"}
            </button>
          </div>
        </div>
        <p className="settings-helper-text">{skillProfileMessage}</p>

        <SkillTemplatePicker
          selectedTemplateId={selectedSkillTemplateId}
          onTemplateChange={setSelectedSkillTemplateId}
          onApplyTemplate={applySelectedSkillTemplateToDraft}
          previewVisible={skillTemplatePreviewVisible}
          onTogglePreview={() =>
            setSkillTemplatePreviewVisible((isVisible) => !isVisible)
          }
        />

        <div className="skill-profile-state-grid skill-profile-state-grid-wide">
          <article>
            <span>Saved profile</span>
            <strong>{skillProfileSource === "saved" ? "Workspace saved profile" : "Default profile"}</strong>
            <p>{skillProfileUpdatedAt ? `Last saved ${formatDateTime(skillProfileUpdatedAt)}` : "No workspace-specific profile saved yet."}</p>
            <small>{savedActiveSkillNames.length > 0 ? savedActiveSkillNames.join(" + ") : "No saved active skills"}</small>
          </article>
          <article>
            <span>Draft profile</span>
            <strong>{hasUnsavedSkillProfile ? "Unsaved draft" : "Matches saved profile"}</strong>
            <p>{draftActiveSkillNames.length > 0 ? draftActiveSkillNames.join(" + ") : "No draft active skills"}</p>
            <small>Ask uses the saved profile after you save this draft.</small>
          </article>
          <article>
            <span>Draft diff</span>
            <strong>{skillProfileDiff.summary}</strong>
            <p>{skillProfileDiff.details}</p>
            <small>Use reset to saved/default before saving if the draft looks wrong.</small>
          </article>
          <article>
            <span>Ask usage</span>
            <strong>Guidance only</strong>
            <p>Skills shape focus and wording. Facts still need retrieved source chunks.</p>
            <small>No scan, index, rebuild, or shell command is triggered by skill edits.</small>
          </article>
        </div>

        {skillGuidancePreviewVisible ? (
          <SkillGuidancePreview
            preferences={preferences.skillPreferences}
            instructionDrafts={instructionDrafts}
          />
        ) : null}

        <div className="skill-library-settings-grid">
          {SKILL_PRESETS.map((preset) => {
            const preference = preferences.skillPreferences[preset.id];
            const draft =
              instructionDrafts[preset.id] ?? preference.customInstructions;
            const hasUnsavedInstruction =
              draft !== preference.customInstructions;
            return (
              <article
                className={`skill-settings-card ${preference.enabled ? "is-enabled" : ""}`}
                key={preset.id}
              >
                <div className="skill-settings-card-heading">
                  <div>
                    <p className="eyebrow">{preset.shortName} skill</p>
                    <h3>{preset.name}</h3>
                  </div>
                  <div
                    className="skill-toggle-actions"
                    aria-label={`${preset.name} skill state`}
                  >
                    <StatusBadge
                      label={preference.enabled ? "Enabled" : "Disabled"}
                      tone={preference.enabled ? "success" : "neutral"}
                    />
                    <button
                      type="button"
                      className={
                        preference.enabled ? "ghost-button" : "primary-button"
                      }
                      onClick={() =>
                        updateSkillPreference(preset.id, {
                          enabled: !preference.enabled,
                        })
                      }
                    >
                      {preference.enabled ? "Disable" : "Enable"}
                    </button>
                  </div>
                </div>

                <p>{preset.purpose}</p>
                <div className="skill-settings-meta">
                  <strong>Best for</strong>
                  <span>{preset.bestFor}</span>
                </div>
                <div className="skill-settings-meta">
                  <strong>Example questions</strong>
                  <span>{preset.exampleQuestions.join(" • ")}</span>
                </div>
                <div className="skill-settings-meta">
                  <strong>Recommended files</strong>
                  <span>{preset.recommendedFiles.join(", ")}</span>
                </div>

                <label className="skill-instruction-editor">
                  <span>Custom instruction</span>
                  <textarea
                    value={draft}
                    onChange={(event) =>
                      updateInstructionDraft(preset.id, event.target.value)
                    }
                    rows={4}
                  />
                </label>
                <div className="skill-settings-actions">
                  <div className="skill-settings-action-buttons">
                    <button
                      type="button"
                      className="primary-button"
                      disabled={!hasUnsavedInstruction}
                      onClick={() => saveSkillInstruction(preset.id)}
                    >
                      Save instruction
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => resetSkillInstruction(preset.id)}
                    >
                      Reset
                    </button>
                  </div>
                  <span>
                    {savedSkillId === preset.id && !hasUnsavedInstruction
                      ? "Saved draft"
                      : hasUnsavedInstruction
                        ? "Unsaved"
                        : `${draft.length}/1200`}
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="panel settings-transfer-panel is-compact">
        <div className="settings-transfer-heading">
          <div>
            <p className="eyebrow">Local backup</p>
            <h2>Backup local settings</h2>
            <p>
              Export or import browser-local preferences as JSON. This is
              optional and only changes this browser.
            </p>
          </div>
          <div className="settings-disclosure-actions">
            <StatusBadge label="JSON only" tone="neutral" />
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                setBackupToolsVisible((isVisible) => !isVisible);
                setTransferMessage(
                  backupToolsVisible
                    ? "Backup tools are hidden until needed."
                    : "Backup tools shown. Copy or paste preferences JSON.",
                );
              }}
            >
              {backupToolsVisible ? "Hide" : "Show backup tools"}
            </button>
          </div>
        </div>

        {backupToolsVisible ? (
          <>
            <div className="settings-transfer-grid">
              <div className="settings-transfer-card">
                <div>
                  <h3>Export preferences</h3>
                  <p>Copy the current local preferences as safe JSON.</p>
                </div>
                <textarea
                  className="settings-json-box"
                  value={preferencesJson}
                  readOnly
                  aria-label="Current local preferences JSON"
                />
                <div className="settings-transfer-actions">
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleCopyPreferences()}
                  >
                    Copy JSON
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={handleLoadCurrentPreferences}
                  >
                    Load into import box
                  </button>
                </div>
              </div>

              <div className="settings-transfer-card">
                <div>
                  <h3>Import preferences</h3>
                  <p>Paste exported JSON. Unsupported values are rejected.</p>
                </div>
                <textarea
                  className="settings-json-box"
                  value={importDraft}
                  onChange={(event) => setImportDraft(event.target.value)}
                  placeholder={`{
  "theme": "system",
  "density": "comfortable",
  "defaultSourceSnippets": 5,
  "landingTab": "overview",
  "apiBaseUrl": "http://127.0.0.1:8000",
  "productName": "AI Private Workspace",
  "brandInitials": "AI",
  "accentColor": "green",
  "fileIndexingPreferences": {
    "profile": "balanced",
    "includePatterns": "src/**\ndocs/**\n*.tf",
    "excludePatterns": "node_modules/**\n.venv/**\ndist/**"
  },
  "skillPreferences": {
    "devops": {
      "enabled": true,
      "customInstructions": "Pay attention to Jenkins pipelines and deployment rules."
    }
  }
}`}
                  aria-label="Import local preferences JSON"
                />
                <div className="settings-transfer-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!importDraft.trim()}
                    onClick={handleImportPreferences}
                  >
                    Import preferences
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={!importDraft}
                    onClick={() => {
                      setImportDraft("");
                      setTransferMessage("Import box cleared.");
                    }}
                  >
                    Clear
                  </button>
                </div>
              </div>
            </div>
            <p className="settings-transfer-message">{transferMessage}</p>
          </>
        ) : null}
      </section>

      <section className="panel settings-reset-panel">
        <div>
          <p className="eyebrow">Local preferences</p>
          <h2>Reset local settings</h2>
          <p>
            Reset theme, density, startup tab, source snippet defaults, and
            backend URL for this browser only. Workspace data, models, runtime,
            and local files are not changed.
          </p>
        </div>
        <div className="settings-reset-actions">
          <StatusBadge label="No backend changes" tone="neutral" />
          <button
            type="button"
            className={
              resetRequested
                ? "danger-button is-confirming"
                : "danger-button is-secondary"
            }
            onClick={handleResetClick}
          >
            {resetRequested ? "Confirm reset" : "Reset"}
          </button>
          {resetRequested ? (
            <button
              type="button"
              className="ghost-button"
              onClick={() => setResetRequested(false)}
            >
              Cancel
            </button>
          ) : null}
        </div>
      </section>

      <section className="panel settings-safety-panel">
        <div>
          <p className="eyebrow">Safety</p>
          <h2>Local-only posture</h2>
          <p>
            These preferences never execute shell commands, rebuild context,
            restart the backend, or change model runtime. Safety-critical setup
            remains explicit.
          </p>
        </div>
        <div className="settings-safety-list">
          <span>Manual setup</span>
          <span>No shell execution</span>
          <span>No automatic model changes</span>
          <span>Sources stay visible</span>
        </div>
      </section>


      <section className="panel settings-desktop-startup-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Desktop startup</p>
            <h2>Resume local workspace</h2>
            <p>
              Use a desktop-like startup flow: start local services, open the UI, and automatically restore the last selected workspace when it still exists. Commands are copy-only.
            </p>
          </div>
          <StatusBadge
            label={desktopStartupLoading ? "Checking" : desktopStartup?.status === "ok" ? "Ready" : "Review"}
            tone={desktopStartup?.status === "ok" ? "success" : "warning"}
          />
        </div>
        {desktopStartupError ? (
          <p className="settings-transfer-message">Could not load desktop startup guidance: {desktopStartupError}</p>
        ) : null}
        {desktopStartup ? (
          <>
            <div className="startup-checklist-summary">
              <strong>{desktopStartup.summary}</strong>
              <span>{desktopStartup.suggested_next_action}</span>
            </div>
            <div className="local-data-details">
              <div>
                <span>Open last workspace</span>
                <strong>{desktopStartup.open_last_workspace_enabled ? "Enabled" : "Disabled"}</strong>
                <small>Browser key: {desktopStartup.last_workspace_storage_key}</small>
              </div>
              <div>
                <span>Safety notes</span>
                <ul>
                  {desktopStartup.safety_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="settings-command-stack">
              {desktopStartup.startup_commands.map((command) => (
                <div className="startup-checklist-command" key={command.label}>
                  <span>{command.label}</span>
                  <code>{command.command}</code>
                  <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(command.command)}>
                    Copy
                  </button>
                  <small>{command.description}</small>
                </div>
              ))}
            </div>
            <ol className="settings-preflight-list">
              {desktopStartup.checklist.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </>
        ) : null}
      </section>



      <section className="panel settings-production-readiness-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Production readiness</p>
            <h2>Daily-use readiness and packaging path</h2>
            <p>
              Final Phase 16 checklist for running AI Private Workspace like a local product. This is read-only and copy-only.
            </p>
          </div>
          <StatusBadge
            label={productionReadinessLoading ? "Checking" : productionReadiness?.status === "ok" ? "Ready" : productionReadiness?.status === "blocked" ? "Blocked" : "Review"}
            tone={productionReadiness?.status === "ok" ? "success" : productionReadiness?.status === "blocked" ? "danger" : "warning"}
          />
        </div>
        {productionReadinessError ? (
          <p className="settings-transfer-message">Could not load production readiness: {productionReadinessError}</p>
        ) : null}
        {productionReadiness ? (
          <>
            <div className="startup-checklist-summary">
              <strong>{productionReadiness.summary}</strong>
              <span>Readiness score: {productionReadiness.readiness_score}%</span>
              <span>{productionReadiness.safety_note}</span>
            </div>
            <div className="startup-checklist-grid">
              {productionReadiness.items.map((item) => (
                <div className={`startup-checklist-item is-${item.status}`} key={item.id}>
                  <div className="startup-checklist-item-header">
                    <strong>{item.title}</strong>
                    <StatusBadge label={item.status} tone={item.status === "ok" ? "success" : item.status === "blocked" ? "danger" : "warning"} />
                  </div>
                  <p>{item.summary}</p>
                  <small>{item.detail}</small>
                  {item.recommended_action ? <small>Action: {item.recommended_action}</small> : null}
                </div>
              ))}
            </div>
            <div className="settings-command-stack">
              {productionReadiness.packaging_options.map((option) => (
                <div className="startup-checklist-command" key={option.id}>
                  <span>{option.title} · {option.status}</span>
                  <small>{option.summary}</small>
                  <ol className="settings-preflight-list">
                    {option.steps.map((step) => <li key={step}>{step}</li>)}
                  </ol>
                  {option.copy_commands.map((command) => (
                    <div className="settings-inline-command" key={command}>
                      <code>{command}</code>
                      <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(command)}>Copy</button>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <ol className="settings-preflight-list">
              {productionReadiness.recommended_next_steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
          </>
        ) : null}
      </section>

      <section className="panel settings-startup-checklist-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Startup checklist</p>
            <h2>Local runtime readiness</h2>
            <p>
              Review the backend Python, database, models, and safe-update posture before daily work. Commands are shown for copy only.
            </p>
          </div>
          <StatusBadge
            label={startupChecklistLoading ? "Checking" : startupChecklist?.status === "ok" ? "Ready" : startupChecklist?.status === "blocked" ? "Blocked" : "Review"}
            tone={startupChecklist?.status === "ok" ? "success" : startupChecklist?.status === "blocked" ? "danger" : "warning"}
          />
        </div>
        {startupChecklistError ? (
          <p className="settings-transfer-message">Could not load startup checklist: {startupChecklistError}</p>
        ) : null}
        {startupChecklist ? (
          <>
            <div className="startup-checklist-summary">
              <strong>{startupChecklist.summary}</strong>
              <span>{startupChecklist.safety_note}</span>
            </div>
            <div className="startup-checklist-grid">
              {startupChecklist.items.map((item) => (
                <div className={`startup-checklist-item is-${item.status}`} key={item.id}>
                  <div className="startup-checklist-item-header">
                    <div>
                      <span>{item.title}</span>
                      <strong>{item.summary}</strong>
                    </div>
                    <StatusBadge
                      label={item.status === "ok" ? "OK" : item.status === "blocked" ? "Blocked" : "Review"}
                      tone={item.status === "ok" ? "success" : item.status === "blocked" ? "danger" : "warning"}
                    />
                  </div>
                  <p>{item.detail}</p>
                  {item.copy_command ? (
                    <div className="startup-checklist-command">
                      {item.action_label ? <span>{item.action_label}</span> : null}
                      <code>{item.copy_command}</code>
                      <button
                        className="secondary-action small"
                        type="button"
                        onClick={() => void navigator.clipboard.writeText(item.copy_command ?? "")}
                      >
                        Copy
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </>
        ) : null}
      </section>

      <section className="panel settings-local-data-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Local data safety</p>
            <h2>Workspace database protection</h2>
            <p>
              Runtime workspace data is stored outside update archives. Keep these paths excluded when applying generated zips.
            </p>
          </div>
          <StatusBadge
            label={localDataSafetyLoading ? "Checking" : localDataSafety?.status === "ok" ? "Protected" : "Review"}
            tone={localDataSafety?.status === "ok" ? "success" : "warning"}
          />
        </div>
        {localDataSafetyError ? (
          <p className="settings-transfer-message">Could not load diagnostics: {localDataSafetyError}</p>
        ) : null}
        {localDataSafety ? (
          <>
            <div className="local-data-grid">
              <div>
                <span>Database</span>
                <strong>{localDataSafety.database_exists ? "Exists" : "Missing"}</strong>
                <small>{formatBytes(localDataSafety.database_size_bytes)}</small>
              </div>
              <div>
                <span>Workspaces</span>
                <strong>{formatOptionalCount(localDataSafety.workspaces_count)}</strong>
                <small>local DB records</small>
              </div>
              <div>
                <span>Conversations</span>
                <strong>{formatOptionalCount(localDataSafety.conversations_count)}</strong>
                <small>saved history</small>
              </div>
              <div>
                <span>Reports</span>
                <strong>{formatOptionalCount(localDataSafety.saved_reports_count)}</strong>
                <small>saved docs</small>
              </div>
            </div>
            <div className="local-data-details">
              <div>
                <span>Active DB path</span>
                <code>{localDataSafety.database_path}</code>
              </div>
              <div>
                <span>Safe update excludes</span>
                <code>{localDataSafety.safe_update_excludes.join(" ")}</code>
              </div>
              {localDataSafety.warnings.length > 0 ? (
                <div>
                  <span>Warnings</span>
                  <ul>
                    {localDataSafety.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </section>


      <section className="panel settings-update-workflow-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Safe updates</p>
            <h2>Generated archive apply workflow</h2>
            <p>
              Apply generated task archives through a dry-run and automatic DB backup guardrail. The UI only shows copyable commands.
            </p>
          </div>
          <StatusBadge
            label={safeUpdateWorkflowLoading ? "Checking" : safeUpdateWorkflow?.status === "ok" ? "Protected" : "Review"}
            tone={safeUpdateWorkflow?.status === "ok" ? "success" : "warning"}
          />
        </div>
        {safeUpdateWorkflowError ? (
          <p className="settings-transfer-message">Could not load safe update workflow: {safeUpdateWorkflowError}</p>
        ) : null}
        {safeUpdateWorkflow ? (
          <>
            <div className="startup-checklist-summary">
              <strong>{safeUpdateWorkflow.summary}</strong>
              <span>{safeUpdateWorkflow.safety_note}</span>
            </div>
            <div className="local-data-details">
              <div>
                <span>Protected paths</span>
                <code>{safeUpdateWorkflow.protected_paths.join(" · ")}</code>
              </div>
              <div>
                <span>Required excludes</span>
                <code>{safeUpdateWorkflow.required_excludes.join(" ")}</code>
              </div>
              <div>
                <span>Backup policy</span>
                <small>{safeUpdateWorkflow.backup_policy}</small>
              </div>
            </div>
            <div className="settings-command-stack">
              <div className="startup-checklist-command">
                <span>Dry-run first</span>
                <code>{safeUpdateWorkflow.dry_run_command}</code>
                <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(safeUpdateWorkflow.dry_run_command)}>
                  Copy
                </button>
              </div>
              <div className="startup-checklist-command">
                <span>Apply after review</span>
                <code>{safeUpdateWorkflow.apply_command}</code>
                <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(safeUpdateWorkflow.apply_command)}>
                  Copy
                </button>
              </div>
            </div>
            <ol className="settings-preflight-list">
              {safeUpdateWorkflow.preflight_checks.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ol>
            {safeUpdateWorkflow.warnings.length > 0 ? (
              <ul className="quality-warning-list">
                {safeUpdateWorkflow.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="panel settings-troubleshooting-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Troubleshooting assistant</p>
            <h2>Model and Qdrant diagnostics</h2>
            <p>
              Read-only troubleshooting for Ollama, Qdrant, backend startup, and local runtime configuration. Commands are copy-only.
            </p>
          </div>
          <StatusBadge
            label={runtimeTroubleshootingLoading ? "Checking" : runtimeTroubleshooting?.status === "ok" ? "Healthy" : runtimeTroubleshooting?.status === "blocked" ? "Blocked" : "Review"}
            tone={runtimeTroubleshooting?.status === "ok" ? "success" : runtimeTroubleshooting?.status === "blocked" ? "danger" : "warning"}
          />
        </div>
        {runtimeTroubleshootingError ? (
          <p className="settings-transfer-message">Troubleshooting diagnostics error: {runtimeTroubleshootingError}</p>
        ) : null}
        {runtimeTroubleshooting ? (
          <>
            <div className="startup-checklist-summary">
              <strong>{runtimeTroubleshooting.summary}</strong>
              <span>{runtimeTroubleshooting.safety_note}</span>
            </div>
            {runtimeTroubleshooting.issues.length > 0 ? (
              <div className="troubleshooting-issue-list">
                {runtimeTroubleshooting.issues.map((issue) => (
                  <article className={`troubleshooting-issue is-${issue.severity}`} key={issue.id}>
                    <div className="startup-checklist-item-header">
                      <div>
                        <span>{issue.component}</span>
                        <strong>{issue.title}</strong>
                      </div>
                      <StatusBadge
                        label={issue.severity === "blocked" ? "Blocked" : "Review"}
                        tone={issue.severity === "blocked" ? "danger" : "warning"}
                      />
                    </div>
                    <p>{issue.summary}</p>
                    <small>{issue.details}</small>
                    <div className="troubleshooting-step-list">
                      {issue.steps.map((step) => (
                        <div className="startup-checklist-command" key={`${issue.id}-${step.title}`}>
                          <span>{step.title}</span>
                          {step.copy_command ? <code>{step.copy_command}</code> : <small>{step.detail}</small>}
                          {step.copy_command ? (
                            <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(step.copy_command ?? "")}>
                              Copy
                            </button>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="settings-transfer-message">No runtime issues detected by backend diagnostics.</p>
            )}
            <div className="troubleshooting-command-grid">
              <div>
                <span>Quick checks</span>
                {runtimeTroubleshooting.quick_checks.map((step) => (
                  <div className="startup-checklist-command" key={step.title}>
                    <code>{step.copy_command}</code>
                    <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(step.copy_command ?? "")}>Copy</button>
                  </div>
                ))}
              </div>
              <div>
                <span>Safe restart commands</span>
                {runtimeTroubleshooting.safe_restart_commands.map((step) => (
                  <div className="startup-checklist-command" key={step.title}>
                    <code>{step.copy_command}</code>
                    <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(step.copy_command ?? "")}>Copy</button>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : null}
      </section>

      <section className="panel settings-backup-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Backup and restore</p>
            <h2>Workspace DB backup workflow</h2>
            <p>
              Create explicit local backups and prepare manual restore commands. Restore is copy-only by design and is never executed by the frontend.
            </p>
          </div>
          <StatusBadge
            label={databaseBackupsLoading ? "Checking" : `${databaseBackups?.backups.length ?? 0} backups`}
            tone={(databaseBackups?.backups.length ?? 0) > 0 ? "success" : "warning"}
          />
        </div>
        {databaseBackupsError ? (
          <p className="settings-transfer-message">Backup diagnostics error: {databaseBackupsError}</p>
        ) : null}
        <div className="settings-actions-row">
          <button
            className="primary-action"
            type="button"
            onClick={handleCreateDatabaseBackup}
            disabled={creatingDatabaseBackup}
          >
            {creatingDatabaseBackup ? "Creating backup..." : "Create DB backup"}
          </button>
          <button className="secondary-action" type="button" onClick={refreshDatabaseBackups}>
            Refresh backups
          </button>
        </div>
        {databaseBackups ? (
          <>
            <div className="local-data-details">
              <div>
                <span>Active database</span>
                <code>{databaseBackups.database_path}</code>
              </div>
              <div>
                <span>Restore policy</span>
                <small>{databaseBackups.restore_note}</small>
              </div>
            </div>
            {databaseBackups.backups.length > 0 ? (
              <div className="backup-list">
                {databaseBackups.backups.slice(0, 6).map((backup) => (
                  <label className="backup-list-item" key={backup.filename}>
                    <input
                      type="radio"
                      name="database-backup"
                      checked={selectedBackupFilename === backup.filename}
                      onChange={() => setSelectedBackupFilename(backup.filename)}
                    />
                    <span>
                      <strong>{backup.filename}</strong>
                      <small>{formatBytes(backup.size_bytes)} · {formatDateTime(backup.created_at)}</small>
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <p className="settings-transfer-message">No backups found yet. Create one before applying generated updates.</p>
            )}
          </>
        ) : null}
        <div className="settings-actions-row">
          <button
            className="secondary-action"
            type="button"
            onClick={handleBuildRestorePlan}
            disabled={!selectedBackupFilename}
          >
            Prepare restore plan
          </button>
        </div>
        {databaseRestorePlanError ? (
          <p className="settings-transfer-message">Restore plan error: {databaseRestorePlanError}</p>
        ) : null}
        {databaseRestorePlan ? (
          <div className="restore-plan-card">
            <div className="startup-checklist-summary">
              <strong>Manual restore plan for {databaseRestorePlan.backup.filename}</strong>
              <span>{databaseRestorePlan.safety_note}</span>
            </div>
            <ol>
              {databaseRestorePlan.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <div className="startup-checklist-grid">
              {databaseRestorePlan.copy_commands.map((command) => (
                <div className="startup-checklist-command" key={command}>
                  <code>{command}</code>
                  <button className="secondary-action small" type="button" onClick={() => void navigator.clipboard.writeText(command)}>
                    Copy
                  </button>
                </div>
              ))}
            </div>
            {databaseRestorePlan.warnings.length > 0 ? (
              <ul className="quality-warning-list">
                {databaseRestorePlan.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="panel settings-migration-panel">
        <div className="settings-section-heading">
          <div>
            <p className="eyebrow">Migration safety</p>
            <h2>SQLite schema readiness</h2>
            <p>
              Read-only check for known feature tables before and after generated updates.
            </p>
          </div>
          <StatusBadge
            label={databaseMigrationSafetyLoading ? "Checking" : databaseMigrationSafety?.status === "ok" ? "Ready" : "Review"}
            tone={databaseMigrationSafety?.status === "ok" ? "success" : "warning"}
          />
        </div>
        {databaseMigrationSafetyError ? (
          <p className="settings-transfer-message">Migration diagnostics error: {databaseMigrationSafetyError}</p>
        ) : null}
        {databaseMigrationSafety ? (
          <>
            <div className="startup-checklist-summary">
              <strong>{databaseMigrationSafety.schema_version}</strong>
              <span>{databaseMigrationSafety.safety_note}</span>
            </div>
            <div className="migration-table-grid">
              {databaseMigrationSafety.tables.map((table) => (
                <div className={`migration-table-item ${table.exists ? "is-ok" : "is-missing"}`} key={table.name}>
                  <span>{table.name}</span>
                  <strong>{table.exists ? formatOptionalCount(table.row_count) : "missing"}</strong>
                </div>
              ))}
            </div>
            {databaseMigrationSafety.warnings.length > 0 ? (
              <ul className="quality-warning-list">
                {databaseMigrationSafety.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}



function formatOptionalCount(value: number | null): string {
  return typeof value === "number" ? String(value) : "—";
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}


function SkillTemplatePicker({
  selectedTemplateId,
  onTemplateChange,
  onApplyTemplate,
  previewVisible,
  onTogglePreview,
}: {
  selectedTemplateId: SkillProfileTemplateId;
  onTemplateChange: (templateId: SkillProfileTemplateId) => void;
  onApplyTemplate: () => void;
  previewVisible: boolean;
  onTogglePreview: () => void;
}) {
  const selectedTemplate =
    SKILL_PROFILE_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    SKILL_PROFILE_TEMPLATES[0];

  return (
    <section className="skill-template-panel" aria-label="Skill profile templates">
      <div className="skill-template-heading">
        <div>
          <p className="eyebrow">Templates</p>
          <h3>Safe skill profile switching</h3>
          <p>
            Templates change the draft Ask guidance only. They do not scan, index, rebuild context, restart models, or execute shell commands.
          </p>
        </div>
        <div className="skill-template-actions">
          <button type="button" className="ghost-button" onClick={onTogglePreview}>
            {previewVisible ? "Hide template preview" : "Preview template"}
          </button>
          <button type="button" className="primary-button" onClick={onApplyTemplate}>
            Apply template to draft
          </button>
        </div>
      </div>

      <div className="skill-template-grid">
        {SKILL_PROFILE_TEMPLATES.map((template) => (
          <button
            type="button"
            key={template.id}
            className={`skill-template-card ${template.id === selectedTemplateId ? "is-selected" : ""}`}
            onClick={() => onTemplateChange(template.id)}
            aria-pressed={template.id === selectedTemplateId}
          >
            <span>{template.shortName}</span>
            <strong>{template.name}</strong>
            <small>{template.purpose}</small>
          </button>
        ))}
      </div>

      {previewVisible ? (
        <div className="skill-template-preview">
          <div>
            <span>Selected template</span>
            <strong>{selectedTemplate.name}</strong>
            <p>{selectedTemplate.purpose}</p>
          </div>
          <div>
            <span>Enabled skills</span>
            <strong>
              {selectedTemplate.activeSkillIds
                .map((skillId) => SKILL_PRESETS.find((preset) => preset.id === skillId)?.name ?? skillId)
                .join(" + ")}
            </strong>
            <p>Apply writes this into the draft. Save the workspace profile when the preview looks right.</p>
          </div>
          <div className="skill-template-guidance-list">
            {selectedTemplate.activeSkillIds.map((skillId) => {
              const preset = SKILL_PRESETS.find((item) => item.id === skillId);
              return (
                <article key={skillId}>
                  <strong>{preset?.name ?? skillId}</strong>
                  <pre>{selectedTemplate.guidance[skillId] ?? preset?.defaultInstructions ?? ""}</pre>
                </article>
              );
            })}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function SkillGuidancePreview({
  preferences,
  instructionDrafts,
}: {
  preferences: SkillPreferences;
  instructionDrafts: Record<SkillPresetId, string>;
}) {
  const active = SKILL_PRESETS.filter((preset) => preferences[preset.id]?.enabled);

  return (
    <section className="skill-guidance-preview" aria-label="Prompt guidance preview">
      <div>
        <p className="eyebrow">Preview prompt guidance</p>
        <h3>Guidance that Ask will receive after saving</h3>
        <p>Only enabled skills are sent as guidance. Retrieved sources remain the authority for project-specific claims.</p>
      </div>
      {active.length > 0 ? (
        <div className="skill-guidance-preview-list">
          {active.map((preset) => {
            const guidance = (instructionDrafts[preset.id] ?? preferences[preset.id]?.customInstructions ?? preset.defaultInstructions).trim();
            return (
              <article key={preset.id}>
                <strong>{preset.name}</strong>
                <pre>{guidance}</pre>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="settings-helper-note">No enabled skills. Ask will rely on the assistant mode and retrieved sources.</p>
      )}
    </section>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function SettingsFilePreviewResult({
  preview,
  mode,
}: {
  preview: FileSelectionPreview;
  mode: "saved" | "draft";
}) {
  return (
    <div className="settings-file-preview-result">
      <div className="settings-file-preview-summary">
        <div>
          <strong>{mode === "draft" ? "Draft preview" : "Saved preview"}</strong>
          <span>{preview.profile} profile</span>
        </div>
        <div>
          <span>Included</span>
          <strong>{preview.included_files_count}</strong>
        </div>
        <div>
          <span>Excluded</span>
          <strong>{preview.excluded_files_count}</strong>
        </div>
        <div>
          <span>Skipped</span>
          <strong>{preview.skipped_files_count}</strong>
        </div>
      </div>
      <div className="settings-file-preview-explain">
        <SettingsPreviewSamples title="Included examples" items={preview.included_samples} />
        <SettingsPreviewSamples title="Excluded examples" items={preview.excluded_samples} />
      </div>
    </div>
  );
}

function SettingsPreviewSamples({
  title,
  items,
}: {
  title: string;
  items: FileSelectionPreview["included_samples"];
}) {
  const visibleItems = items.slice(0, 3);

  return (
    <div className="settings-preview-samples">
      <span>{title}</span>
      {visibleItems.length > 0 ? (
        <ul>
          {visibleItems.map((item) => (
            <li key={`${title}-${item.path}`}>
              <code>{item.path}</code>
              <small>
                {item.reason}
                {item.matched_rule ? ` · ${item.matched_rule}` : ""}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <p>No sample files for this decision.</p>
      )}
    </div>
  );
}

function SettingsSection({
  eyebrow,
  title,
  description,
  badge,
  tone = "info",
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  badge: string;
  tone?: "success" | "warning" | "info" | "neutral";
  children: ReactNode;
}) {
  return (
    <section className="panel settings-section-card">
      <div className="settings-section-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <StatusBadge label={badge} tone={tone} />
      </div>
      <p>{description}</p>
      <div className="settings-row-list">{children}</div>
    </section>
  );
}

function SettingsRow({
  label,
  value,
  code = false,
}: {
  label: string;
  value: string;
  code?: boolean;
}) {
  return (
    <div className="settings-row">
      <span>{label}</span>
      {code ? <code>{value}</code> : <strong>{value}</strong>}
    </div>
  );
}

function PreferenceGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="settings-preference-group">
      <span>{label}</span>
      {children}
    </div>
  );
}

function SegmentedChoice<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div className="settings-segmented-control">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? "is-selected" : ""}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function buildInstructionDrafts(
  skillPreferences: SkillPreferences,
): Record<SkillPresetId, string> {
  return SKILL_PRESETS.reduce(
    (drafts, preset) => {
      drafts[preset.id] =
        skillPreferences[preset.id]?.customInstructions ??
        preset.defaultInstructions;
      return drafts;
    },
    {} as Record<SkillPresetId, string>,
  );
}

function getActiveSkillNames(skillPreferences: SkillPreferences): string[] {
  return SKILL_PRESETS.filter((preset) => skillPreferences[preset.id]?.enabled).map(
    (preset) => preset.name,
  );
}

function buildSkillProfileDiff(
  savedPreferences: SkillPreferences,
  draftPreferences: SkillPreferences,
  instructionDrafts: Record<SkillPresetId, string>,
) {
  const added: string[] = [];
  const removed: string[] = [];
  const instructionChanges: string[] = [];

  for (const preset of SKILL_PRESETS) {
    const saved = savedPreferences[preset.id];
    const draft = draftPreferences[preset.id];
    const savedEnabled = Boolean(saved?.enabled);
    const draftEnabled = Boolean(draft?.enabled);
    const draftInstruction = (instructionDrafts[preset.id] ?? draft?.customInstructions ?? "").trim();
    const savedInstruction = (saved?.customInstructions ?? "").trim();

    if (!savedEnabled && draftEnabled) {
      added.push(preset.name);
    }
    if (savedEnabled && !draftEnabled) {
      removed.push(preset.name);
    }
    if (draftInstruction !== savedInstruction) {
      instructionChanges.push(preset.name);
    }
  }

  const totalChanges = added.length + removed.length + instructionChanges.length;
  const summary = totalChanges === 0
    ? "No changes"
    : [
        added.length > 0 ? `${added.length} added` : null,
        removed.length > 0 ? `${removed.length} removed` : null,
        instructionChanges.length > 0 ? `${instructionChanges.length} instruction edits` : null,
      ]
        .filter(Boolean)
        .join(" · ");
  const details = totalChanges === 0
    ? "Draft matches the saved workspace profile."
    : [
        added.length > 0 ? `Added: ${added.join(", ")}` : null,
        removed.length > 0 ? `Removed: ${removed.join(", ")}` : null,
        instructionChanges.length > 0 ? `Edited: ${instructionChanges.join(", ")}` : null,
      ]
        .filter(Boolean)
        .join(". ");

  return {
    added,
    removed,
    instructionChanges,
    totalChanges,
    summary,
    details,
  };
}

function parseImportedPreferences(
  rawValue: string,
  currentPreferences: WorkbenchPreferences,
): WorkbenchPreferences | null {
  try {
    const parsed = JSON.parse(rawValue) as Partial<WorkbenchPreferences>;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }

    const nextPreferences: WorkbenchPreferences = { ...currentPreferences };
    let recognizedValueCount = 0;

    if (parsed.theme !== undefined) {
      if (!isThemePreference(parsed.theme)) {
        return null;
      }
      nextPreferences.theme = parsed.theme;
      recognizedValueCount += 1;
    }

    if (parsed.density !== undefined) {
      if (!isDensityPreference(parsed.density)) {
        return null;
      }
      nextPreferences.density = parsed.density;
      recognizedValueCount += 1;
    }

    if (parsed.defaultSourceSnippets !== undefined) {
      if (!isSourceSnippetPreference(parsed.defaultSourceSnippets)) {
        return null;
      }
      nextPreferences.defaultSourceSnippets = parsed.defaultSourceSnippets;
      recognizedValueCount += 1;
    }

    if (parsed.landingTab !== undefined) {
      if (!isLandingTabPreference(parsed.landingTab)) {
        return null;
      }
      nextPreferences.landingTab = parsed.landingTab;
      recognizedValueCount += 1;
    }

    if (parsed.apiBaseUrl !== undefined) {
      if (!isValidHttpUrl(parsed.apiBaseUrl)) {
        return null;
      }
      nextPreferences.apiBaseUrl = normalizeApiBaseUrl(parsed.apiBaseUrl);
      recognizedValueCount += 1;
    }

    if (parsed.brandInitials !== undefined) {
      if (!isBrandInitialsPreference(parsed.brandInitials)) {
        return null;
      }
      nextPreferences.brandInitials = normalizeBrandInitials(
        parsed.brandInitials,
      );
      recognizedValueCount += 1;
    }

    if (parsed.productName !== undefined) {
      if (!isProductNamePreference(parsed.productName)) {
        return null;
      }
      nextPreferences.productName = normalizeProductName(parsed.productName);
      recognizedValueCount += 1;
    }

    if (parsed.accentColor !== undefined) {
      if (!isAccentColorPreference(parsed.accentColor)) {
        return null;
      }
      nextPreferences.accentColor = parsed.accentColor;
      recognizedValueCount += 1;
    }

    if (parsed.skillPreferences !== undefined) {
      nextPreferences.skillPreferences = normalizeSkillPreferences(
        parsed.skillPreferences,
      );
      recognizedValueCount += 1;
    }

    return recognizedValueCount > 0 ? nextPreferences : null;
  } catch {
    return null;
  }
}

function isThemePreference(
  value: unknown,
): value is WorkbenchPreferences["theme"] {
  return value === "system" || value === "light" || value === "dark";
}

function isDensityPreference(
  value: unknown,
): value is WorkbenchPreferences["density"] {
  return value === "comfortable" || value === "compact";
}

function isSourceSnippetPreference(
  value: unknown,
): value is WorkbenchPreferences["defaultSourceSnippets"] {
  return value === 3 || value === 5 || value === 8 || value === 10;
}

function isLandingTabPreference(
  value: unknown,
): value is WorkbenchPreferences["landingTab"] {
  return (
    value === "overview" ||
    value === "ask" ||
    value === "models" ||
    value === "reports" ||
    value === "actions" ||
    value === "activity" ||
    value === "settings"
  );
}

function isValidHttpUrl(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function normalizeApiBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function isBrandInitialsPreference(value: unknown): value is string {
  return typeof value === "string" && normalizeBrandInitials(value).length > 0;
}

function normalizeBrandInitials(value: string): string {
  return (
    value
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "")
      .slice(0, 3) || "AI"
  );
}

function isProductNamePreference(value: unknown): value is string {
  return typeof value === "string" && normalizeProductName(value).length > 0;
}

function normalizeProductName(value: string): string {
  const normalized = value.trim().replace(/\s+/g, " ").slice(0, 48);
  return normalized || "AI Private Workspace";
}

function isAccentColorPreference(
  value: unknown,
): value is WorkbenchPreferences["accentColor"] {
  return (
    value === "green" ||
    value === "blue" ||
    value === "purple" ||
    value === "orange"
  );
}

function formatMode(value: string) {
  return value.replace(/_/g, " ");
}
