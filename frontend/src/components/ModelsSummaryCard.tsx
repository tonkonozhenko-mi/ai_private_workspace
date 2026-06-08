import type { WorkspaceModelsDashboardSummary } from "../api/types";

interface ModelsSummaryCardProps {
  summary: WorkspaceModelsDashboardSummary;
}

export function ModelsSummaryCard({ summary }: ModelsSummaryCardProps) {
  return (
    <section className="panel models-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Models</p>
          <h2>Local AI status</h2>
        </div>
        <span className={`status-badge status-${summary.overall_status}`}>
          {formatLabel(summary.overall_status)}
        </span>
      </div>

      <dl className="model-summary-list">
        <ModelRow label="Selected LLM" value={summary.selected_llm} />
        <ModelRow label="Selected embedding" value={summary.selected_embedding} />
        <ModelRow label="Active LLM" value={summary.active_llm} />
        <ModelRow label="Active embedding" value={summary.active_embedding} />
        <ModelRow label="Top recommendation" value={summary.top_recommended_model} />
      </dl>

      <div className="model-summary-footer">
        <span>
          <strong>{summary.warnings_count}</strong> warnings
        </span>
        <span>
          <strong>{summary.performance_models_count}</strong> models measured
        </span>
      </div>

      <div className="next-action-strip">
        <span>Next model action</span>
        <strong>{summary.primary_next_action_title ?? "Review model status"}</strong>
      </div>
    </section>
  );
}

function ModelRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value ?? "Not selected"}</dd>
    </div>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
