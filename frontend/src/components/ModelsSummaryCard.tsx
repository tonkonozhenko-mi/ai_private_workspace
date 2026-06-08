import type { WorkspaceModelsDashboardSummary } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface ModelsSummaryCardProps {
  summary: WorkspaceModelsDashboardSummary;
  compact?: boolean;
  spacious?: boolean;
}

export function ModelsSummaryCard({
  summary,
  compact = false,
  spacious = false,
}: ModelsSummaryCardProps) {
  return (
    <section
      className={`panel models-panel${compact ? " is-compact" : ""}${
        spacious ? " is-spacious" : ""
      }`}
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Models</p>
          <h2>Local AI status</h2>
        </div>
        <StatusBadge label={summary.overall_status} size="md" />
      </div>

      <dl className="model-summary-list">
        <ModelRow label="Selected LLM" value={summary.selected_llm} />
        <ModelRow label="Selected embedding" value={summary.selected_embedding} />
        {!compact ? (
          <ModelRow label="Active LLM" value={summary.active_llm} />
        ) : null}
        {!compact ? (
          <ModelRow label="Active embedding" value={summary.active_embedding} />
        ) : null}
        <ModelRow
          label="Top recommendation"
          value={summary.top_recommended_model}
        />
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
