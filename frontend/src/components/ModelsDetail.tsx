import type {
  LocalAIActivationGuide,
  ModelPerformanceItem,
  WorkspaceModelRecommendation,
  WorkspaceModelsDashboard,
} from "../api/types";
import { CopyButton } from "./CopyButton";

interface ModelsDetailProps {
  dashboard: WorkspaceModelsDashboard;
  activationGuide: LocalAIActivationGuide;
}

export function ModelsDetail({
  dashboard,
  activationGuide,
}: ModelsDetailProps) {
  const usage = dashboard.usage_plan;

  return (
    <div className="models-detail">
      <section className="panel models-state-panel">
        <PanelHeading
          eyebrow="Workspace models"
          title="Selected and active runtime"
          status={dashboard.overall_status}
        />
        <div className="model-runtime-grid">
          <RuntimeModel
            label="Selected LLM"
            provider={dashboard.selected_llm_provider}
            model={dashboard.selected_llm_model}
            status={dashboard.selection_status.llm_status.status}
          />
          <RuntimeModel
            label="Active LLM"
            provider={usage.active_llm_provider}
            model={usage.active_llm_model}
            status={
              dashboard.selection_status.llm_status.matches_active_runtime
                ? "ready"
                : "runtime_mismatch"
            }
          />
          <RuntimeModel
            label="Selected embedding"
            provider={dashboard.selected_embedding_provider}
            model={dashboard.selected_embedding_model}
            status={dashboard.selection_status.embedding_status.status}
          />
          <RuntimeModel
            label="Active embedding"
            provider={usage.active_embedding_provider}
            model={usage.active_embedding_model}
            status={
              dashboard.selection_status.embedding_status.matches_active_runtime
                ? "ready"
                : "runtime_mismatch"
            }
          />
        </div>
      </section>

      <section className="panel model-readiness-panel">
        <PanelHeading
          eyebrow="Usage readiness"
          title="What works now"
          status={dashboard.usage_plan.can_use_selected_models_fully ? "ready" : "needs_attention"}
        />
        <div className="readiness-list">
          <ReadinessRow
            label="Ask with selected LLM"
            ready={usage.can_ask_with_selected_llm}
          />
          <ReadinessRow
            label="Search with selected embedding"
            ready={usage.can_search_with_selected_embedding}
          />
          <ReadinessRow
            label="Index with selected embedding"
            ready={usage.can_index_with_selected_embedding}
          />
        </div>
        <div className="next-action-strip">
          <span>Primary next action</span>
          <strong>
            {dashboard.primary_next_action_title ?? "Review model selection"}
          </strong>
        </div>
      </section>

      <section className="panel recommendations-panel">
        <PanelHeading eyebrow="Recommendations" title="Top model options" />
        {dashboard.recommendations.recommendations.length > 0 ? (
          <div className="model-ranking-list">
            {dashboard.recommendations.recommendations
              .slice(0, 3)
              .map((recommendation) => (
                <RecommendationRow
                  key={`${recommendation.model.provider}/${recommendation.model.model_name}`}
                  recommendation={recommendation}
                />
              ))}
          </div>
        ) : (
          <EmptyModelState text="No model recommendations are available yet." />
        )}
      </section>

      <section className="panel performance-panel">
        <PanelHeading eyebrow="Workspace history" title="Model performance" />
        {dashboard.performance_summary.items.length > 0 ? (
          <div className="model-ranking-list">
            {dashboard.performance_summary.items
              .slice(0, 3)
              .map((item) => (
                <PerformanceRow
                  key={`${item.provider}/${item.model}`}
                  item={item}
                />
              ))}
          </div>
        ) : (
          <EmptyModelState text="No experiment performance has been recorded yet." />
        )}
      </section>

      <section className="panel activation-panel">
        <PanelHeading
          eyebrow="Instructions only"
          title="Local AI activation guide"
          status={activationGuide.overall_status}
        />
        <p className="panel-intro">
          These commands are displayed as setup instructions. The frontend does
          not execute them or create command proposals.
        </p>
        <p className="activation-safety-note">
          Commands are copied only. The frontend never executes them.
        </p>
        <div className="activation-step-list">
          {activationGuide.steps.map((step) => (
            <article className="activation-step" key={step.id}>
              <div className="activation-step-heading">
                <div>
                  <span>{formatLabel(step.category)}</span>
                  <strong>{step.title}</strong>
                </div>
                <StatusBadge status={step.status} />
              </div>
              <p>{step.description}</p>
              <small>{step.reason}</small>
              <CommandList
                primaryCommand={step.command}
                commands={step.commands ?? []}
              />
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function PanelHeading({
  eyebrow,
  title,
  status,
}: {
  eyebrow: string;
  title: string;
  status?: string;
}) {
  return (
    <div className="panel-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      {status ? <StatusBadge status={status} /> : null}
    </div>
  );
}

function RuntimeModel({
  label,
  provider,
  model,
  status,
}: {
  label: string;
  provider: string | null;
  model: string | null;
  status: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{provider && model ? `${provider}/${model}` : "Not selected"}</strong>
      <StatusBadge status={status} />
    </article>
  );
}

function ReadinessRow({ label, ready }: { label: string; ready: boolean }) {
  return (
    <div>
      <span>{label}</span>
      <StatusBadge status={ready ? "ready" : "blocked"} />
    </div>
  );
}

function RecommendationRow({
  recommendation,
}: {
  recommendation: WorkspaceModelRecommendation;
}) {
  return (
    <article className="model-ranking-row">
      <div>
        <strong>{recommendation.model.display_name}</strong>
        <code>
          {recommendation.model.provider}/{recommendation.model.model_name}
        </code>
      </div>
      <div className="model-ranking-metrics">
        <span>
          Score <strong>{recommendation.final_score}</strong>
        </span>
        <span>
          Warnings <strong>{recommendation.warnings.length}</strong>
        </span>
      </div>
    </article>
  );
}

function PerformanceRow({ item }: { item: ModelPerformanceItem }) {
  return (
    <article className="model-ranking-row">
      <div>
        <strong>
          {item.provider}/{item.model}
        </strong>
        <span>
          {item.average_rating === null
            ? "No ratings yet"
            : `${item.average_rating.toFixed(1)} average rating`}
        </span>
      </div>
      <div className="model-ranking-metrics">
        <span>
          Preferred <strong>{item.preferred_votes}</strong>
        </span>
        <span>
          Score <strong>{item.score}</strong>
        </span>
      </div>
    </article>
  );
}

function CommandList({
  primaryCommand,
  commands,
}: {
  primaryCommand: string | null;
  commands: string[];
}) {
  const orderedCommands = Array.from(
    new Set([...(primaryCommand ? [primaryCommand] : []), ...commands]),
  );

  if (orderedCommands.length === 0) {
    return null;
  }

  return (
    <div className="instruction-commands">
      <span>Command instructions</span>
      {orderedCommands.map((command, index) => (
        <div
          className={`instruction-command-row${
            command === primaryCommand ? " is-primary" : ""
          }`}
          key={`${index}-${command}`}
        >
          <div>
            <span>
              {command === primaryCommand ? "Primary command" : "Alternative"}
            </span>
            <code>{command}</code>
          </div>
          <CopyButton text={command} />
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`status-badge status-${status}`}>
      {formatLabel(status)}
    </span>
  );
}

function EmptyModelState({ text }: { text: string }) {
  return <p className="empty-panel-state">{text}</p>;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
