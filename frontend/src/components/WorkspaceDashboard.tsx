import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";
import { ModelsSummaryCard } from "./ModelsSummaryCard";
import { StatusBadge } from "./StatusBadge";

interface WorkspaceDashboardProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenModels: () => void;
}

export function WorkspaceDashboard({
  dashboard,
  modelsSummary,
  onOpenModels,
}: WorkspaceDashboardProps) {
  const summary = dashboard.summary;
  const indexStatus = summary.index_status;

  return (
    <>
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Workspace overview</p>
          <h1>{dashboard.workspace_name}</h1>
          <p className="workspace-header-path">{summary.project_path}</p>
        </div>
        <div className="workspace-header-status">
          <StatusBadge label={dashboard.status} size="md" />
          <span>{formatLabel(dashboard.assistant_mode)} assistant</span>
        </div>
      </header>

      {modelsSummary.overall_status !== "ready" ? (
        <LocalAISetupWarning
          summary={modelsSummary}
          onOpenModels={onOpenModels}
        />
      ) : null}

      <section className="metric-grid" aria-label="Workspace status">
        <article className="metric-card">
          <span className="metric-label">Detected skills</span>
          <strong>{summary.detected_skills_count}</strong>
          <span>{summary.has_scan ? "Latest scan available" : "Scan not run"}</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Index</span>
          <strong className="metric-word">{formatLabel(indexStatus.status)}</strong>
          <span>{indexStatus.chunks_count} context chunks</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Quick start</span>
          <strong className="metric-word">
            {formatLabel(dashboard.quick_start.status)}
          </strong>
          <span>{dashboard.primary_next_action_title ?? "No next action"}</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Recent activity</span>
          <strong>{dashboard.recent_events.length}</strong>
          <span>events shown</span>
        </article>
      </section>

      <div className="overview-grid">
        <ModelsSummaryCard summary={modelsSummary} compact />
        <section className="panel overview-next-action">
          <div>
            <p className="eyebrow">Primary next action</p>
            <h2>{dashboard.primary_next_action_title ?? "Review workspace"}</h2>
            <p>
              The UI Action Catalog keeps this recommendation deterministic and
              read-only until action execution is designed.
            </p>
          </div>
          <StatusBadge label="recommended" size="md" />
        </section>
      </div>
    </>
  );
}

function LocalAISetupWarning({
  summary,
  onOpenModels,
}: {
  summary: WorkspaceModelsDashboardSummary;
  onOpenModels: () => void;
}) {
  return (
    <section className="panel local-ai-setup-warning">
      <div className="local-ai-setup-warning-heading">
        <div>
          <p className="eyebrow">Models and runtime</p>
          <h2>Local AI setup needs attention</h2>
        </div>
        <StatusBadge label={summary.overall_status} size="md" />
      </div>

      <div className="local-ai-runtime-comparison">
        <ModelComparisonRow
          label="LLM"
          selected={summary.selected_llm}
          active={summary.active_llm}
        />
        <ModelComparisonRow
          label="Embedding"
          selected={summary.selected_embedding}
          active={summary.active_embedding}
        />
      </div>

      <div className="local-ai-setup-messages">
        {summary.can_ask_with_selected_llm ? (
          <p className="is-available">
            Selected LLM can already be used for Ask.
          </p>
        ) : null}
        {!summary.can_search_with_selected_embedding ? (
          <p className="is-warning">
            Selected embedding is not active for search yet.
          </p>
        ) : null}
      </div>

      <div className="local-ai-setup-next">
        <div>
          <span>Primary model action</span>
          <strong>
            {summary.primary_next_action_title ?? "Review local AI setup"}
          </strong>
        </div>
        <div className="local-ai-setup-navigation">
          <p>Open the Models tab to review activation steps.</p>
          <button
            className="local-ai-models-button"
            type="button"
            onClick={onOpenModels}
          >
            Open Models tab
          </button>
        </div>
      </div>
    </section>
  );
}

function ModelComparisonRow({
  label,
  selected,
  active,
}: {
  label: string;
  selected: string | null;
  active: string;
}) {
  return (
    <div>
      <strong>{label}</strong>
      <dl>
        <div>
          <dt>Selected</dt>
          <dd>{selected ?? "Not selected"}</dd>
        </div>
        <div>
          <dt>Active</dt>
          <dd>{active}</dd>
        </div>
      </dl>
    </div>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
