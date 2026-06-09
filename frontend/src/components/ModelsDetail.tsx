import { useEffect, useMemo, useState } from "react";

import { updateWorkspaceModelSelection } from "../api/client";
import type {
  LocalAIActivationGuide,
  ModelPerformanceItem,
  UpdateWorkspaceModelSelectionRequest,
  WorkspaceModelRecommendation,
  WorkspaceModelsDashboard,
} from "../api/types";
import { CopyButton } from "./CopyButton";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface ModelsDetailProps {
  workspaceId: string;
  dashboard: WorkspaceModelsDashboard;
  activationGuide: LocalAIActivationGuide;
  onSelectionUpdated: () => Promise<void> | void;
}

interface ModelOption {
  provider: string;
  model: string;
  label: string;
  source: string;
}

export function ModelsDetail({
  workspaceId,
  dashboard,
  activationGuide,
  onSelectionUpdated,
}: ModelsDetailProps) {
  const usage = dashboard.usage_plan;
  const llmOptions = useMemo(
    () =>
      buildModelOptions({
        modelType: "llm",
        selectedProvider: dashboard.selected_llm_provider,
        selectedModel: dashboard.selected_llm_model,
        activeProvider: usage.active_llm_provider,
        activeModel: usage.active_llm_model,
        recommendations: dashboard.recommendations.recommendations,
      }),
    [
      dashboard.selected_llm_model,
      dashboard.selected_llm_provider,
      dashboard.recommendations.recommendations,
      usage.active_llm_model,
      usage.active_llm_provider,
    ],
  );
  const embeddingOptions = useMemo(
    () =>
      buildModelOptions({
        modelType: "embedding",
        selectedProvider: dashboard.selected_embedding_provider,
        selectedModel: dashboard.selected_embedding_model,
        activeProvider: usage.active_embedding_provider,
        activeModel: usage.active_embedding_model,
        recommendations: dashboard.recommendations.recommendations,
      }),
    [
      dashboard.selected_embedding_model,
      dashboard.selected_embedding_provider,
      dashboard.recommendations.recommendations,
      usage.active_embedding_model,
      usage.active_embedding_provider,
    ],
  );
  const reindexReason = getModelReindexReason(dashboard);

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

      <ModelSelectionEditor
        workspaceId={workspaceId}
        selectedLlmProvider={dashboard.selected_llm_provider}
        selectedLlmModel={dashboard.selected_llm_model}
        selectedEmbeddingProvider={dashboard.selected_embedding_provider}
        selectedEmbeddingModel={dashboard.selected_embedding_model}
        llmOptions={llmOptions}
        embeddingOptions={embeddingOptions}
        reindexReason={reindexReason}
        onSelectionUpdated={onSelectionUpdated}
      />

      <section className="panel model-readiness-panel">
        <PanelHeading
          eyebrow="Usage readiness"
          title="What works now"
          status={
            dashboard.usage_plan.can_use_selected_models_fully
              ? "ready"
              : "needs_attention"
          }
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
          <EmptyState
            title="No model recommendations are available yet"
            compact
          />
        )}
      </section>

      <section className="panel performance-panel">
        <PanelHeading eyebrow="Workspace history" title="Model performance" />
        {dashboard.performance_summary.items.length > 0 ? (
          <div className="model-ranking-list">
            {dashboard.performance_summary.items.slice(0, 3).map((item) => (
              <PerformanceRow
                key={`${item.provider}/${item.model}`}
                item={item}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No experiment performance has been recorded yet"
            compact
          />
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
                <StatusBadge label={step.status} />
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

function ModelSelectionEditor({
  workspaceId,
  selectedLlmProvider,
  selectedLlmModel,
  selectedEmbeddingProvider,
  selectedEmbeddingModel,
  llmOptions,
  embeddingOptions,
  reindexReason,
  onSelectionUpdated,
}: {
  workspaceId: string;
  selectedLlmProvider: string | null;
  selectedLlmModel: string | null;
  selectedEmbeddingProvider: string | null;
  selectedEmbeddingModel: string | null;
  llmOptions: ModelOption[];
  embeddingOptions: ModelOption[];
  reindexReason: string | null;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const [llmValue, setLlmValue] = useState(
    toOptionValue(selectedLlmProvider, selectedLlmModel) ??
      toOptionValue(llmOptions[0]?.provider, llmOptions[0]?.model) ??
      "",
  );
  const [embeddingValue, setEmbeddingValue] = useState(
    toOptionValue(selectedEmbeddingProvider, selectedEmbeddingModel) ??
      toOptionValue(
        embeddingOptions[0]?.provider,
        embeddingOptions[0]?.model,
      ) ??
      "",
  );
  const [savingType, setSavingType] = useState<"llm" | "embedding" | null>(
    null,
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLlmValue(
      toOptionValue(selectedLlmProvider, selectedLlmModel) ??
        toOptionValue(llmOptions[0]?.provider, llmOptions[0]?.model) ??
        "",
    );
  }, [llmOptions, selectedLlmModel, selectedLlmProvider]);

  useEffect(() => {
    setEmbeddingValue(
      toOptionValue(selectedEmbeddingProvider, selectedEmbeddingModel) ??
        toOptionValue(
          embeddingOptions[0]?.provider,
          embeddingOptions[0]?.model,
        ) ??
        "",
    );
  }, [embeddingOptions, selectedEmbeddingModel, selectedEmbeddingProvider]);

  async function saveSelection(modelType: "llm" | "embedding") {
    const selectedValue = modelType === "llm" ? llmValue : embeddingValue;
    const parsed = parseOptionValue(selectedValue);
    if (!parsed) {
      setError("Select a model before saving.");
      setMessage(null);
      return;
    }

    const payload: UpdateWorkspaceModelSelectionRequest = {
      provider: parsed.provider,
      model: parsed.model,
      model_type: modelType,
      selected_reason:
        modelType === "llm"
          ? "Selected from the frontend Models tab."
          : "Selected from the frontend Models tab for workspace retrieval.",
    };

    setSavingType(modelType);
    setError(null);
    setMessage(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, payload);
      setMessage(
        `${modelType === "llm" ? "LLM" : "Embedding"} selection saved. Runtime settings were not changed.`,
      );
      await onSelectionUpdated();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSavingType(null);
    }
  }

  return (
    <section className="panel model-selection-editor-panel">
      <PanelHeading
        eyebrow="Selection editor"
        title="Change workspace model preferences"
        status="manual submit"
      />
      <p className="panel-intro">
        Saving changes only updates workspace preference metadata. It does not
        restart the backend, run reindexing, or execute commands.
      </p>

      <div className="model-selection-grid">
        <ModelSelectionControl
          label="Selected LLM"
          description="Used by Ask when the selected provider/model is supported by the active runtime."
          value={llmValue}
          options={llmOptions}
          selectedProvider={selectedLlmProvider}
          selectedModel={selectedLlmModel}
          disabled={savingType !== null}
          onChange={setLlmValue}
          onSave={() => void saveSelection("llm")}
          isSaving={savingType === "llm"}
        />
        <ModelSelectionControl
          label="Selected embedding"
          description="Requires matching active embedding runtime and reindexing when the embedding space changes."
          value={embeddingValue}
          options={embeddingOptions}
          selectedProvider={selectedEmbeddingProvider}
          selectedModel={selectedEmbeddingModel}
          disabled={savingType !== null}
          onChange={setEmbeddingValue}
          onSave={() => void saveSelection("embedding")}
          isSaving={savingType === "embedding"}
        />
      </div>

      <div className="model-selection-safety-note">
        <StatusBadge label="instructions only" />
        <span>
          Backend restart and reindex steps are still manual. Use the activation
          guide below after changing runtime-sensitive selections.
        </span>
      </div>

      {reindexReason ? (
        <ModelReindexGuidance
          workspaceId={workspaceId}
          reason={reindexReason}
        />
      ) : null}

      {message ? <p className="model-selection-message">{message}</p> : null}
      {error ? <p className="model-selection-error">{error}</p> : null}
    </section>
  );
}

function ModelSelectionControl({
  label,
  description,
  value,
  options,
  selectedProvider,
  selectedModel,
  disabled,
  onChange,
  onSave,
  isSaving,
}: {
  label: string;
  description: string;
  value: string;
  options: ModelOption[];
  selectedProvider: string | null;
  selectedModel: string | null;
  disabled: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
  isSaving: boolean;
}) {
  return (
    <article className="model-selection-card">
      <div className="model-selection-card-heading">
        <div>
          <span>{label}</span>
          <strong>
            {selectedProvider && selectedModel
              ? `${selectedProvider}/${selectedModel}`
              : "Not selected"}
          </strong>
        </div>
        <StatusBadge label="preference" />
      </div>
      <p>{description}</p>
      <label>
        <span>Choose model</span>
        <select
          value={value}
          disabled={disabled || options.length === 0}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.length === 0 ? (
            <option value="">No options available</option>
          ) : (
            options.map((option) => (
              <option
                key={`${option.provider}/${option.model}`}
                value={`${option.provider}||${option.model}`}
              >
                {option.label}
              </option>
            ))
          )}
        </select>
      </label>
      <div className="model-option-source-list">
        {options.slice(0, 3).map((option) => (
          <span key={`${option.provider}/${option.model}/${option.source}`}>
            {option.source}: {option.provider}/{option.model}
          </span>
        ))}
      </div>
      <button
        className="model-selection-save-button"
        type="button"
        disabled={disabled || options.length === 0}
        onClick={onSave}
      >
        {isSaving ? "Saving…" : `Save ${label}`}
      </button>
    </article>
  );
}

function ModelReindexGuidance({
  workspaceId,
  reason,
}: {
  workspaceId: string;
  reason: string;
}) {
  const command = `curl -X POST http://127.0.0.1:8000/workspaces/${workspaceId}/index`;

  return (
    <article className="reindex-guidance model-reindex-guidance">
      <div>
        <StatusBadge label="copy only" />
        <strong>Reindex guidance</strong>
      </div>
      <p>{reason}</p>
      <div className="reindex-command-row">
        <code title={command}>{command}</code>
        <CopyButton text={command} />
      </div>
      <small>
        Changing an LLM does not require reindexing. Reindex only when you
        intentionally changed the embedding model or vector store, or when the
        workspace index was built for a different retrieval runtime.
      </small>
    </article>
  );
}

function getModelReindexReason(
  dashboard: WorkspaceModelsDashboard,
): string | null {
  const embeddingStatus = dashboard.selection_status.embedding_status;
  const selectedEmbedding =
    dashboard.selected_embedding_provider && dashboard.selected_embedding_model
      ? `${dashboard.selected_embedding_provider}/${dashboard.selected_embedding_model}`
      : null;
  const activeEmbedding = `${dashboard.usage_plan.active_embedding_provider}/${dashboard.usage_plan.active_embedding_model}`;

  if (
    selectedEmbedding &&
    embeddingStatus.matches_active_runtime &&
    dashboard.usage_plan.index_status !== "indexed"
  ) {
    return `Workspace index required. Selected embedding ${selectedEmbedding} already matches the active runtime, but workspace index status is ${dashboard.usage_plan.index_status}. Reindex to build searchable context.`;
  }

  if (embeddingStatus.requires_reindex) {
    if (selectedEmbedding && embeddingStatus.matches_active_runtime) {
      return `Workspace index required. Selected embedding ${selectedEmbedding} matches the active runtime, but the workspace does not have a usable index for search yet.`;
    }

    return selectedEmbedding
      ? `Selected embedding ${selectedEmbedding} differs from the active retrieval setup. Reindex after you intentionally switch the embedding runtime or vector store.`
      : "Selected embedding requires rebuilding the workspace index before search can use it reliably.";
  }

  if (
    selectedEmbedding &&
    activeEmbedding &&
    !dashboard.usage_plan.can_search_with_selected_embedding &&
    embeddingStatus.matches_active_runtime
  ) {
    return `Selected embedding ${selectedEmbedding} matches active runtime ${activeEmbedding}, but search is not ready. Reindex to rebuild the active retrieval collection.`;
  }

  return null;
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
      {status ? <StatusBadge label={status} size="md" /> : null}
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
      <strong>
        {provider && model ? `${provider}/${model}` : "Not selected"}
      </strong>
      <StatusBadge label={status} />
    </article>
  );
}

function ReadinessRow({ label, ready }: { label: string; ready: boolean }) {
  return (
    <div>
      <span>{label}</span>
      <StatusBadge label={ready ? "ready" : "blocked"} />
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
            <code title={command} tabIndex={0}>
              {command}
            </code>
          </div>
          <CopyButton text={command} />
        </div>
      ))}
    </div>
  );
}

function buildModelOptions({
  modelType,
  selectedProvider,
  selectedModel,
  activeProvider,
  activeModel,
  recommendations,
}: {
  modelType: "llm" | "embedding";
  selectedProvider: string | null;
  selectedModel: string | null;
  activeProvider: string;
  activeModel: string;
  recommendations: WorkspaceModelRecommendation[];
}): ModelOption[] {
  const options = new Map<string, ModelOption>();

  addOption(options, selectedProvider, selectedModel, "Current selection");
  addOption(options, activeProvider, activeModel, "Active runtime");

  for (const recommendation of recommendations) {
    if (recommendation.model.model_type === modelType) {
      addOption(
        options,
        recommendation.model.provider,
        recommendation.model.model_name,
        `Recommended ${recommendation.final_score}`,
      );
    }
  }

  return Array.from(options.values());
}

function addOption(
  options: Map<string, ModelOption>,
  provider: string | null | undefined,
  model: string | null | undefined,
  source: string,
) {
  if (!provider || !model) {
    return;
  }
  const key = toOptionValue(provider, model);
  if (!key || options.has(key)) {
    return;
  }
  options.set(key, {
    provider,
    model,
    label: `${provider}/${model} · ${source}`,
    source,
  });
}

function toOptionValue(
  provider: string | null | undefined,
  model: string | null | undefined,
) {
  if (!provider || !model) {
    return null;
  }
  return `${provider}||${model}`;
}

function parseOptionValue(value: string) {
  const [provider, model] = value.split("||");
  if (!provider || !model) {
    return null;
  }
  return { provider, model };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected request error";
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
