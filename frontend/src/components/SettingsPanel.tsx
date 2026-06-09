import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { WorkbenchPreferences } from "../App";
import { DEFAULT_API_BASE_URL } from "../api/client";
import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface SettingsPanelProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  preferences: WorkbenchPreferences;
  onPreferencesChange: (preferences: WorkbenchPreferences) => void;
  onResetPreferences: () => void;
}

export function SettingsPanel({
  dashboard,
  modelsSummary,
  preferences,
  onPreferencesChange,
  onResetPreferences,
}: SettingsPanelProps) {
  const summary = dashboard.summary;
  const contextReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
  const [resetRequested, setResetRequested] = useState(false);
  const [savedMessage, setSavedMessage] = useState("Saved in this browser");
  const [importDraft, setImportDraft] = useState("");
  const [transferMessage, setTransferMessage] = useState("Preferences can be copied or imported as JSON.");
  const [backendUrlDraft, setBackendUrlDraft] = useState(preferences.apiBaseUrl);
  const [connectionMessage, setConnectionMessage] = useState("Saved in this browser. Use Refresh after changing the backend URL.");

  useEffect(() => {
    setBackendUrlDraft(preferences.apiBaseUrl);
  }, [preferences.apiBaseUrl]);

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

  async function handleCopyPreferences() {
    setResetRequested(false);
    try {
      await navigator.clipboard.writeText(preferencesJson);
      setTransferMessage("Preferences JSON copied.");
    } catch {
      setTransferMessage("Copy is unavailable. Select the JSON and copy it manually.");
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
    setConnectionMessage("Backend URL saved. Refresh workspaces to use it.");
  }

  function handleResetBackendUrl() {
    setResetRequested(false);
    setBackendUrlDraft(DEFAULT_API_BASE_URL);
    updatePreference("apiBaseUrl", DEFAULT_API_BASE_URL);
    setConnectionMessage("Backend URL reset to the app default.");
  }

  function handleLoadCurrentPreferences() {
    setResetRequested(false);
    setImportDraft(preferencesJson);
    setTransferMessage("Current preferences loaded into the import box.");
  }

  function handleImportPreferences() {
    setResetRequested(false);
    const parsedPreferences = parseImportedPreferences(importDraft, preferences);
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
          <h1>Local workbench settings</h1>
          <p>
            Tune browser-local preferences for display, workspace questions, and
            startup behavior. Project setup and model runtime stay manual.
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
          description="Choose which local API this browser should use. This only changes the frontend connection target."
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
                  disabled={normalizeApiBaseUrl(backendUrlDraft) === preferences.apiBaseUrl}
                  onClick={handleSaveBackendUrl}
                >
                  Save URL
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={preferences.apiBaseUrl === DEFAULT_API_BASE_URL && backendUrlDraft === DEFAULT_API_BASE_URL}
                  onClick={handleResetBackendUrl}
                >
                  Reset default
                </button>
              </div>
              <p>{connectionMessage}</p>
            </div>
          </PreferenceGroup>
          <SettingsRow label="Current target" value={preferences.apiBaseUrl} code />
          <SettingsRow label="Default target" value={DEFAULT_API_BASE_URL} code />
          <SettingsRow label="Scope" value="Local browser to local API" />
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
                  Number(value) as WorkbenchPreferences["defaultSourceSnippets"],
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
          eyebrow="AI defaults"
          title="Models"
          description="Chosen models are still managed from the Models tab. Settings only shows the current workspace defaults."
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
        </SettingsSection>
      </div>


      <section className="panel settings-transfer-panel">
        <div className="settings-transfer-heading">
          <div>
            <p className="eyebrow">Local preferences</p>
            <h2>Export or import browser settings</h2>
            <p>
              Copy these preferences to reuse the same UI defaults in another
              browser. Import only changes this browser-local UI state.
            </p>
          </div>
          <StatusBadge label="JSON only" tone="neutral" />
        </div>

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
  "apiBaseUrl": "http://127.0.0.1:8000"
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
      </section>

      <section className="panel settings-reset-panel">
        <div>
          <p className="eyebrow">Local preferences</p>
          <h2>Reset browser settings</h2>
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
            className={resetRequested ? "danger-button is-confirming" : "danger-button"}
            onClick={handleResetClick}
          >
            {resetRequested ? "Confirm reset" : "Reset local preferences"}
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

    return recognizedValueCount > 0 ? nextPreferences : null;
  } catch {
    return null;
  }
}

function isThemePreference(value: unknown): value is WorkbenchPreferences["theme"] {
  return value === "system" || value === "light" || value === "dark";
}

function isDensityPreference(value: unknown): value is WorkbenchPreferences["density"] {
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

function formatMode(value: string) {
  return value.replace(/_/g, " ");
}
