import { useEffect, useMemo, useState } from "react";

import {
  getModelExperimentRatings,
  getWorkspaceModelExperiments,
  planModelExperiment,
  runModelExperiment,
  saveModelExperimentRating,
  updateWorkspaceModelSelection,
} from "../api/client";
import type {
  LocalAIActivationGuide,
  ModelExperimentPlan,
  ModelExperimentRating,
  ModelExperimentRun,
  ModelExperimentRunCandidate,
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
  hasScan: boolean;
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
  hasScan,
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
  const llmDiffersFromActive =
    Boolean(dashboard.selected_llm_provider && dashboard.selected_llm_model) &&
    !dashboard.selection_status.llm_status.matches_active_runtime;

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
            status={llmDiffersFromActive ? "per-request override" : dashboard.selection_status.llm_status.status}
            title={
              llmDiffersFromActive
                ? "This workspace preference differs from the backend default LLM. Ask can still request it per question when the model is supported by the provider."
                : undefined
            }
          />
          <RuntimeModel
            label="Active LLM"
            provider={usage.active_llm_provider}
            model={usage.active_llm_model}
            status={
              dashboard.selection_status.llm_status.matches_active_runtime
                ? "ready"
                : "default runtime"
            }
            title={
              llmDiffersFromActive
                ? "This is the backend default LLM. It is not automatically changed by saving a workspace LLM preference."
                : undefined
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
        {llmDiffersFromActive ? (
          <div className="llm-override-note">
            <StatusBadge label="informational" />
            <div>
              <strong>Selected LLM is a per-request preference.</strong>
              <p>
                The selected LLM differs from the backend default runtime. This
                does not require reindexing. Ask can still use the selected LLM
                per request when the model is available in the provider.
              </p>
            </div>
          </div>
        ) : null}
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
        hasScan={hasScan}
        onSelectionUpdated={onSelectionUpdated}
      />

      <ModelExperimentPlanner
        workspaceId={workspaceId}
        llmOptions={llmOptions}
        selectedLlmProvider={dashboard.selected_llm_provider}
        selectedLlmModel={dashboard.selected_llm_model}
        activeLlmProvider={usage.active_llm_provider}
        activeLlmModel={usage.active_llm_model}
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


function ModelExperimentPlanner({
  workspaceId,
  llmOptions,
  selectedLlmProvider,
  selectedLlmModel,
  activeLlmProvider,
  activeLlmModel,
  onSelectionUpdated,
}: {
  workspaceId: string;
  llmOptions: ModelOption[];
  selectedLlmProvider: string | null;
  selectedLlmModel: string | null;
  activeLlmProvider: string;
  activeLlmModel: string;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const defaultCandidateA =
    toOptionValue(selectedLlmProvider, selectedLlmModel) ??
    toOptionValue(activeLlmProvider, activeLlmModel) ??
    toOptionValue(llmOptions[0]?.provider, llmOptions[0]?.model) ??
    "";
  const defaultCandidateB =
    firstDifferentOptionValue(llmOptions, defaultCandidateA) ??
    toOptionValue(activeLlmProvider, activeLlmModel) ??
    defaultCandidateA;
  const [question, setQuestion] = useState(
    "How is Terraform backend configured?",
  );
  const [candidateA, setCandidateA] = useState(defaultCandidateA);
  const [candidateB, setCandidateB] = useState(defaultCandidateB);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [plan, setPlan] = useState<ModelExperimentPlan | null>(null);
  const [runResult, setRunResult] = useState<ModelExperimentRun | null>(null);
  const [experimentHistory, setExperimentHistory] = useState<ModelExperimentRun[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    setCandidateA(defaultCandidateA);
    setCandidateB(defaultCandidateB);
  }, [defaultCandidateA, defaultCandidateB]);

  useEffect(() => {
    void loadExperimentHistory();
  }, [workspaceId]);

  async function loadExperimentHistory() {
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const result = await getWorkspaceModelExperiments(workspaceId);
      setExperimentHistory(result);
    } catch (historyLoadError) {
      setHistoryError(errorMessage(historyLoadError));
    } finally {
      setIsLoadingHistory(false);
    }
  }

  async function generatePlan() {
    const parsedCandidates = [candidateA, candidateB]
      .map(parseOptionValue)
      .filter((candidate): candidate is { provider: string; model: string } =>
        Boolean(candidate),
      );
    const uniqueCandidates = dedupeCandidates(parsedCandidates);

    if (question.trim().length === 0) {
      setError("Enter a comparison question before generating a plan.");
      setPlan(null);
      return;
    }

    if (uniqueCandidates.length < 2) {
      setError("Choose at least two different LLM candidates.");
      setPlan(null);
      return;
    }

    setIsPlanning(true);
    setError(null);
    try {
      const result = await planModelExperiment({
        workspace_id: workspaceId,
        question: question.trim(),
        candidates: uniqueCandidates.map((candidate) => ({
          provider: candidate.provider,
          model: candidate.model,
          model_type: "llm",
        })),
      });
      setPlan(result);
      setRunResult(null);
      setRunError(null);
    } catch (planError) {
      setError(errorMessage(planError));
      setPlan(null);
    } finally {
      setIsPlanning(false);
    }
  }

  async function runComparisonExperiment() {
    const parsedCandidates = [candidateA, candidateB]
      .map(parseOptionValue)
      .filter((candidate): candidate is { provider: string; model: string } =>
        Boolean(candidate),
      );
    const uniqueCandidates = dedupeCandidates(parsedCandidates);

    if (question.trim().length === 0) {
      setRunError("Enter a comparison question before running an experiment.");
      setRunResult(null);
      return;
    }

    if (uniqueCandidates.length < 2) {
      setRunError("Choose at least two different LLM candidates.");
      setRunResult(null);
      return;
    }

    setIsRunning(true);
    setRunError(null);
    try {
      const result = await runModelExperiment({
        workspace_id: workspaceId,
        question: question.trim(),
        candidates: uniqueCandidates.map((candidate) => ({
          provider: candidate.provider,
          model: candidate.model,
          model_type: "llm",
        })),
      });
      setRunResult(result);
      setExperimentHistory((current) => upsertExperimentHistory(current, result));
    } catch (experimentError) {
      setRunError(errorMessage(experimentError));
      setRunResult(null);
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <section className="panel model-experiment-planner-panel">
      <PanelHeading
        eyebrow="Experiment planning"
        title="Compare LLM candidates"
        status="advisory"
      />
      <p className="panel-intro">
        Generate a safe comparison plan before running any model experiment. This
        does not call models, change selected models, restart the backend, or
        rebuild the index.
      </p>
      <div className="model-experiment-form">
        <label className="model-experiment-question">
          <span>Comparison question</span>
          <textarea
            value={question}
            rows={3}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <div className="model-experiment-candidates">
          <ModelCandidateSelect
            label="Candidate A"
            value={candidateA}
            options={llmOptions}
            onChange={setCandidateA}
          />
          <ModelCandidateSelect
            label="Candidate B"
            value={candidateB}
            options={llmOptions}
            onChange={setCandidateB}
          />
        </div>
        <button
          className="model-selection-save-button"
          type="button"
          disabled={isPlanning || llmOptions.length < 2}
          onClick={() => void generatePlan()}
        >
          {isPlanning ? "Generating plan…" : "Generate comparison plan"}
        </button>
      </div>
      <div className="model-selection-safety-note">
        <StatusBadge label="plan only" />
        <span>
          Planning is read/advisory. Use experiment run only after explicit
          confirmation in a separate flow.
        </span>
      </div>
      {error ? <p className="model-selection-error">{error}</p> : null}
      {plan ? <ModelExperimentPlanResult plan={plan} /> : null}
      {plan ? (
        <div className="model-experiment-run-panel">
          <div className="model-experiment-run-heading">
            <StatusBadge label="local llm calls" />
            <div>
              <strong>Run local comparison experiment</strong>
              <p>
                This calls the selected local LLM candidates through the backend.
                It may take time and can use CPU/RAM, but it does not execute
                shell commands, change selected models, restart the backend, or
                rebuild the index.
              </p>
            </div>
          </div>
          <button
            className="model-selection-save-button"
            type="button"
            disabled={isRunning}
            onClick={() => void runComparisonExperiment()}
          >
            {isRunning ? "Running experiment…" : "Run comparison experiment"}
          </button>
        </div>
      ) : null}
      {runError ? <p className="model-selection-error">{runError}</p> : null}
      {runResult ? (
        <ModelExperimentRunResult
          result={runResult}
          workspaceId={workspaceId}
          onSelectionUpdated={onSelectionUpdated}
        />
      ) : null}
      <ModelExperimentHistoryPanel
        experiments={experimentHistory}
        isLoading={isLoadingHistory}
        error={historyError}
        activeExperimentId={runResult?.id ?? null}
        onRefresh={() => void loadExperimentHistory()}
        onSelectExperiment={setRunResult}
      />
    </section>
  );
}

function ModelCandidateSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ModelOption[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <select
        value={value}
        disabled={options.length === 0}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.length === 0 ? (
          <option value="">No LLM options available</option>
        ) : (
          options.map((option) => (
            <option
              key={`${label}/${option.provider}/${option.model}`}
              value={`${option.provider}||${option.model}`}
            >
              {option.label}
            </option>
          ))
        )}
      </select>
    </label>
  );
}

function ModelExperimentPlanResult({ plan }: { plan: ModelExperimentPlan }) {
  return (
    <article className="model-experiment-plan-result">
      <div className="model-experiment-plan-summary">
        <StatusBadge
          label={plan.can_compare_without_reindex ? "No reindex" : "Reindex needed"}
        />
        <StatusBadge
          label={plan.requires_reindex ? "Requires reindex" : "Shared context"}
        />
        <strong>{formatLabel(plan.experiment_type)}</strong>
      </div>
      <p>{plan.shared_context_strategy}</p>
      <div className="model-experiment-candidate-list">
        {plan.candidates.map((candidate) => (
          <article
            className="model-experiment-candidate-card"
            key={`${candidate.provider}/${candidate.model}`}
          >
            <div>
              <strong>{candidate.display_name}</strong>
              <code>
                {candidate.provider}/{candidate.model}
              </code>
            </div>
            <div className="model-experiment-candidate-badges">
              <StatusBadge
                label={candidate.known_in_catalog ? "Catalog" : "Custom"}
              />
              <StatusBadge
                label={
                  candidate.requires_backend_restart
                    ? "Restart needed"
                    : "No restart"
                }
              />
              <StatusBadge
                label={candidate.requires_reindex ? "Reindex needed" : "No reindex"}
              />
            </div>
            {candidate.warnings.length > 0 ? (
              <ul>
                {candidate.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </div>
      <PlanList title="Recommended actions" items={plan.recommended_actions} />
      <PlanList title="Notes" items={plan.notes} />
    </article>
  );
}


function ModelExperimentRunResult({
  result,
  workspaceId,
  onSelectionUpdated,
}: {
  result: ModelExperimentRun;
  workspaceId: string;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  return (
    <article className="model-experiment-run-result">
      <div className="model-experiment-plan-summary">
        <StatusBadge label={result.status} />
        <StatusBadge label={`${result.shared_context_sources_count} shared sources`} />
        <strong>Experiment run</strong>
      </div>
      <div className="model-experiment-run-meta">
        <span>
          Experiment ID <code>{result.id}</code>
        </span>
        <span>Created {formatDateTime(result.created_at)}</span>
        {result.completed_at ? <span>Completed {formatDateTime(result.completed_at)}</span> : null}
      </div>
      <div className="model-experiment-candidate-list">
        {result.candidates.map((candidate) => (
          <article
            className="model-experiment-candidate-card model-experiment-run-card"
            key={`${candidate.provider}/${candidate.model}`}
          >
            <div>
              <strong>
                {candidate.provider}/{candidate.model}
              </strong>
              <code>{candidate.status}</code>
            </div>
            <div className="model-experiment-candidate-badges">
              <StatusBadge label={candidate.status} />
              <StatusBadge label={`${candidate.latency_ms ?? 0} ms`} />
              <StatusBadge label={`${candidate.sources_count} sources`} />
              <StatusBadge label={`${candidate.quality_warnings_count} warnings`} />
            </div>
            {candidate.error ? (
              <p className="model-selection-error">{candidate.error}</p>
            ) : (
              <p className="model-experiment-answer-preview">
                {candidate.answer ? truncateText(candidate.answer, 560) : "No answer returned."}
              </p>
            )}
          </article>
        ))}
      </div>
      <ExperimentRunHeuristics result={result} />
      <ExperimentRatingPanel
        result={result}
        workspaceId={workspaceId}
        onSelectionUpdated={onSelectionUpdated}
      />
      <PlanList title="Run notes" items={result.notes} />
    </article>
  );
}

function ExperimentRunHeuristics({ result }: { result: ModelExperimentRun }) {
  const completed = result.candidates.filter(
    (candidate) => candidate.status === "completed" && !candidate.error,
  );
  if (completed.length === 0) {
    return null;
  }

  const fastest = [...completed].sort(
    (left, right) => (left.latency_ms ?? Number.MAX_SAFE_INTEGER) - (right.latency_ms ?? Number.MAX_SAFE_INTEGER),
  )[0];
  const fewestWarnings = [...completed].sort(
    (left, right) => left.quality_warnings_count - right.quality_warnings_count,
  )[0];
  const mostSources = [...completed].sort(
    (left, right) => right.sources_count - left.sources_count,
  )[0];

  return (
    <div className="model-experiment-heuristics">
      <strong>Quick comparison hints</strong>
      <ul>
        <li>
          Fastest: {fastest.provider}/{fastest.model} ({fastest.latency_ms ?? "unknown"} ms)
        </li>
        <li>
          Fewest warnings: {fewestWarnings.provider}/{fewestWarnings.model} ({fewestWarnings.quality_warnings_count})
        </li>
        <li>
          Most sources used: {mostSources.provider}/{mostSources.model} ({mostSources.sources_count})
        </li>
      </ul>
      <small>
        These are simple hints, not an automatic winner. Review answer quality and source grounding manually before changing the selected LLM.
      </small>
    </div>
  );
}



function ModelExperimentHistoryPanel({
  experiments,
  isLoading,
  error,
  activeExperimentId,
  onRefresh,
  onSelectExperiment,
}: {
  experiments: ModelExperimentRun[];
  isLoading: boolean;
  error: string | null;
  activeExperimentId: string | null;
  onRefresh: () => void;
  onSelectExperiment: (experiment: ModelExperimentRun) => void;
}) {
  return (
    <div className="model-experiment-history-panel">
      <div className="model-experiment-history-heading">
        <div>
          <StatusBadge label="history" />
          <strong>Experiment history</strong>
          <p>
            Review previous local model comparisons for this workspace. Selecting
            a run only opens its saved details and ratings UI.
          </p>
        </div>
        <button type="button" className="secondary-button" onClick={onRefresh}>
          {isLoading ? "Refreshing…" : "Refresh history"}
        </button>
      </div>
      {error ? <p className="model-selection-error">{error}</p> : null}
      {isLoading && experiments.length === 0 ? (
        <p className="model-experiment-rating-muted">Loading experiment history…</p>
      ) : null}
      {!isLoading && experiments.length === 0 ? (
        <EmptyState
          title="No model experiments yet"
          message="Generate a plan and run a local comparison experiment to build workspace history."
          compact
        />
      ) : null}
      {experiments.length > 0 ? (
        <div className="model-experiment-history-list">
          {experiments.slice(0, 6).map((experiment) => (
            <button
              key={experiment.id}
              type="button"
              className={
                activeExperimentId === experiment.id
                  ? "model-experiment-history-item selected"
                  : "model-experiment-history-item"
              }
              onClick={() => onSelectExperiment(experiment)}
            >
              <div>
                <strong>{truncateText(experiment.question, 96)}</strong>
                <span>{formatDateTime(experiment.created_at)}</span>
              </div>
              <div className="model-experiment-history-meta">
                <StatusBadge label={experiment.status} />
                <StatusBadge label={`${experiment.shared_context_sources_count} sources`} />
                <StatusBadge label={`${experiment.candidates.length} candidates`} />
              </div>
              <div className="model-experiment-history-candidates">
                {experiment.candidates.slice(0, 3).map((candidate) => (
                  <span key={`${experiment.id}/${candidate.provider}/${candidate.model}`}>
                    {candidate.provider}/{candidate.model} · {candidate.latency_ms ?? "?"} ms · {candidate.quality_warnings_count} warnings
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ExperimentRatingPanel({
  result,
  workspaceId,
  onSelectionUpdated,
}: {
  result: ModelExperimentRun;
  workspaceId: string;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const completedCandidates = result.candidates.filter(
    (candidate) => candidate.status === "completed" && !candidate.error,
  );
  const defaultCandidate = completedCandidates[0];
  const [selectedCandidate, setSelectedCandidate] = useState(
    defaultCandidate ? toOptionValue(defaultCandidate.provider, defaultCandidate.model) ?? "" : "",
  );
  const [rating, setRating] = useState(5);
  const [isPreferred, setIsPreferred] = useState(true);
  const [selectedTags, setSelectedTags] = useState<string[]>([
    "better_source_grounding",
  ]);
  const [comment, setComment] = useState("");
  const [ratings, setRatings] = useState<ModelExperimentRating[]>([]);
  const [isLoadingRatings, setIsLoadingRatings] = useState(false);
  const [isSavingRating, setIsSavingRating] = useState(false);
  const [ratingError, setRatingError] = useState<string | null>(null);
  const [ratingMessage, setRatingMessage] = useState<string | null>(null);
  const [applyCandidate, setApplyCandidate] = useState<ModelExperimentRating | null>(null);
  const [isApplyingSelection, setIsApplyingSelection] = useState(false);

  useEffect(() => {
    setSelectedCandidate(
      defaultCandidate ? toOptionValue(defaultCandidate.provider, defaultCandidate.model) ?? "" : "",
    );
  }, [defaultCandidate?.provider, defaultCandidate?.model, result.id]);

  useEffect(() => {
    let cancelled = false;
    async function loadRatings() {
      setIsLoadingRatings(true);
      setRatingError(null);
      try {
        const existingRatings = await getModelExperimentRatings(result.id);
        if (!cancelled) {
          setRatings(existingRatings);
        }
      } catch (loadError) {
        if (!cancelled) {
          setRatingError(errorMessage(loadError));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingRatings(false);
        }
      }
    }

    void loadRatings();
    return () => {
      cancelled = true;
    };
  }, [result.id]);

  if (completedCandidates.length === 0) {
    return null;
  }

  async function saveRating() {
    const parsed = parseOptionValue(selectedCandidate);
    if (!parsed) {
      setRatingError("Choose a completed candidate before saving a rating.");
      return;
    }

    setIsSavingRating(true);
    setRatingError(null);
    setRatingMessage(null);
    try {
      const savedRating = await saveModelExperimentRating(result.id, {
        provider: parsed.provider,
        model: parsed.model,
        rating,
        is_preferred: isPreferred,
        tags: selectedTags,
        comment: comment.trim().length > 0 ? comment.trim() : undefined,
      });
      setRatings((current) => [savedRating, ...current]);
      setRatingMessage("Experiment rating saved. Selected model was not changed.");
    } catch (saveError) {
      setRatingError(errorMessage(saveError));
    } finally {
      setIsSavingRating(false);
    }
  }

  async function applyPreferredRating(ratingToApply: ModelExperimentRating) {
    setIsApplyingSelection(true);
    setRatingError(null);
    setRatingMessage(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: ratingToApply.provider,
        model: ratingToApply.model,
        model_type: "llm",
        selected_reason: `Selected from experiment ${result.id} after manual preferred rating.`,
      });
      setRatingMessage(
        `Selected LLM updated to ${ratingToApply.provider}/${ratingToApply.model}. Runtime settings, indexing, and experiment results were not changed.`,
      );
      setApplyCandidate(null);
      await onSelectionUpdated();
    } catch (applyError) {
      setRatingError(errorMessage(applyError));
    } finally {
      setIsApplyingSelection(false);
    }
  }

  return (
    <div className="experiment-rating-panel">
      <div className="experiment-rating-heading">
        <StatusBadge label="manual rating" />
        <div>
          <strong>Rate this experiment</strong>
          <p>
            Save human feedback for model performance tracking. This does not
            change the selected LLM or rerun the experiment.
          </p>
        </div>
      </div>
      <div className="experiment-rating-form">
        <label>
          <span>Candidate</span>
          <select
            value={selectedCandidate}
            onChange={(event) => setSelectedCandidate(event.target.value)}
          >
            {completedCandidates.map((candidate) => (
              <option
                key={`${candidate.provider}/${candidate.model}`}
                value={`${candidate.provider}||${candidate.model}`}
              >
                {candidate.provider}/{candidate.model}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Rating</span>
          <select
            value={rating}
            onChange={(event) => setRating(Number(event.target.value))}
          >
            {[5, 4, 3, 2, 1].map((value) => (
              <option key={value} value={value}>
                {value} / 5
              </option>
            ))}
          </select>
        </label>
        <label className="experiment-rating-checkbox">
          <input
            type="checkbox"
            checked={isPreferred}
            onChange={(event) => setIsPreferred(event.target.checked)}
          />
          <span>Mark as preferred candidate</span>
        </label>
      </div>
      <TagChecklist selectedTags={selectedTags} onChange={setSelectedTags} />
      <label className="experiment-rating-comment">
        <span>Comment</span>
        <textarea
          value={comment}
          rows={3}
          placeholder="Why did this model perform better or worse?"
          onChange={(event) => setComment(event.target.value)}
        />
      </label>
      <button
        className="model-selection-save-button"
        type="button"
        disabled={isSavingRating}
        onClick={() => void saveRating()}
      >
        {isSavingRating ? "Saving rating…" : "Save rating"}
      </button>
      {ratingMessage ? <p className="model-selection-message">{ratingMessage}</p> : null}
      {ratingError ? <p className="model-selection-error">{ratingError}</p> : null}
      <SavedRatingsList
        ratings={ratings}
        isLoading={isLoadingRatings}
        applyCandidate={applyCandidate}
        isApplyingSelection={isApplyingSelection}
        onRequestApply={setApplyCandidate}
        onCancelApply={() => setApplyCandidate(null)}
        onConfirmApply={(ratingToApply) => void applyPreferredRating(ratingToApply)}
      />
    </div>
  );
}

function TagChecklist({
  selectedTags,
  onChange,
}: {
  selectedTags: string[];
  onChange: (tags: string[]) => void;
}) {
  const tags = [
    "better_source_grounding",
    "more_complete_answer",
    "faster",
    "less_hallucination",
    "clearer_explanation",
  ];

  function toggleTag(tag: string) {
    onChange(
      selectedTags.includes(tag)
        ? selectedTags.filter((selected) => selected !== tag)
        : [...selectedTags, tag],
    );
  }

  return (
    <fieldset className="experiment-rating-tags">
      <legend>Tags</legend>
      {tags.map((tag) => (
        <label key={tag}>
          <input
            type="checkbox"
            checked={selectedTags.includes(tag)}
            onChange={() => toggleTag(tag)}
          />
          <span>{formatLabel(tag)}</span>
        </label>
      ))}
    </fieldset>
  );
}

function SavedRatingsList({
  ratings,
  isLoading,
  applyCandidate,
  isApplyingSelection,
  onRequestApply,
  onCancelApply,
  onConfirmApply,
}: {
  ratings: ModelExperimentRating[];
  isLoading: boolean;
  applyCandidate: ModelExperimentRating | null;
  isApplyingSelection: boolean;
  onRequestApply: (rating: ModelExperimentRating) => void;
  onCancelApply: () => void;
  onConfirmApply: (rating: ModelExperimentRating) => void;
}) {
  if (isLoading) {
    return <p className="model-experiment-rating-muted">Loading saved ratings…</p>;
  }

  if (ratings.length === 0) {
    return (
      <p className="model-experiment-rating-muted">
        No ratings saved for this experiment yet.
      </p>
    );
  }

  return (
    <div className="saved-experiment-ratings">
      <strong>Saved ratings</strong>
      {ratings.slice(0, 5).map((rating) => (
        <article key={rating.id}>
          <div>
            <strong>
              {rating.provider}/{rating.model}
            </strong>
            <span>{formatDateTime(rating.created_at)}</span>
          </div>
          <div className="model-experiment-candidate-badges">
            <StatusBadge label={`${rating.rating}/5`} />
            {rating.is_preferred ? <StatusBadge label="preferred" /> : null}
            {rating.tags.slice(0, 3).map((tag) => (
              <StatusBadge key={tag} label={formatLabel(tag)} />
            ))}
          </div>
          {rating.comment ? <p>{rating.comment}</p> : null}
          {rating.is_preferred ? (
            <PreferredModelApplyControl
              rating={rating}
              applyCandidate={applyCandidate}
              isApplyingSelection={isApplyingSelection}
              onRequestApply={onRequestApply}
              onCancelApply={onCancelApply}
              onConfirmApply={onConfirmApply}
            />
          ) : null}
        </article>
      ))}
    </div>
  );
}

function PreferredModelApplyControl({
  rating,
  applyCandidate,
  isApplyingSelection,
  onRequestApply,
  onCancelApply,
  onConfirmApply,
}: {
  rating: ModelExperimentRating;
  applyCandidate: ModelExperimentRating | null;
  isApplyingSelection: boolean;
  onRequestApply: (rating: ModelExperimentRating) => void;
  onCancelApply: () => void;
  onConfirmApply: (rating: ModelExperimentRating) => void;
}) {
  const isConfirming = applyCandidate?.id === rating.id;
  const label = `${rating.provider}/${rating.model}`;

  if (!isConfirming) {
    return (
      <div className="preferred-apply-control">
        <button
          type="button"
          className="secondary-button"
          onClick={() => onRequestApply(rating)}
        >
          Use this model as selected LLM
        </button>
        <small>
          This only updates workspace LLM preference. It does not restart the
          backend, reindex, rerun experiments, or change embedding settings.
        </small>
      </div>
    );
  }

  return (
    <div className="preferred-apply-confirmation">
      <StatusBadge label="confirmation required" />
      <div>
        <strong>Use {label} as selected LLM?</strong>
        <p>
          This saves the preferred rated model as the workspace selected LLM.
          Runtime settings stay unchanged, and Ask will use it per request when
          supported by the provider.
        </p>
      </div>
      <div className="preferred-apply-actions">
        <button
          type="button"
          className="model-selection-save-button"
          disabled={isApplyingSelection}
          onClick={() => onConfirmApply(rating)}
        >
          {isApplyingSelection ? "Applying…" : "Confirm selection"}
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={isApplyingSelection}
          onClick={onCancelApply}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function PlanList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="model-experiment-plan-list">
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function firstDifferentOptionValue(
  options: ModelOption[],
  currentValue: string,
): string | null {
  const option = options.find(
    (candidate) =>
      toOptionValue(candidate.provider, candidate.model) !== currentValue,
  );
  return option ? toOptionValue(option.provider, option.model) : null;
}

function dedupeCandidates(
  candidates: { provider: string; model: string }[],
): { provider: string; model: string }[] {
  const seen = new Set<string>();
  return candidates.filter((candidate) => {
    const key = `${candidate.provider}/${candidate.model}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function upsertExperimentHistory(
  history: ModelExperimentRun[],
  experiment: ModelExperimentRun,
): ModelExperimentRun[] {
  return [experiment, ...history.filter((item) => item.id !== experiment.id)];
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
  hasScan,
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
  hasScan: boolean;
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
          description="Used by Ask as a per-request preference when the selected provider/model is supported. No reindex is required for LLM changes."
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
          Backend restart and reindex steps are still manual. Changing an LLM
          preference does not require reindexing; changing embedding/runtime
          sensitive selections may require the guidance below.
        </span>
      </div>

      {reindexReason ? (
        <ModelReindexGuidance
          workspaceId={workspaceId}
          reason={reindexReason}
          hasScan={hasScan}
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
  hasScan,
}: {
  workspaceId: string;
  reason: string;
  hasScan: boolean;
}) {
  const scanCommand = `curl -X POST http://127.0.0.1:8000/workspaces/${workspaceId}/scan`;
  const indexCommand = `curl -X POST http://127.0.0.1:8000/workspaces/${workspaceId}/index`;

  return (
    <article className="reindex-guidance model-reindex-guidance">
      <div>
        <StatusBadge label="copy only" />
        <strong>{hasScan ? "Reindex guidance" : "Scan and index guidance"}</strong>
      </div>
      <p>{reason}</p>
      {!hasScan ? (
        <CommandGuidanceRow
          label="Step 1 · scan project"
          command={scanCommand}
        />
      ) : null}
      <CommandGuidanceRow
        label={hasScan ? "Rebuild workspace index" : "Step 2 · build index"}
        command={indexCommand}
      />
      <small>
        The frontend does not run scan or indexing automatically. Copy and run
        these commands only when you intentionally want to rebuild workspace
        context. Changing an LLM does not require reindexing.
      </small>
    </article>
  );
}

function CommandGuidanceRow({
  label,
  command,
}: {
  label: string;
  command: string;
}) {
  return (
    <div className="reindex-command-step">
      <span>{label}</span>
      <div className="reindex-command-row">
        <code title={command}>{command}</code>
        <CopyButton text={command} />
      </div>
    </div>
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
  title,
}: {
  label: string;
  provider: string | null;
  model: string | null;
  status: string;
  title?: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>
        {provider && model ? `${provider}/${model}` : "Not selected"}
      </strong>
      <StatusBadge label={status} title={title} />
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

function truncateText(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength).trimEnd()}…` : value;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unexpected request error";
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
