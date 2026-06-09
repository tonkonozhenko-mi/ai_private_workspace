import { useEffect, useState, type ReactNode } from "react";

import type { WorkbenchPreferences } from "../App";
import { API_BASE_URL } from "../api/client";
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

  function handleResetClick() {
    if (!resetRequested) {
      setResetRequested(true);
      return;
    }
    onResetPreferences();
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
          description="The frontend talks to your local backend. This value is shown for clarity and stays read-only."
          badge="Connected"
        >
          <SettingsRow label="Backend URL" value={API_BASE_URL} code />
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


      <section className="panel settings-reset-panel">
        <div>
          <p className="eyebrow">Local preferences</p>
          <h2>Reset browser settings</h2>
          <p>
            Reset theme, density, startup tab, and source snippet defaults for
            this browser only. Workspace data, models, and backend settings are
            not changed.
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

function formatMode(value: string) {
  return value.replace(/_/g, " ");
}
