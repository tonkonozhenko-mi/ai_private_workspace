import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";
import { ModelsSummaryCard } from "./ModelsSummaryCard";

interface WorkspaceDashboardProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
}

export function WorkspaceDashboard({
  dashboard,
  modelsSummary,
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
          <span className={`status-badge status-${dashboard.status}`}>
            {formatLabel(dashboard.status)}
          </span>
          <span>{formatLabel(dashboard.assistant_mode)} assistant</span>
        </div>
      </header>

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
          <span className="status-badge status-recommended">recommended</span>
        </section>
      </div>
    </>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
