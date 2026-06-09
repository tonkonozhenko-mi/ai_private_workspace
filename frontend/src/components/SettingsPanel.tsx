import type { ReactNode } from "react";
import { API_BASE_URL } from "../api/client";
import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface SettingsPanelProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
}

export function SettingsPanel({ dashboard, modelsSummary }: SettingsPanelProps) {
  const summary = dashboard.summary;
  const contextReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";

  return (
    <div className="settings-page">
      <section className="panel settings-hero-panel">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Keep local workbench preferences clear.</h1>
          <p>
            Settings are introduced as a safe overview first. Saving preferences will be added only when the product flow is stable.
          </p>
        </div>
        <StatusBadge label="Read only" tone="info" size="md" />
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
          description="The frontend talks to your local backend. This value is shown for clarity and is not editable yet."
          badge="Connected"
        >
          <SettingsRow label="Backend URL" value={API_BASE_URL} code />
          <SettingsRow label="Scope" value="Local browser to local API" />
        </SettingsSection>

        <SettingsSection
          eyebrow="Appearance"
          title="Display"
          description="Theme controls will be added later. The current interface keeps the calm light workspace with dark sidebar."
          badge="Planned"
          tone="neutral"
        >
          <SettingsRow label="Theme" value="System-style light workspace" />
          <SettingsRow label="Density" value="Comfortable" />
        </SettingsSection>

        <SettingsSection
          eyebrow="Ask defaults"
          title="Workspace questions"
          description="Ask stays manual. Default source snippet count can be made configurable in a future task."
          badge={contextReady ? "Ready" : "Needs context"}
          tone={contextReady ? "success" : "warning"}
        >
          <SettingsRow label="Default source snippets" value="5" />
          <SettingsRow label="Answer mode" value="Source-backed local answer" />
        </SettingsSection>

        <SettingsSection
          eyebrow="AI defaults"
          title="Models"
          description="Chosen models are managed from the Models tab. Settings will later provide global defaults."
          badge={localAIReady ? "Ready" : "Review"}
          tone={localAIReady ? "success" : "warning"}
        >
          <SettingsRow label="AI answer model" value={modelsSummary.selected_llm ?? "Not selected"} code />
          <SettingsRow label="Search context model" value={modelsSummary.selected_embedding ?? "Not selected"} code />
        </SettingsSection>
      </div>

      <section className="panel settings-safety-panel">
        <div>
          <p className="eyebrow">Safety</p>
          <h2>Local-only posture</h2>
          <p>
            This screen is informational. The frontend does not execute shell commands, rebuild context, restart the backend, or change models automatically.
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

function formatMode(value: string) {
  return value.replace(/_/g, " ");
}
