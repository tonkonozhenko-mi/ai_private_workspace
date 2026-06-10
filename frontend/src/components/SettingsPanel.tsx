import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { WorkbenchPreferences } from "../App";
import { DEFAULT_API_BASE_URL } from "../api/client";
import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";
import {
  DEFAULT_FILE_INDEXING_PREFERENCES,
  countPatterns,
  normalizeFileIndexingPreferences,
  normalizePatternText,
} from "./fileIndexingPreferences";
import { StatusBadge } from "./StatusBadge";
import {
  DEFAULT_SKILL_PREFERENCES,
  SKILL_PRESETS,
  normalizeSkillPreferences,
  type SkillPresetId,
  type SkillPreferences,
} from "./skillLibrary";

interface SettingsPanelProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  preferences: WorkbenchPreferences;
  onPreferencesChange: (preferences: WorkbenchPreferences) => void;
  onResetPreferences: () => void;
  onOpenModels: () => void;
}

export function SettingsPanel({
  dashboard,
  modelsSummary,
  preferences,
  onPreferencesChange,
  onResetPreferences,
  onOpenModels,
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
  const [savedSkillId, setSavedSkillId] = useState<SkillPresetId | null>(null);
  const [fileRulesDraft, setFileRulesDraft] = useState(() => ({
    includePatterns: preferences.fileIndexingPreferences.includePatterns,
    excludePatterns: preferences.fileIndexingPreferences.excludePatterns,
  }));
  const [fileRulesMessage, setFileRulesMessage] = useState("File rules saved in this browser.");

  useEffect(() => {
    setBackendUrlDraft(preferences.apiBaseUrl);
  }, [preferences.apiBaseUrl]);

  useEffect(() => {
    setInstructionDrafts(buildInstructionDrafts(preferences.skillPreferences));
  }, [preferences.skillPreferences]);

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

  function saveFileRules() {
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
    updatePreference("fileIndexingPreferences", nextPreferences);
    setFileRulesDraft({
      includePatterns: nextPreferences.includePatterns,
      excludePatterns: nextPreferences.excludePatterns,
    });
    setFileRulesMessage("File rules saved in this browser.");
  }

  function resetFileRules() {
    updatePreference("fileIndexingPreferences", DEFAULT_FILE_INDEXING_PREFERENCES);
    setFileRulesDraft({
      includePatterns: DEFAULT_FILE_INDEXING_PREFERENCES.includePatterns,
      excludePatterns: DEFAULT_FILE_INDEXING_PREFERENCES.excludePatterns,
    });
    setFileRulesMessage("File rules reset to safe defaults.");
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
          <SettingsRow label="Product name" value="AI Private Workspace" />
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
          <SettingsRow label="Storage" value="Saved locally in this browser" />
        </SettingsSection>


        <SettingsSection
          eyebrow="File selection"
          title="Files and search context"
          description="Choose browser-local file rules before rebuilding search context. These rules are prepared here first and will be connected to indexing actions in the next step."
          badge="Local rules"
          tone="info"
        >
          <div className="settings-file-rule-summary">
            <div>
              <strong>{countPatterns(fileRulesDraft.includePatterns)}</strong>
              <span>include rules</span>
            </div>
            <div>
              <strong>{countPatterns(fileRulesDraft.excludePatterns)}</strong>
              <span>exclude rules</span>
            </div>
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
            <button type="button" className="primary-button" onClick={saveFileRules}>
              Save file rules
            </button>
            <button type="button" className="ghost-button" onClick={resetFileRules}>
              Reset defaults
            </button>
            <span>{fileRulesMessage}</span>
          </div>
          <p className="settings-helper-note">
            Safe defaults include source, docs, infrastructure, and CI/CD files while excluding dependencies, caches, build outputs, archives, and logs.
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
              Start from safe presets, then tune instructions for this browser.
              These preferences do not change backend runtime or rebuild
              context.
            </p>
          </div>
          <StatusBadge
            label={`${SKILL_PRESETS.filter((preset) => preferences.skillPreferences[preset.id]?.enabled).length} active`}
            tone="info"
          />
        </div>

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
                      ? "Saved locally"
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
