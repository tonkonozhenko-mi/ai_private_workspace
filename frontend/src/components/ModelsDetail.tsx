import { useEffect, useMemo, useState } from "react";

import { formatModelLabel } from "../lib/modelLabel";
import { recheckEngineLabel } from "../lib/rescanLabels";

import {
  createLocalModelInstallDraft,
  getGgufCatalog,
  getLlamaRuntimeStatus,
  getGuidedModelSetup,
  getLocalModelInstallGuide,
  getLocalModelInstallStatus,
  getOllamaPull,
  startOllamaPull,
  deleteInstalledModel,
  getLocalModelDownloadWorkerPlan,
  getLocalModelDownloadExecutionCapability,
  startLocalModelDownloadJob,
  getLocalModelDownloadJob,
  listLocalModelDownloadJobs,
  cancelLocalModelDownloadJob,
  getModelExperimentRatings,
  getWorkspaceModelExperiments,
  planModelExperiment,
  runModelExperiment,
  saveModelExperimentRating,
  updateWorkspaceModelSelection,
} from "../api/client";
import type {
  GuidedModelSetupGuide,
  GuidedModelSetupSection,
  LocalAIActivationGuide,
  LocalModelInstallDraft,
  LlamaRuntimeStatus,
  LocalModelInstallGuide,
  LocalModelInstallStatus,
  LocalModelDownloadWorkerPlan,
  LocalModelDownloadExecutionCapability,
  LocalModelDownloadJob,
  LocalModelDownloadJobList,
  LocalModelInstallOption,
  ModelExperimentPlan,
  ModelExperimentRating,
  ModelExperimentRun,
  ModelExperimentRunCandidate,
  WorkspaceModelRecommendation,
  WorkspaceModelsDashboard,
  WorkspaceJob,
} from "../api/types";
import { CopyButton } from "./CopyButton";
import { EmptyState } from "./EmptyState";
import { LlamaCppModelsPanel } from "./LlamaCppModelsPanel";
import { RerankerSetting } from "./RerankerSetting";
import { StatusBadge } from "./StatusBadge";


type AnswerCreativity = "precise" | "balanced" | "creative";

interface ModelsDetailProps {
  workspaceId: string;
  hasScan: boolean;
  developerMode?: boolean;
  answerCreativity?: AnswerCreativity;
  onAnswerCreativityChange?: (value: AnswerCreativity) => void;
  dashboard: WorkspaceModelsDashboard;
  activationGuide: LocalAIActivationGuide;
  onSelectionUpdated: () => Promise<void> | void;
  onStartIndexJob: () => Promise<WorkspaceJob>;
  onGetWorkspaceJob: (jobId: string) => Promise<WorkspaceJob>;
}

interface ModelOption {
  provider: string;
  model: string;
  label: string;
  source: string;
}

// The three sections the nav actually offers. It listed three more, and the
// initial state was one of them — so opening Models showed the header, the
// nav, and then nothing, until you clicked. "catalog" is the one screen the
// nav shows outside developer mode, so it is where this opens.
type ModelsSection = "catalog" | "skills" | "compare";

export function ModelsDetail({
  workspaceId,
  hasScan,
  developerMode = false,
  answerCreativity = "precise",
  onAnswerCreativityChange,
  dashboard,
  activationGuide,
  onSelectionUpdated,
  onStartIndexJob,
  onGetWorkspaceJob,
}: ModelsDetailProps) {
  const usage = dashboard.usage_plan;
  // The dashboard's "active" model is a configuration string; the only truth
  // about which answer/search model the built-in engine is actually holding is
  // the live runtime status. Read it so CURRENT SETUP reports what is really
  // running, not what the config believes — the two can disagree while a switch
  // is settling, and the card must not claim a model the engine isn't serving.
  const [llamaRuntime, setLlamaRuntime] = useState<LlamaRuntimeStatus | null>(null);
  useEffect(() => {
    let cancelled = false;
    void getLlamaRuntimeStatus()
      .then((status) => {
        if (!cancelled) setLlamaRuntime(status);
      })
      .catch(() => {
        if (!cancelled) setLlamaRuntime(null);
      });
    return () => {
      cancelled = true;
    };
    // Re-read whenever the dashboard is refreshed (e.g. after a model switch).
  }, [dashboard]);
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
  // Compare/face-off must only offer models that are actually downloaded and
  // runnable (not recommendations or fake), never the embedding model, and ONLY
  // from this project's backend — you can't face-off an Ollama model against a
  // llama.cpp model (different engines).
  const comparisonBackend: "ollama" | "llamacpp" =
    dashboard.selected_llm_provider === "llamacpp" ||
    dashboard.selected_embedding_provider === "llamacpp"
      ? "llamacpp"
      : "ollama";
  const [compareInstallStatus, setCompareInstallStatus] =
    useState<LocalModelInstallStatus | null>(null);
  const [compareGgufModels, setCompareGgufModels] = useState<
    Array<{ id: string; installed: boolean; active: boolean }>
  >([]);
  useEffect(() => {
    let cancelled = false;
    if (comparisonBackend === "llamacpp") {
      getGgufCatalog("llm")
        .then((models) => {
          if (!cancelled) {
            setCompareGgufModels(
              models.map((m) => ({ id: m.id, installed: m.installed, active: m.active })),
            );
          }
        })
        .catch(() => {});
    } else {
      getLocalModelInstallStatus()
        .then((status) => {
          if (!cancelled) setCompareInstallStatus(status);
        })
        .catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [comparisonBackend]);
  const comparisonLlmOptions = useMemo(() => {
    const options = new Map<string, ModelOption>();
    if (comparisonBackend === "llamacpp") {
      for (const m of compareGgufModels) {
        if (m.installed) {
          addOption(options, "llamacpp", m.id, m.active ? "In use" : "Downloaded");
        }
      }
      return Array.from(options.values());
    }
    if (dashboard.selected_llm_provider === "ollama") {
      addOption(
        options,
        dashboard.selected_llm_provider,
        dashboard.selected_llm_model,
        "Current selection",
      );
    }
    for (const item of asArray(compareInstallStatus?.items)) {
      if (
        item.model_type === "llm" &&
        item.status === "installed" &&
        item.provider === "ollama"
      ) {
        addOption(options, item.provider, item.model, "Installed");
      }
    }
    return Array.from(options.values());
  }, [
    comparisonBackend,
    compareGgufModels,
    compareInstallStatus,
    dashboard.selected_llm_provider,
    dashboard.selected_llm_model,
  ]);

  const reindexReason = getModelReindexReason(dashboard);
  const llmDiffersFromBackendDefault =
    Boolean(dashboard.selected_llm_provider && dashboard.selected_llm_model) &&
    !dashboard.selection_status.llm_status.matches_active_runtime;
  const needsContextBuild = dashboard.overall_status === "needs_context_index";
  const [contextBuildJob, setContextBuildJob] = useState<WorkspaceJob | null>(null);
  const [contextBuildError, setContextBuildError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<ModelsSection>("catalog");

  useEffect(() => {
    if (!contextBuildJob || !["queued", "running"].includes(contextBuildJob.status)) {
      return;
    }

    const timeout = window.setTimeout(async () => {
      try {
        const refreshedJob = await onGetWorkspaceJob(contextBuildJob.job_id);
        setContextBuildJob(refreshedJob);
        if (["completed", "failed", "cancelled"].includes(refreshedJob.status)) {
          await onSelectionUpdated();
        }
      } catch (error) {
        setContextBuildError(errorMessage(error));
      }
    }, 1800);

    return () => window.clearTimeout(timeout);
  }, [contextBuildJob, onGetWorkspaceJob, onSelectionUpdated]);

  async function handleBuildContext() {
    setContextBuildError(null);
    try {
      const job = await onStartIndexJob();
      setContextBuildJob(job);
    } catch (error) {
      setContextBuildError(errorMessage(error));
    }
  }

  async function applyGuidedSelection(
    modelType: "llm" | "embedding",
    provider: string,
    model: string,
  ) {
    await updateWorkspaceModelSelection(workspaceId, {
      provider,
      model,
      model_type: modelType,
      selected_reason:
        modelType === "llm"
          ? "Chosen from guided local model setup."
          : "Chosen from guided local search model setup.",
    });
    if (
      modelType === "llm" &&
      provider === "ollama" &&
      (
        dashboard.selected_embedding_model === null ||
        dashboard.selected_embedding_provider !== "ollama"
      )
    ) {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: "ollama",
        model: "nomic-embed-text",
        model_type: "embedding",
        selected_reason:
          "Automatically paired with the guided local AI answer model.",
      });
    }
    await onSelectionUpdated();
  }

  // What CURRENT SETUP shows: the live engine's model when the built-in engine
  // is actually running and this workspace uses it — that is the model really
  // answering — otherwise the saved selection (or the config's active model).
  // This keeps the card from claiming a model the engine has not switched to.
  const engineIsLive = Boolean(llamaRuntime?.running);
  const workspaceUsesLlamaLlm =
    dashboard.selected_llm_provider === "llamacpp" ||
    (!dashboard.selected_llm_provider && usage.active_llm_provider === "llamacpp");
  const workspaceUsesLlamaEmbed =
    dashboard.selected_embedding_provider === "llamacpp" ||
    (!dashboard.selected_embedding_provider && usage.active_embedding_provider === "llamacpp");
  const liveAnswerModel =
    engineIsLive && workspaceUsesLlamaLlm && llamaRuntime?.active_llm_model
      ? { provider: "llamacpp", model: llamaRuntime.active_llm_model }
      : {
          provider: dashboard.selected_llm_provider ?? usage.active_llm_provider,
          model: dashboard.selected_llm_model ?? usage.active_llm_model,
        };
  const liveSearchModel =
    engineIsLive && workspaceUsesLlamaEmbed && llamaRuntime?.active_embedding_model
      ? { provider: "llamacpp", model: llamaRuntime.active_embedding_model }
      : {
          provider: dashboard.selected_embedding_provider ?? usage.active_embedding_provider,
          model: dashboard.selected_embedding_model ?? usage.active_embedding_model,
        };

  return (
    <div className="models-detail models-detail-simple">
      <div className="models-overview-top">
      <section className="panel models-simple-panel models-simple-panel-clean">
        <PanelHeading
          eyebrow="Current setup"
          title="Models used by this workspace"
          status={dashboard.overall_status}
        />
        <div className="models-simple-grid">
          <SimpleModelCard
            label="AI answer model"
            provider={liveAnswerModel.provider}
            model={liveAnswerModel.model}
            description="Used when you ask questions."
            status={usage.can_ask_with_selected_llm ? "Ready" : "Needs setup"}
          />
          <SimpleModelCard
            label="Search context model"
            provider={liveSearchModel.provider}
            model={liveSearchModel.model}
            description="Used to build and search local project context."
            status={getSearchContextStatusLabel(dashboard)}
          />
        </div>
        <RuntimeNextActionPanel
          dashboard={dashboard}
          workspaceId={workspaceId}
          contextBuildJob={contextBuildJob}
          contextBuildError={contextBuildError}
          onBuildContext={handleBuildContext}
          onSelectionUpdated={onSelectionUpdated}
        />
      </section>
      </div>

      <nav className="models-section-nav" aria-label="Model settings sections">
        {(([
          ["catalog", "Choose & install"],
          ["skills", "Tuning"],
          ["compare", "Compare"],
        ] as Array<[ModelsSection, string]>).filter(
          ([id]) => developerMode || id === "catalog",
        )).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={activeSection === id ? "is-selected" : ""}
            aria-pressed={activeSection === id}
            onClick={() => setActiveSection(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {activeSection === "catalog" ? (
        <>
          <GuidedModelSetupPanel
            workspaceId={workspaceId}
            developerMode={developerMode}
            backend={
              // Prefer the engine that's actually live: if the workspace is
              // running on llama.cpp, show its GGUF manager even when a stale
              // Ollama selection lingers — otherwise the Ollama guided flow would
              // offer (and persist) models for an engine that isn't installed.
              dashboard.selected_llm_provider === "llamacpp" ||
              dashboard.selected_embedding_provider === "llamacpp" ||
              usage.active_llm_provider === "llamacpp" ||
              usage.active_embedding_provider === "llamacpp"
                ? "llamacpp"
                : "ollama"
            }
            onApplySelection={applyGuidedSelection}
            onSelectionUpdated={onSelectionUpdated}
          />
          {/* Reranker ("sharper search") is a llama.cpp-only precision pass —
              only offer it when this project runs on the built-in engine. */}
          {comparisonBackend === "llamacpp" ? <RerankerSetting /> : null}
          {/* The detailed Ollama model manager is meaningless in llama.cpp mode
              (it pulls Ollama models) — the llama.cpp panel above manages GGUF
              models instead. Only show it for the Ollama backend. */}
          {developerMode &&
          dashboard.selected_llm_provider !== "llamacpp" &&
          dashboard.selected_embedding_provider !== "llamacpp" ? (
            <LocalModelInstallPanel
              key={[
                workspaceId,
                dashboard.selected_llm_provider,
                dashboard.selected_llm_model,
                dashboard.selected_embedding_provider,
                dashboard.selected_embedding_model,
              ].join("-")}
              workspaceId={workspaceId}
              onSelectionUpdated={onSelectionUpdated}
            />
          ) : null}
        </>
      ) : null}

      {activeSection === "skills" ? (
        <>
          <section className="panel models-simple-panel">
            <PanelHeading
              eyebrow="Answer tuning"
              title="Answer creativity"
            />
            <p className="panel-helper">
              How freely the AI words its answers. <strong>Precise</strong> sticks closely to
              your project (best for code and facts, and the most repeatable — the same
              question gives the same answer); <strong>Creative</strong> allows more varied
              phrasing. Applies to new questions in Ask.
            </p>
            <div className="segmented-control" aria-label="Answer creativity">
              {(["precise", "balanced", "creative"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={answerCreativity === value ? "is-selected" : ""}
                  onClick={() => onAnswerCreativityChange?.(value)}
                >
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </button>
              ))}
            </div>
          </section>
        </>
      ) : null}

      {activeSection === "compare" ? (
        <ModelExperimentPlanner
          workspaceId={workspaceId}
          llmOptions={comparisonLlmOptions}
          selectedLlmProvider={dashboard.selected_llm_provider}
          selectedLlmModel={dashboard.selected_llm_model}
          activeLlmProvider={usage.active_llm_provider}
          activeLlmModel={usage.active_llm_model}
          onSelectionUpdated={onSelectionUpdated}
        />
      ) : null}

    </div>
  );
}



function RuntimeNextActionPanel({
  dashboard,
  workspaceId,
  contextBuildJob,
  contextBuildError,
  onBuildContext,
  onSelectionUpdated,
}: {
  dashboard: WorkspaceModelsDashboard;
  workspaceId: string;
  contextBuildJob: WorkspaceJob | null;
  contextBuildError: string | null;
  onBuildContext: () => Promise<void> | void;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const usage = dashboard.usage_plan;
  const embeddingPlan = dashboard.embedding_indexing_plan;
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const selectedEmbedding = formatProviderModel(
    dashboard.selected_embedding_provider,
    dashboard.selected_embedding_model,
  );
  const activeEmbedding = formatProviderModel(
    usage.active_embedding_provider,
    usage.active_embedding_model,
  );
  const selectedLlm = formatProviderModel(
    dashboard.selected_llm_provider,
    dashboard.selected_llm_model,
  );
  const activeLlm = formatProviderModel(
    usage.active_llm_provider,
    usage.active_llm_model,
  );

  const needsEmbeddingRuntime =
    dashboard.overall_status === "needs_embedding_runtime" ||
    embeddingPlan.plan_status === "runtime_mismatch" ||
    embeddingPlan.requires_backend_restart;
  const needsContextBuild = dashboard.overall_status === "needs_context_index";
  const isReady = dashboard.usage_plan.can_use_selected_models_fully;

  async function recheckRuntime() {
    setActionBusy("recheck");
    setActionError(null);
    setActionMessage(null);
    try {
      await onSelectionUpdated();
      setActionMessage("Runtime status refreshed.");
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setActionBusy(null);
    }
  }

  async function useActiveEmbeddingRuntime() {
    if (!usage.active_embedding_provider || !usage.active_embedding_model) {
      setActionError("Active backend search model is not available.");
      return;
    }

    setActionBusy("use-active-embedding");
    setActionError(null);
    setActionMessage(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: usage.active_embedding_provider,
        model: usage.active_embedding_model,
        model_type: "embedding",
        selected_reason:
          "Switched from the runtime readiness panel to the active backend search model.",
      });
      setActionMessage(
        `Search context model changed to active runtime: ${activeEmbedding}. Rebuild context once before Ask uses local sources.`,
      );
      await onSelectionUpdated();
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setActionBusy(null);
    }
  }

  async function useActiveLlmRuntime() {
    if (!usage.active_llm_provider || !usage.active_llm_model) {
      setActionError("Active backend answer model is not available.");
      return;
    }
    setActionBusy("use-active-llm");
    setActionError(null);
    setActionMessage(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: usage.active_llm_provider,
        model: usage.active_llm_model,
        model_type: "llm",
        selected_reason: "Switched to the running backend answer model.",
      });
      setActionMessage(`AI answer model changed to the active runtime: ${activeLlm}.`);
      await onSelectionUpdated();
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setActionBusy(null);
    }
  }

  // The selected answer model can't run (e.g. an Ollama pick that never installed)
  // while the live engine is happily running a different model. Offer a one-click
  // heal onto the active model instead of leaving the workspace stuck on "needs
  // setup".
  const answerModelMismatch =
    !usage.can_ask_with_selected_llm &&
    Boolean(usage.active_llm_provider && usage.active_llm_model) &&
    activeLlm !== selectedLlm;

  if (needsEmbeddingRuntime) {
    return (
      <div className="runtime-next-action-panel runtime-next-action-panel-warning">
        <div className="runtime-next-action-copy">
          <StatusBadge label="Action needed" />
          <div>
            <strong>Search context runtime does not match this workspace.</strong>
            <p>
              Selected search model: <code>{selectedEmbedding}</code>. Active backend search model: <code>{activeEmbedding}</code>.
              Ask can use the AI answer model, but local source search needs the search model to match the active backend runtime.
            </p>
            <p className="runtime-next-action-hint">
              Fastest way to continue now: use the active backend search model, then rebuild context.
              To use the selected model instead, quit and reopen the app after starting the backend with that model.
            </p>
          </div>
        </div>
        <div className="runtime-next-action-buttons">
          <button
            className="primary-button"
            type="button"
            disabled={actionBusy !== null}
            onClick={() => void useActiveEmbeddingRuntime()}
          >
            {actionBusy === "use-active-embedding"
              ? "Applying…"
              : `Use active search model (${activeEmbedding})`}
          </button>
          <button
            className="secondary-action"
            type="button"
            disabled={actionBusy !== null}
            onClick={() => void recheckRuntime()}
          >
            {recheckEngineLabel(actionBusy === "recheck")}
          </button>
        </div>
        {actionMessage ? <p className="model-selection-message">{actionMessage}</p> : null}
        {actionError ? <p className="model-selection-error">{actionError}</p> : null}
      </div>
    );
  }

  if (needsContextBuild) {
    const isRunning = contextBuildJob
      ? ["queued", "running"].includes(contextBuildJob.status)
      : false;
    const isDone = contextBuildJob?.status === "completed";
    return (
      <div className="runtime-next-action-panel">
        <div className="runtime-next-action-copy">
          <StatusBadge label="Next step" />
          <div>
            <strong>Build context so Ask can use local sources.</strong>
            <p>
              The models match the active runtime. Build the workspace context once with <code>{activeEmbedding}</code>.
            </p>
          </div>
        </div>
        <div className="runtime-next-action-buttons">
          <button
            className="primary-button"
            type="button"
            disabled={isRunning || isDone}
            onClick={() => void onBuildContext()}
          >
            {isRunning ? "Building context…" : isDone ? "Context built" : "Build context now"}
          </button>
          <button className="secondary-action" type="button" onClick={() => void recheckRuntime()}>
            {recheckEngineLabel(false)}
          </button>
        </div>
        {contextBuildJob?.message ? (
          <p className="context-build-callout-note">{contextBuildJob.message}</p>
        ) : null}
        {contextBuildError ? <p className="model-selection-error">{contextBuildError}</p> : null}
        {actionMessage ? <p className="model-selection-message">{actionMessage}</p> : null}
        {actionError ? <p className="model-selection-error">{actionError}</p> : null}
      </div>
    );
  }

  if (isReady) {
    return (
      <div className="runtime-next-action-panel runtime-next-action-panel-ready is-compact">
        <span className="runtime-ready-line">
          <span className="runtime-ready-dot" aria-hidden="true" />
          Ready — answers use your local project context.
        </span>
        <button className="runtime-ready-recheck" type="button" onClick={() => void recheckRuntime()}>
          {recheckEngineLabel(actionBusy === "recheck")}
        </button>
        {actionMessage ? <p className="model-selection-message">{actionMessage}</p> : null}
        {actionError ? <p className="model-selection-error">{actionError}</p> : null}
      </div>
    );
  }

  return (
    <div className="runtime-next-action-panel runtime-next-action-panel-warning">
      <div className="runtime-next-action-copy">
        <StatusBadge label="Review needed" />
        <div>
          <strong>Model setup needs attention.</strong>
          <p>{getModelWorkspaceStatusMessage(dashboard)}</p>
          {answerModelMismatch ? (
            <p className="runtime-next-action-hint">
              The selected answer model <code>{selectedLlm}</code> can’t run, but the engine is
              running <code>{activeLlm}</code>. You can switch this workspace onto it.
            </p>
          ) : null}
        </div>
      </div>
      <div className="runtime-next-action-buttons">
        {answerModelMismatch ? (
          <button
            className="primary-button"
            type="button"
            disabled={actionBusy !== null}
            onClick={() => void useActiveLlmRuntime()}
          >
            {actionBusy === "use-active-llm"
              ? "Applying…"
              : `Use active answer model (${activeLlm})`}
          </button>
        ) : null}
        <button className="secondary-action" type="button" onClick={() => void recheckRuntime()}>
          {recheckEngineLabel(false)}
        </button>
      </div>
      {actionMessage ? <p className="model-selection-message">{actionMessage}</p> : null}
      {actionError ? <p className="model-selection-error">{actionError}</p> : null}
    </div>
  );
}

function formatProviderModel(provider: string | null | undefined, model: string | null | undefined): string {
  return provider && model ? `${provider}/${model}` : "not selected";
}


function LocalModelInstallPanel({
  workspaceId,
  onSelectionUpdated,
}: {
  workspaceId: string;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const [guide, setGuide] = useState<LocalModelInstallGuide | null>(null);
  const [installStatus, setInstallStatus] =
    useState<LocalModelInstallStatus | null>(null);
  const [workerPlan, setWorkerPlan] =
    useState<LocalModelDownloadWorkerPlan | null>(null);
  const [executionCapability, setExecutionCapability] =
    useState<LocalModelDownloadExecutionCapability | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState<LocalModelInstallDraft | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [draftingKey, setDraftingKey] = useState<string | null>(null);
  const [downloadJob, setDownloadJob] = useState<LocalModelDownloadJob | null>(
    null,
  );
  const [jobList, setJobList] = useState<LocalModelDownloadJobList | null>(
    null,
  );
  const [runningDraft, setRunningDraft] = useState(false);
  const [refreshingJob, setRefreshingJob] = useState(false);
  const [refreshingJobs, setRefreshingJobs] = useState(false);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [refreshingInstallStatus, setRefreshingInstallStatus] = useState(false);
  const [deletingModelName, setDeletingModelName] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getLocalModelInstallGuide(),
      getLocalModelInstallStatus(),
      getLocalModelDownloadWorkerPlan(),
      getLocalModelDownloadExecutionCapability(),
      listLocalModelDownloadJobs(workspaceId),
    ])
      .then(
        ([
          installGuide,
          installedStatus,
          downloadWorkerPlan,
          downloadCapability,
          downloadJobs,
        ]) => {
          if (!cancelled) {
            setGuide(installGuide);
            setInstallStatus(installedStatus);
            setWorkerPlan(downloadWorkerPlan);
            setExecutionCapability(downloadCapability);
            setJobList(downloadJobs);
            setError(null);
          }
        },
      )
      .catch((installError) => {
        if (!cancelled) {
          setError(errorMessage(installError));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);


  const createDraft = async (option: LocalModelInstallOption) => {
    const key = `${option.provider}-${option.model}`;
    setDraftingKey(key);
    setDraftError(null);
    try {
      const result = await createLocalModelInstallDraft({
        workspace_id: workspaceId,
        provider: option.provider,
        model: option.model,
        model_type: option.model_type,
      });
      setDraft(result);
      setDownloadJob(null);
      void refreshDownloadJobs();
    } catch (installDraftError) {
      setDraftError(errorMessage(installDraftError));
    } finally {
      setDraftingKey(null);
    }
  };

  const startDownloadJob = async () => {
    if (!draft) {
      return;
    }
    setRunningDraft(true);
    setDraftError(null);
    try {
      const job = await startLocalModelDownloadJob(draft.command_proposal.id);
      setDownloadJob(job);
      void refreshDownloadJobs();
      if (job.status === "succeeded") {
        void refreshInstallStatus();
      }
    } catch (downloadError) {
      setDraftError(errorMessage(downloadError));
    } finally {
      setRunningDraft(false);
    }
  };

  const refreshDownloadJob = async () => {
    if (!downloadJob) {
      return;
    }
    setRefreshingJob(true);
    setDraftError(null);
    try {
      const job = await getLocalModelDownloadJob(downloadJob.id);
      setDownloadJob(job);
      void refreshDownloadJobs();
      if (job.status === "succeeded") {
        void refreshInstallStatus();
      }
    } catch (downloadError) {
      setDraftError(errorMessage(downloadError));
    } finally {
      setRefreshingJob(false);
    }
  };

  const refreshDownloadJobs = async () => {
    setRefreshingJobs(true);
    try {
      const jobs = await listLocalModelDownloadJobs(workspaceId);
      setJobList(jobs);
    } catch (downloadJobsError) {
      setDraftError(errorMessage(downloadJobsError));
    } finally {
      setRefreshingJobs(false);
    }
  };

  const requestCancelJob = async (jobId: string) => {
    setCancellingJobId(jobId);
    setDraftError(null);
    try {
      const cancelled = await cancelLocalModelDownloadJob(jobId);
      if (downloadJob?.id === jobId) {
        setDownloadJob(cancelled);
      }
      await refreshDownloadJobs();
    } catch (cancelError) {
      setDraftError(errorMessage(cancelError));
    } finally {
      setCancellingJobId(null);
    }
  };

  const refreshInstallStatus = async () => {
    setRefreshingInstallStatus(true);
    try {
      const status = await getLocalModelInstallStatus();
      setInstallStatus(status);
    } catch (installStatusError) {
      setDraftError(errorMessage(installStatusError));
    } finally {
      setRefreshingInstallStatus(false);
    }
  };

  const handleDeleteInstalledModel = async (name: string) => {
    setDeletingModelName(name);
    setDraftError(null);
    try {
      await deleteInstalledModel(name);
      await refreshInstallStatus();
      // Refresh the workspace so Current setup / model selection reflect the
      // deletion (e.g. a previously-selected model now reads as Needs setup).
      await onSelectionUpdated();
    } catch (deleteError) {
      setDraftError(errorMessage(deleteError));
    } finally {
      setDeletingModelName(null);
    }
  };

  useEffect(() => {
    if (
      !downloadJob ||
      (downloadJob.status !== "queued" && downloadJob.status !== "running")
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshDownloadJob();
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [downloadJob?.id, downloadJob?.status]);

  if (loading) {
    return (
      <section className="panel model-install-panel">
        <PanelHeading
          eyebrow="Model install"
          title="Local model download plan"
        />
        <p className="panel-intro">
          Loading recommended local model install options…
        </p>
      </section>
    );
  }

  if (error || !guide) {
    return (
      <section className="panel model-install-panel">
        <PanelHeading
          eyebrow="Model install"
          title="Local model download plan"
        />
        <p className="model-selection-error">
          {error ?? "Could not load model install guide."}
        </p>
      </section>
    );
  }

  const guideOptions = asArray(guide.options);
  const installItems = asArray(installStatus?.items);
  const jobItems = asArray(jobList?.jobs);
  const activeJobs = jobItems.filter(
    (job) => job.status === "queued" || job.status === "running",
  );
  const recommendedInstallItems = installItems.filter((item) => item.recommended);
  const missingRecommended = recommendedInstallItems.filter(
    (item) => item.status !== "installed",
  );
  const installedRecommendedCount = recommendedInstallItems.filter(
    (item) => item.status === "installed",
  ).length;
  const openDownloads =
    missingRecommended.length > 0 || Boolean(draft) || Boolean(downloadJob);

  return (
    <section className="panel model-install-panel model-manager-panel">
      <PanelHeading
        eyebrow="Local model manager"
        title="Install and verify local models"
        status={getModelManagerStatus(
          installStatus,
          jobList,
          executionCapability,
        )}
      />
      {installStatus && !installStatus.runtime_reachable ? (
        <div className="ollama-required-notice" role="status">
          <div>
            <strong>Ollama is needed to download and run local models</strong>
            <p>
              This app downloads and runs models through Ollama. Install it from{" "}
              <span className="ollama-required-link">ollama.com/download</span> if you
              don't have it, then start the Ollama app and re-check.
            </p>
          </div>
          <button
            className="secondary-action"
            type="button"
            onClick={() => void refreshInstallStatus()}
            disabled={refreshingInstallStatus}
          >
            {refreshingInstallStatus ? "Checking…" : "Re-check"}
          </button>
        </div>
      ) : null}
      {activeJobs.length > 0 ? (
        <div className="model-manager-active-stack">
          {activeJobs.slice(0, 2).map((job) => (
            <ModelDownloadJobStatusCard
              key={job.id}
              job={downloadJob?.id === job.id ? downloadJob : job}
              isRefreshing={refreshingJob}
              onRefresh={() => {
                setDownloadJob(job);
                void getLocalModelDownloadJob(job.id)
                  .then((latest) => {
                    setDownloadJob(latest);
                    void refreshDownloadJobs();
                    if (latest.status === "succeeded") {
                      void refreshInstallStatus();
                    }
                  })
                  .catch((downloadError) =>
                    setDraftError(errorMessage(downloadError)),
                  );
              }}
              onRefreshInstalled={() => void refreshInstallStatus()}
              onCancel={() => void requestCancelJob(job.id)}
              isCancelling={cancellingJobId === job.id}
            />
          ))}
        </div>
      ) : null}

      {downloadJob && activeJobs.every((job) => job.id !== downloadJob.id) ? (
        <ModelDownloadJobStatusCard
          job={downloadJob}
          isRefreshing={refreshingJob}
          onRefresh={() => void refreshDownloadJob()}
          onRefreshInstalled={() => void refreshInstallStatus()}
          onCancel={() => void requestCancelJob(downloadJob.id)}
          isCancelling={cancellingJobId === downloadJob.id}
        />
      ) : null}

      <details className="model-manager-section is-download" open={openDownloads}>
        <summary>
          <div>
            <span className="eyebrow">Add</span>
            <strong>
              {missingRecommended.length > 0
                ? "Recommended models need attention"
                : "Add or change a model"}
            </strong>
            <p>
              {missingRecommended.length > 0
                ? `${missingRecommended.length} recommended model(s) are not installed yet.`
                : "Open only when you want to add or change local models."}
            </p>
          </div>
        </summary>
        <div className="model-install-section-heading">
          <div>
            <span className="eyebrow">Choose</span>
            <strong>Recommended downloads</strong>
            <p>
              Answer models generate replies. Search models build local context
              for RAG.
            </p>
          </div>
        </div>
        <div
          className="model-install-grid"
          aria-label="Recommended local model downloads"
        >
          {guideOptions.map((option) => {
            const installedItem = installStatus?.items.find(
              (item) =>
                item.provider === option.provider &&
                item.model === option.model,
            );
            const isInstalled = installedItem?.status === "installed";
            return (
              <article
                className="model-install-card"
                key={`${option.provider}-${option.model}`}
              >
                <div className="model-install-card-heading">
                  <span className="model-install-type">
                    {option.model_type === "llm"
                      ? "AI answers"
                      : "Search context"}
                  </span>
                  {isInstalled ? (
                    <StatusBadge label="Installed" />
                  ) : option.recommended ? (
                    <StatusBadge label="Recommended" />
                  ) : null}
                </div>
                <strong>{option.display_name}</strong>
                <p>{option.purpose}</p>
                <dl>
                  <div>
                    <dt>Model</dt>
                    <dd>
                      {option.provider}/{option.model}
                    </dd>
                  </div>
                  <div>
                    <dt>Size</dt>
                    <dd>{option.estimated_size ?? "Check Ollama"}</dd>
                  </div>
                </dl>
                <div className="model-install-actions">
                  <button
                    className="secondary-button model-install-draft-button"
                    type="button"
                    onClick={() => void createDraft(option)}
                    disabled={
                      draftingKey === `${option.provider}-${option.model}` ||
                      isInstalled
                    }
                  >
                    {isInstalled
                      ? "Installed"
                      : draftingKey === `${option.provider}-${option.model}`
                        ? "Preparing…"
                        : "Download"}
                  </button>
                  {!isInstalled && !executionCapability?.execution_enabled ? (
                    <CopyButton text={option.install_command} label="pull command" />
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
        {draftError ? (
          <p className="model-selection-error">{draftError}</p>
        ) : null}
        {draft ? (
          <div className="model-install-draft-summary">
            <div>
              <span className="eyebrow">Ready to download</span>
              <strong>{draft.display_name}</strong>
              <p>{draft.safety_summary}</p>
            </div>
            <div className="model-install-draft-actions">
              <button
                className="primary-action"
                type="button"
                disabled={
                  !executionCapability?.execution_enabled || runningDraft
                }
                onClick={() => void startDownloadJob()}
                title={executionCapability?.disabled_reason ?? undefined}
              >
                {runningDraft ? "Starting…" : "Start download"}
              </button>
              {!executionCapability?.execution_enabled ? (
                <CopyButton text={draft.command} label="command" />
              ) : null}
            </div>
          </div>
        ) : null}
      </details>

      <details
        className="model-manager-section is-installed"
        open={
          (installStatus?.installed_count ?? 0) > 0 ||
          !installStatus?.runtime_reachable
        }
      >
        <summary>
          <div>
            <span className="eyebrow">Manage</span>
            <strong>Installed models & disk space</strong>
            <p>See installed models with their size on disk, and delete ones you no longer need.</p>
          </div>
        </summary>
        {installStatus ? (
          <InstalledModelsStatusPanel
            status={installStatus}
            isRefreshing={refreshingInstallStatus}
            onRefresh={() => void refreshInstallStatus()}
            deletingModelName={deletingModelName}
            onDelete={(name) => void handleDeleteInstalledModel(name)}
          />
        ) : null}
      </details>

    </section>
  );
}

function getModelManagerStatus(
  installStatus: LocalModelInstallStatus | null,
  jobList: LocalModelDownloadJobList | null,
  capability: LocalModelDownloadExecutionCapability | null,
): string {
  if (jobList?.running_count && jobList.running_count > 0) {
    return "downloading";
  }
  if (!installStatus?.runtime_reachable) {
    return "offline";
  }
  const recommended = asArray(installStatus.items).filter((item) => item.recommended);
  const missing = recommended.filter((item) => item.status !== "installed");
  if (missing.length === 0 && recommended.length > 0) {
    return "ready";
  }
  return capability?.execution_enabled ? "ready to download" : "manual setup";
}

function ModelDownloadJobStatusCard({
  job,
  isRefreshing,
  onRefresh,
  onRefreshInstalled,
  onCancel,
  isCancelling,
}: {
  job: LocalModelDownloadJob;
  isRefreshing: boolean;
  onRefresh: () => void;
  onRefreshInstalled: () => void;
  onCancel: () => void;
  isCancelling: boolean;
}) {
  const isFinished = job.status === "succeeded" || job.status === "failed";
  const friendlyStatus = getFriendlyDownloadJobStatus(job);

  return (
    <div
      className={`model-download-job-card model-download-job-card--${job.status}`}
    >
      <div className="model-download-job-header">
        <div>
          <span className="eyebrow">Download progress</span>
          <strong>{friendlyStatus.title}</strong>
          <p>{friendlyStatus.message}</p>
        </div>
        <StatusBadge label={friendlyStatus.badge} />
      </div>
      <div
        className="model-download-progress"
        aria-label="Model download progress"
      >
        <span
          style={{
            width: `${Math.max(0, Math.min(100, job.progress_percent))}%`,
          }}
        />
      </div>
      <div className="model-download-job-meta">
        <span>{job.display_name}</span>
        <span>{job.progress_percent}%</span>
      </div>
      {job.cancel_requested_at ? (
        <div className="model-download-cancel-note">
          <strong>Cancel requested safely.</strong>
          <p>{job.cancellation_summary}</p>
        </div>
      ) : null}
      {job.status === "succeeded" ? (
        <div className="model-download-success-note">
          <strong>Model download finished.</strong>
          <p>
            Refresh the installed models list, then save this model as a
            workspace preference if you want to use it.
          </p>
        </div>
      ) : null}
      {job.status === "failed" ? (
        <details className="model-download-output">
          <summary>Show backend output</summary>
          {job.stderr_preview ? (
            <pre>{job.stderr_preview}</pre>
          ) : (
            <p>No stderr output was returned.</p>
          )}
        </details>
      ) : null}
      <div className="model-download-job-actions">
        <button
          className="secondary-button model-install-draft-button"
          type="button"
          disabled={isRefreshing}
          onClick={onRefresh}
        >
          {isRefreshing
            ? "Refreshing…"
            : isFinished
              ? "Refresh job"
              : "Refresh status"}
        </button>
        {job.cancellable &&
        (job.status === "queued" || job.status === "running") ? (
          <button
            className="secondary-button model-install-draft-button"
            type="button"
            disabled={isCancelling}
            onClick={onCancel}
          >
            {isCancelling
              ? "Requesting…"
              : job.status === "queued"
                ? "Cancel download"
                : "Request safe cancel"}
          </button>
        ) : null}
        {job.status === "succeeded" ? (
          <button
            className="primary-button model-install-draft-button"
            type="button"
            onClick={onRefreshInstalled}
          >
            Re-check installed models
          </button>
        ) : null}
      </div>
    </div>
  );
}

function getFriendlyDownloadJobStatus(job: LocalModelDownloadJob): {
  title: string;
  message: string;
  badge: string;
} {
  if (job.status === "cancelled") {
    return {
      title: "Download cancelled",
      message:
        job.progress_message || "The download was cancelled before execution.",
      badge: "Cancelled",
    };
  }
  if (job.status === "succeeded") {
    return {
      title: "Download complete",
      message: `${job.display_name} is ready to verify in the installed models list.`,
      badge: "Complete",
    };
  }
  if (job.status === "failed") {
    return {
      title: "Download needs attention",
      message:
        job.progress_message ||
        "The backend worker could not finish the download.",
      badge: "Failed",
    };
  }
  if (job.status === "running") {
    return {
      title: "Downloading model",
      message: job.progress_message,
      badge: "Running",
    };
  }
  return {
    title: "Download queued",
    message: job.progress_message,
    badge: "Queued",
  };
}

function InstalledModelsStatusPanel({
  status,
  isRefreshing,
  onRefresh,
  deletingModelName,
  onDelete,
}: {
  status: LocalModelInstallStatus;
  isRefreshing: boolean;
  onRefresh: () => void;
  deletingModelName: string | null;
  onDelete: (name: string) => void;
}) {
  const [confirmName, setConfirmName] = useState<string | null>(null);
  return (
    <div className="installed-models-panel">
      <div className="installed-models-header">
        <div>
          <span className="eyebrow">Installed models</span>
          <strong>
            {status.runtime_reachable
              ? "Local Ollama models"
              : "Ollama is offline"}
          </strong>
          <p>
            {status.runtime_reachable
              ? status.summary
              : "Start Ollama, then refresh this read-only check."}
          </p>
        </div>
        <div className="installed-models-header-actions">
          <StatusBadge
            label={status.runtime_reachable ? status.status : "Offline"}
          />
          <button
            className="secondary-button"
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Checking…" : "Refresh"}
          </button>
        </div>
      </div>
      {(() => {
        const items = asArray(status.items);
        const answerItems = items.filter((item) => item.model_type === "llm");
        const searchItems = items.filter(
          (item) => item.model_type === "embedding",
        );
        const otherItems = items.filter(
          (item) => item.model_type !== "llm" && item.model_type !== "embedding",
        );
        const renderGroup = (label: string, groupItems: typeof items) =>
          groupItems.length > 0 ? (
            <div className="installed-models-group">
              <h4 className="installed-models-group-label">{label}</h4>
              <div
                className="installed-models-grid"
                aria-label={`${label} status`}
              >
                {groupItems.map((item) => (
                  <InstalledModelCard
                    key={`${item.provider}-${item.model}`}
                    item={item}
                    confirmName={confirmName}
                    deletingModelName={deletingModelName}
                    onRequestConfirm={setConfirmName}
                    onDelete={onDelete}
                  />
                ))}
              </div>
            </div>
          ) : null;
        return (
          <>
            {renderGroup("Answer models", answerItems)}
            {renderGroup("Search models", searchItems)}
            {renderGroup("Other", otherItems)}
          </>
        );
      })()}
      <p className="installed-models-note">
        Reads {status.runtime_url}/api/tags. Delete removes the model from your
        local Ollama runtime to free disk space; your project files are never
        touched.
      </p>
    </div>
  );
}

function InstalledModelCard({
  item,
  confirmName,
  deletingModelName,
  onRequestConfirm,
  onDelete,
}: {
  item: LocalModelInstallStatus["items"][number];
  confirmName: string | null;
  deletingModelName: string | null;
  onRequestConfirm: (name: string | null) => void;
  onDelete: (name: string) => void;
}) {
  const deleteName = item.installed_as ?? item.model;
  const [expanded, setExpanded] = useState(false);
  const installed = item.status === "installed";
  const roleLabel =
    item.model_type === "embedding"
      ? "Search model"
      : item.model_type === "llm"
        ? "Answer model"
        : "Model";
  const contextValue = item.context_length ?? item.embedding_length;
  return (
    <article className={`installed-model-row${expanded ? " is-expanded" : ""}`}>
      <button
        type="button"
        className="installed-model-row-head"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        <span className={`installed-model-icon is-${item.model_type === "embedding" ? "search" : "answer"}`} aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
            {item.model_type === "embedding" ? (
              <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>
            ) : (
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            )}
          </svg>
        </span>
        <span className="installed-model-name-block">
          <span className="installed-model-name">{item.display_name}</span>
          <span className="installed-model-role">{roleLabel}</span>
        </span>
        {installed ? (
          <span className="installed-model-size">{formatModelBytes(item.size_bytes)}</span>
        ) : (
          <span className={`model-status-pill model-status-${item.status}`}>{item.status}</span>
        )}
        <svg className="installed-model-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {expanded ? (
        <div className="installed-model-detail">
          {item.detail ? <p className="installed-model-detail-text">{item.detail}</p> : null}
          <dl className="installed-model-metadata">
            <div>
              <dt>Source</dt>
              <dd>{item.installed_as ? `Installed as ${item.installed_as}` : `${item.provider}/${item.model}`}</dd>
            </div>
            <div>
              <dt>Parameters</dt>
              <dd>{item.parameter_size ?? "—"}</dd>
            </div>
            <div>
              <dt>Quantization</dt>
              <dd>{item.quantization_level ?? "—"}</dd>
            </div>
            <div>
              <dt>{item.model_type === "embedding" ? "Embedding size" : "Context length"}</dt>
              <dd>{contextValue != null ? contextValue.toLocaleString() : "—"}</dd>
            </div>
            <div>
              <dt>Capabilities</dt>
              <dd>{asArray(item.capabilities).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt>Installed / updated</dt>
              <dd>{formatModelTimestamp(item.modified_at)}</dd>
            </div>
          </dl>
          {installed ? (
            <div className="installed-model-actions">
              {confirmName === deleteName ? (
                <>
                  <button
                    type="button"
                    className="workspace-card-action is-danger"
                    disabled={deletingModelName !== null}
                    onClick={() => {
                      onDelete(deleteName);
                      onRequestConfirm(null);
                    }}
                  >
                    {deletingModelName === deleteName ? "Deleting…" : "Confirm delete"}
                  </button>
                  <button
                    type="button"
                    className="workspace-card-action"
                    disabled={deletingModelName !== null}
                    onClick={() => onRequestConfirm(null)}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="workspace-card-action is-danger"
                  disabled={deletingModelName !== null}
                  onClick={() => onRequestConfirm(deleteName)}
                >
                  Delete model
                </button>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function formatModelBytes(value: number | null): string {
  if (value === null) {
    return "Not reported";
  }
  return `${(value / (1024 ** 3)).toFixed(1)} GB`;
}

function formatModelTimestamp(value: string | null): string {
  if (value === null) {
    return "Not reported";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function GuidedModelSetupPanel({
  workspaceId,
  developerMode = false,
  backend = "ollama",
  onApplySelection,
  onSelectionUpdated,
}: {
  workspaceId: string;
  developerMode?: boolean;
  backend?: "ollama" | "llamacpp";
  onApplySelection: (
    modelType: "llm" | "embedding",
    provider: string,
    model: string,
  ) => Promise<void> | void;
  onSelectionUpdated?: () => Promise<void> | void;
}) {
  const [guide, setGuide] = useState<GuidedModelSetupGuide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [llmChoice, setLlmChoice] = useState("");
  const [embeddingChoice, setEmbeddingChoice] = useState("");
  const [customLlm, setCustomLlm] = useState("");
  const [customEmbedding, setCustomEmbedding] = useState("");
  const [saving, setSaving] = useState<"llm" | "embedding" | null>(null);
  const [installPercent, setInstallPercent] = useState<number | null>(null);
  const [installJobId, setInstallJobId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Load the Ollama guided setup — but only in Ollama mode. This hook MUST run on
  // every render (before any early return), or switching the workspace's engine
  // from llama.cpp to Ollama would change the hook count between renders and crash
  // the screen with React error #300 ("rendered more hooks than the previous
  // render"). The body no-ops for llama.cpp so nothing is fetched there.
  useEffect(() => {
    if (backend === "llamacpp") {
      return;
    }
    let cancelled = false;
    getGuidedModelSetup(workspaceId)
      .then((result) => {
        if (cancelled) {
          return;
        }
        setGuide(result);
        setError(null);
        setLlmChoice(
          toSetupChoiceValue(
            asArray(result.llm?.options)[0]?.provider,
            asArray(result.llm?.options)[0]?.model,
          ),
        );
        setEmbeddingChoice(
          toSetupChoiceValue(
            asArray(result.embedding?.options)[0]?.provider,
            asArray(result.embedding?.options)[0]?.model,
          ),
        );
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(errorMessage(loadError));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, backend]);

  // The built-in llama.cpp engine manages GGUF model files, not Ollama pulls, so
  // in that mode the Ollama guided controls don't apply — show the llama.cpp
  // panel instead (it has its own per-model download + Stop).
  if (backend === "llamacpp") {
    return (
      <section className="panel guided-model-setup-panel">
        <PanelHeading eyebrow="Guided setup" title="Built-in engine models" />
        <p className="panel-intro">
          This workspace uses the built-in llama.cpp engine. Manage its local
          models below — nothing is installed through Ollama.
        </p>
        <LlamaCppModelsPanel
          workspaceId={workspaceId}
          onSelectionUpdated={onSelectionUpdated}
        />
      </section>
    );
  }

  async function saveGuidedSelection(modelType: "llm" | "embedding") {
    const value = modelType === "llm" ? llmChoice : embeddingChoice;
    const parsed = parseSetupChoiceValue(value);
    const customModel = (
      modelType === "llm" ? customLlm : customEmbedding
    ).trim();
    const provider = parsed?.provider ?? "ollama";
    const model = parsed?.model === "__custom__" ? customModel : parsed?.model;
    if (!model) {
      setError("Choose a model or enter a custom model name.");
      return;
    }

    setSaving(modelType);
    setError(null);
    setMessage(null);
    try {
      await onApplySelection(modelType, provider, model);
      if (provider !== "ollama") {
        setMessage(
          `${modelType === "llm" ? "AI answer model" : "Search context model"} saved as ${provider}/${model}.`,
        );
        return;
      }

      const installed = await getLocalModelInstallStatus();
      const installedModel = asArray(installed.items).find(
        (item) =>
          item.provider === provider &&
          [item.model, item.installed_as?.replace(/:latest$/, "")]
            .filter(Boolean)
            .some((name) => name === model || `${name}:latest` === model),
      );
      if (installedModel?.status === "installed") {
        setMessage(
          `${provider}/${model} is selected, installed, and ready for ${modelType === "llm" ? "Ask" : "context building"}.`,
        );
        return;
      }

      // Ask the Ollama daemon directly. No shell command, so this needs no
      // execution permission and is not limited to the app's own catalog — the
      // restriction that used to send people to a terminal for anything else.
      // Only if the daemon cannot be reached do we fall back to the older
      // command-proposal path, which still exists for the shell case.
      try {
        let pull = await startOllamaPull(model);
        setInstallPercent(pull.progress_percent ?? 0);
        setMessage(`Downloading ${provider}/${model}…`);
        for (
          let attempt = 0;
          attempt < 2400 && !["succeeded", "failed", "cancelled"].includes(pull.status);
          attempt += 1
        ) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          try {
            pull = await getOllamaPull(pull.id);
          } catch {
            break;
          }
          setInstallPercent(pull.progress_percent ?? null);
          setMessage(pull.progress_message || `Downloading ${provider}/${model}…`);
        }
        if (pull.status === "succeeded") {
          setMessage(
            `${provider}/${model} installed and selected — ready for ${modelType === "llm" ? "Ask" : "context building"}.`,
          );
          return;
        }
        if (pull.status === "failed" && pull.error) {
          setError(pull.error);
          return;
        }
      } catch {
        // Fall through to the older path below.
      }

      const draft = await createLocalModelInstallDraft({
        workspace_id: workspaceId,
        provider,
        model,
        model_type: modelType,
      });
      const capability = await getLocalModelDownloadExecutionCapability();
      if (capability.execution_enabled) {
        let current = await startLocalModelDownloadJob(draft.command_proposal.id);
        setInstallJobId(current.id);
        setInstallPercent(current.progress_percent ?? 0);
        setMessage(`Downloading ${provider}/${model}…`);
        for (
          let attempt = 0;
          attempt < 1200 &&
          !["succeeded", "failed", "cancelled"].includes(current.status);
          attempt += 1
        ) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          try {
            current = await getLocalModelDownloadJob(current.id);
          } catch {
            break;
          }
          if (current.status === "running") {
            setInstallPercent(current.progress_percent ?? null);
            setMessage(
              current.progress_percent != null
                ? `Downloading ${provider}/${model}… ${current.progress_percent}%`
                : `Downloading ${provider}/${model}…`,
            );
          }
        }
        if (current.status === "succeeded") {
          setMessage(
            `${provider}/${model} installed and selected — ready for ${modelType === "llm" ? "Ask" : "context building"}.`,
          );
        } else if (current.status === "failed") {
          setError(
            `Could not install ${provider}/${model}. ${current.stderr_preview ?? current.progress_message ?? "Check the exact model tag and that Ollama is running, then try again."}`,
          );
        } else {
          setMessage(`${provider}/${model} download ${current.status}.`);
        }
      } else {
        setMessage(
          `${provider}/${model} is selected but not installed. A safe download draft is ready in the model manager below.`,
        );
      }
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(null);
      setInstallPercent(null);
      setInstallJobId(null);
    }
  }

  async function cancelGuidedDownload() {
    if (!installJobId) {
      return;
    }
    try {
      await cancelLocalModelDownloadJob(installJobId);
      setMessage("Download stopped.");
    } catch (cancelError) {
      setError(errorMessage(cancelError));
    }
  }

  if (error && !guide) {
    return (
      <section className="panel guided-model-setup-panel">
        <PanelHeading eyebrow="Guided setup" title="Choose local models" />
        <p className="model-selection-error">{error}</p>
      </section>
    );
  }

  if (!guide) {
    return (
      <section className="panel guided-model-setup-panel">
        <PanelHeading eyebrow="Guided setup" title="Choose local models" />
        <p className="panel-intro">Loading local model setup guidance…</p>
      </section>
    );
  }

  const llmSection = normalizeGuidedModelSection(guide.llm, "llm");
  const embeddingSection = normalizeGuidedModelSection(guide.embedding, "embedding");

  return (
    <section className="panel guided-model-setup-panel">
      <PanelHeading eyebrow="Guided setup" title={guide.title} />
      <p className="panel-intro">{guide.summary}</p>
      <div className="guided-model-grid">
        <GuidedModelSetupControl
          section={llmSection}
          value={llmChoice}
          customValue={customLlm}
          disabled={saving !== null}
          isSaving={saving === "llm"}
          installPercent={installPercent}
          canStop={saving === "llm" && installJobId !== null}
          onStop={() => void cancelGuidedDownload()}
          note="The model that writes the answers when you ask questions."
          onChange={setLlmChoice}
          onCustomChange={setCustomLlm}
          onSave={() => void saveGuidedSelection("llm")}
        />
        <GuidedModelSetupControl
          section={embeddingSection}
          value={embeddingChoice}
          customValue={customEmbedding}
          disabled={saving !== null}
          isSaving={saving === "embedding"}
          installPercent={installPercent}
          canStop={saving === "embedding" && installJobId !== null}
          onStop={() => void cancelGuidedDownload()}
          note="Turns your project into searchable form so the AI can find relevant files. nomic-embed-text is a great default; changing it later rebuilds the index."
          onChange={setEmbeddingChoice}
          onCustomChange={setCustomEmbedding}
          onSave={() => void saveGuidedSelection("embedding")}
        />
      </div>
      <p className="guided-model-safety-note">
        Picking a model that isn't installed yet downloads it (you'll see progress).
        Your project files, backend, and existing index aren't touched until you act.
      </p>
      {message ? <p className="model-selection-message">{message}</p> : null}
      {error ? <p className="model-selection-error">{error}</p> : null}
    </section>
  );
}

function GuidedModelSetupControl({
  section,
  value,
  customValue,
  disabled,
  isSaving,
  installPercent,
  canStop = false,
  onStop,
  note,
  onChange,
  onCustomChange,
  onSave,
}: {
  section: GuidedModelSetupSection;
  value: string;
  customValue: string;
  disabled: boolean;
  isSaving: boolean;
  installPercent: number | null;
  canStop?: boolean;
  onStop?: () => void;
  note?: string;
  onChange: (value: string) => void;
  onCustomChange: (value: string) => void;
  onSave: () => void;
}) {
  const isCustom = parseSetupChoiceValue(value)?.model === "__custom__";
  const options = asArray(section.options);
  const selectedOption = options.find(
    (option) => toSetupChoiceValue(option.provider, option.model) === value,
  );
  return (
    <article className="guided-model-card">
      <div className="guided-model-card-heading">
        <div>
          <span>{section.model_type === "llm" ? "Answer model" : "Search model"}</span>
          <strong>{section.title}</strong>
        </div>
      </div>
      {note ? <p className="guided-model-note">{note}</p> : null}
      <label className="guided-model-select">
        <span className="sr-only">Choose {section.title}</span>
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option
              key={`${option.provider}/${option.model}`}
              value={toSetupChoiceValue(option.provider, option.model)}
            >
              {option.display_name}
              {option.estimated_size ? ` · ${option.estimated_size}` : ""}
              {option.recommended ? " · recommended" : ""}
            </option>
          ))}
          <option value="ollama||__custom__">Custom Ollama model…</option>
        </select>
      </label>
      {isCustom ? (
        <label className="guided-model-custom-field">
          <span className="sr-only">Custom model name</span>
          <input
            value={customValue}
            disabled={disabled}
            placeholder={
              section.model_type === "llm"
                ? "qwen2.5-coder:7b"
                : "nomic-embed-text"
            }
            onChange={(event) => onCustomChange(event.target.value)}
          />
        </label>
      ) : selectedOption ? (
        <div className="guided-model-selected-meta">
          {selectedOption.fit_label ? (
            <span className={`guided-model-fit guided-model-fit-${selectedOption.fit ?? "unknown"}`}>
              {selectedOption.fit_label}
            </span>
          ) : null}
          {selectedOption.estimated_size ? <em>↓ {selectedOption.estimated_size}</em> : null}
          {selectedOption.quality_tier ? <em>Quality: {selectedOption.quality_tier}</em> : null}
          {selectedOption.speed_tier ? <em>Speed: {selectedOption.speed_tier}</em> : null}
          {selectedOption.local_only ? <em>Offline</em> : null}
        </div>
      ) : null}
      <button
        className="model-selection-save-button"
        type="button"
        disabled={disabled}
        onClick={onSave}
      >
        {isSaving
          ? "Setting up…"
          : `Use & install ${section.title}`}
      </button>
      {isSaving ? (
        <div className="install-progress" role="status" aria-label="Model download progress">
          <div
            className={`install-progress-bar${installPercent === null ? " is-indeterminate" : ""}`}
          >
            <span
              style={installPercent === null ? undefined : { width: `${installPercent}%` }}
            />
          </div>
          <span className="install-progress-label">
            {installPercent === null ? "Preparing…" : `${installPercent}%`}
          </span>
          {canStop && onStop ? (
            <button
              type="button"
              className="guided-model-stop-button"
              onClick={onStop}
            >
              Stop
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function toSetupChoiceValue(
  provider: string | undefined,
  model: string | undefined,
): string {
  return provider && model ? `${provider}||${model}` : "";
}

function parseSetupChoiceValue(
  value: string,
): { provider: string; model: string } | null {
  const [provider, model] = value.split("||");
  if (!provider || !model) {
    return null;
  }
  return { provider, model };
}

function getSearchContextStatusLabel(dashboard: WorkspaceModelsDashboard): string {
  if (dashboard.usage_plan.can_search_with_selected_embedding) {
    return "Ready";
  }
  if (dashboard.embedding_indexing_plan.plan_status === "needs_index") {
    return "Needs context build";
  }
  if (dashboard.embedding_indexing_plan.plan_status === "runtime_mismatch") {
    return "Needs runtime review";
  }
  if (dashboard.selected_embedding_model === null) {
    return "Needs setup";
  }
  return "Needs attention";
}

function getModelWorkspaceStatusMessage(dashboard: WorkspaceModelsDashboard): string {
  if (dashboard.usage_plan.can_use_selected_models_fully) {
    return "Ready to ask questions with the current workspace models.";
  }
  if (dashboard.embedding_indexing_plan.plan_status === "needs_index") {
    return "The search model is selected. Build workspace context once so Ask can use local sources.";
  }
  if (dashboard.embedding_indexing_plan.plan_status === "runtime_mismatch") {
    return "The selected search model differs from the backend runtime. Restart with that model before rebuilding context.";
  }
  return "Review the setup guidance below before relying on this workspace.";
}

function SimpleModelCard({
  label,
  provider,
  model,
  description,
  status,
}: {
  label: string;
  provider: string | null;
  model: string | null;
  description: string;
  status: string;
}) {
  // Humanized name front and center; the exact provider-qualified id stays
  // one hover away — raw GGUF paths made the app's primary model card
  // unreadable ("llamacpp/Org/Repo-GGUF/file.Q4_K_M.gguf").
  const displayModel = model ? formatModelLabel(provider, model) : "Not selected";
  const rawTitle = model ? `${provider ?? "unknown"}/${model}` : undefined;

  return (
    <article className="simple-model-card">
      <div>
        <span>{label}</span>
        <strong title={rawTitle}>{displayModel}</strong>
      </div>
      <p>{description}</p>
      {status !== "Ready" ? <StatusBadge label={status} /> : null}
    </article>
  );
}

type ComparisonAttachedFile = {
  id: string;
  name: string;
  content: string;
  truncated: boolean;
  sizeKb: number;
};

const COMPARISON_FILE_MAX_BYTES = 200 * 1024;

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
  const [experimentHistory, setExperimentHistory] = useState<
    ModelExperimentRun[]
  >([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [attachedFiles, setAttachedFiles] = useState<ComparisonAttachedFile[]>([]);
  const [isDraggingFile, setIsDraggingFile] = useState(false);

  async function handleDroppedComparisonFiles(files: FileList | null) {
    if (!files || files.length === 0) {
      return;
    }
    const textFiles = Array.from(files)
      .filter((file) => !file.type.startsWith("image/"))
      .slice(0, 6);
    const parsed = await Promise.all(
      textFiles.map(async (file): Promise<ComparisonAttachedFile | null> => {
        const truncated = file.size > COMPARISON_FILE_MAX_BYTES;
        const slice = truncated ? file.slice(0, COMPARISON_FILE_MAX_BYTES) : file;
        try {
          return {
            id: `${Date.now()}-${file.name}-${Math.random().toString(36).slice(2, 8)}`,
            name: file.name,
            content: await slice.text(),
            truncated,
            sizeKb: Math.max(1, Math.round(file.size / 1024)),
          };
        } catch {
          return null;
        }
      }),
    );
    const readable = parsed.filter(
      (file): file is ComparisonAttachedFile => file !== null,
    );
    if (readable.length > 0) {
      setAttachedFiles((current) => [...current, ...readable].slice(0, 6));
    }
  }

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
      setError("Choose at least two different AI model candidates.");
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
      setRunError("Choose at least two different AI model candidates.");
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
        attached_documents: attachedFiles.map((file) => ({
          name: file.name,
          content: file.content,
        })),
      });
      setRunResult(result);
      setExperimentHistory((current) =>
        upsertExperimentHistory(current, result),
      );
    } catch (experimentError) {
      setRunError(errorMessage(experimentError));
      setRunResult(null);
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <section className="panel model-experiment-planner-panel">
      <div className="model-experiment-header">
        <p className="eyebrow">Compare</p>
        <h2>Model face-off</h2>
        <span>
          Two local models, one question — see which answers your project
          better, then make the winner this project's model.
        </span>
      </div>
      <div className="model-experiment-form">
        <label
          className={`model-experiment-question${isDraggingFile ? " is-drag-over" : ""}`}
          onDragOver={(event) => {
            if (event.dataTransfer?.types?.includes("Files")) {
              event.preventDefault();
              setIsDraggingFile(true);
            }
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              setIsDraggingFile(false);
            }
          }}
          onDrop={(event) => {
            if (event.dataTransfer?.files?.length) {
              event.preventDefault();
              setIsDraggingFile(false);
              void handleDroppedComparisonFiles(event.dataTransfer.files);
            }
          }}
        >
          <span>Comparison question</span>
          <textarea
            value={question}
            rows={3}
            placeholder="Ask something — or drop a log/config file here and both models will analyze it."
            onChange={(event) => setQuestion(event.target.value)}
          />
          {isDraggingFile ? (
            <div className="ask-drop-overlay" aria-hidden="true">
              Drop to attach — both models will analyze the file
            </div>
          ) : null}
        </label>
        {attachedFiles.length > 0 ? (
          <div className="ask-file-chips" aria-label="Attached files">
            {attachedFiles.map((file) => (
              <span key={file.id} className="ask-file-chip">
                <span className="ask-file-chip-icon" aria-hidden="true">
                  ▤
                </span>
                <span className="ask-file-chip-name" title={file.name}>
                  {file.name}
                </span>
                <span className="ask-file-chip-size">
                  {file.truncated
                    ? `${Math.round(COMPARISON_FILE_MAX_BYTES / 1024)}KB+`
                    : `${file.sizeKb}KB`}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onClick={() =>
                    setAttachedFiles((current) =>
                      current.filter((item) => item.id !== file.id),
                    )
                  }
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <div className="model-experiment-candidates">
          <ModelCandidateSelect
            label="Model A"
            value={candidateA}
            options={llmOptions}
            onChange={setCandidateA}
          />
          <ModelCandidateSelect
            label="Model B"
            value={candidateB}
            options={llmOptions}
            onChange={setCandidateB}
          />
        </div>
        <button
          className="model-selection-save-button model-experiment-run-button"
          type="button"
          disabled={isRunning || llmOptions.length < 2}
          onClick={() => void runComparisonExperiment()}
        >
          {isRunning ? "Running…" : "Run face-off"}
        </button>
        <span className="model-experiment-run-hint">
          Both models answer on your machine. Nothing else in your setup changes.
        </span>
      </div>
      {runError ? <p className="model-selection-error">{runError}</p> : null}
      {runResult ? (
        <ModelExperimentRunResult
          result={runResult}
          workspaceId={workspaceId}
          onSelectionUpdated={onSelectionUpdated}
        />
      ) : null}
      <details className="model-experiment-advanced">
        <summary>Preview the match-up first (optional)</summary>
        <p className="model-experiment-advanced-note">
          A dry run — it doesn't call any model or change your setup. It just
          shows what will happen and whether anything needs rebuilding.
        </p>
        <button
          className="secondary-action"
          type="button"
          disabled={isPlanning || llmOptions.length < 2}
          onClick={() => void generatePlan()}
        >
          {isPlanning ? "Preparing…" : "Prepare comparison"}
        </button>
        {error ? <p className="model-selection-error">{error}</p> : null}
        {plan ? <ModelExperimentPlanResult plan={plan} /> : null}
      </details>
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
          <option value="">No AI model options available</option>
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
          label={
            plan.can_compare_without_reindex
              ? "No rebuild needed"
              : "Rebuild needed"
          }
        />
        <StatusBadge
          label={plan.requires_reindex ? "Requires rebuild" : "Shared context"}
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
            <div className="model-candidate-headline">
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
                label={
                  candidate.requires_reindex
                    ? "Rebuild needed"
                    : "No rebuild needed"
                }
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
  const [promotingModel, setPromotingModel] = useState<string | null>(null);
  const [promoteMessage, setPromoteMessage] = useState<string | null>(null);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  async function useModelForProject(candidate: ModelExperimentRunCandidate) {
    const key = `${candidate.provider}/${candidate.model}`;
    setPromotingModel(key);
    setPromoteError(null);
    setPromoteMessage(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: candidate.provider,
        model: candidate.model,
        model_type: "llm",
        selected_reason: `Won a model face-off (${result.id}).`,
      });
      setPromoteMessage(
        `${candidate.provider}/${candidate.model} is now this project's answer model. Nothing else changed.`,
      );
      await onSelectionUpdated();
    } catch (promoteErr) {
      setPromoteError(errorMessage(promoteErr));
    } finally {
      setPromotingModel(null);
    }
  }

  return (
    <article className="model-experiment-run-result">
      <div className="model-experiment-plan-summary">
        <StatusBadge label={result.status} />
        <StatusBadge
          label={`${result.shared_context_sources_count} shared sources`}
        />
        <strong>Results — pick your winner</strong>
      </div>
      <div className="model-experiment-run-meta">
        <span>Created {formatDateTime(result.created_at)}</span>
        {result.completed_at ? (
          <span>Completed {formatDateTime(result.completed_at)}</span>
        ) : null}
      </div>
      <div className="model-experiment-candidate-list">
        {result.candidates.map((candidate) => {
          const key = `${candidate.provider}/${candidate.model}`;
          const isCompleted =
            candidate.status === "completed" && !candidate.error;
          return (
            <article
              className="model-experiment-candidate-card model-experiment-run-card"
              key={key}
            >
              <div className="model-candidate-headline">
                <strong>
                  {candidate.provider}/{candidate.model}
                </strong>
                <code>{candidate.status}</code>
              </div>
              <div className="model-experiment-candidate-badges">
                <StatusBadge label={candidate.status} />
                <StatusBadge label={`${candidate.latency_ms ?? 0} ms`} />
                <StatusBadge label={`${candidate.sources_count} sources`} />
                <StatusBadge
                  label={`${candidate.quality_warnings_count} notes`}
                />
              </div>
              {candidate.error ? (
                <p className="model-selection-error">{candidate.error}</p>
              ) : (
                <p className="model-experiment-answer-preview">
                  {candidate.answer
                    ? truncateText(candidate.answer, 560)
                    : "No answer returned."}
                </p>
              )}
              {isCompleted ? (
                <button
                  className="model-selection-save-button model-experiment-use-button"
                  type="button"
                  disabled={promotingModel !== null}
                  onClick={() => void useModelForProject(candidate)}
                >
                  {promotingModel === key
                    ? "Setting…"
                    : "🏆 Use this model for this project"}
                </button>
              ) : null}
            </article>
          );
        })}
      </div>
      {promoteMessage ? (
        <p className="model-selection-message">{promoteMessage}</p>
      ) : null}
      {promoteError ? (
        <p className="model-selection-error">{promoteError}</p>
      ) : null}
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
    (left, right) =>
      (left.latency_ms ?? Number.MAX_SAFE_INTEGER) -
      (right.latency_ms ?? Number.MAX_SAFE_INTEGER),
  )[0];
  const fewestWarnings = [...completed].sort(
    (left, right) => left.quality_warnings_count - right.quality_warnings_count,
  )[0];
  const mostSources = [...completed].sort(
    (left, right) => right.sources_count - left.sources_count,
  )[0];

  return (
    <div className="model-experiment-heuristics">
      <strong>Scoreboard</strong>
      <ul>
        <li>
          🏎️ Fastest: {fastest.provider}/{fastest.model} (
          {fastest.latency_ms ?? "unknown"} ms)
        </li>
        <li>
          ✅ Fewest verification notes: {fewestWarnings.provider}/
          {fewestWarnings.model} ({fewestWarnings.quality_warnings_count})
        </li>
        <li>
          📎 Most sources used: {mostSources.provider}/{mostSources.model} (
          {mostSources.sources_count})
        </li>
      </ul>
      <small>
        Just quick stats, not a verdict — you're the judge. Read both answers
        and decide which one you trust before picking a winner below.
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
          <strong>Comparison history</strong>
          <p>
            Review previous local model comparisons for this workspace.
            Selecting a run only opens its saved details and ratings UI.
          </p>
        </div>
        <button type="button" className="secondary-button" onClick={onRefresh}>
          {isLoading ? "Refreshing…" : "Refresh history"}
        </button>
      </div>
      {error ? <p className="model-selection-error">{error}</p> : null}
      {isLoading && experiments.length === 0 ? (
        <p className="model-experiment-rating-muted">
          Loading experiment history…
        </p>
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
                <StatusBadge
                  label={`${experiment.shared_context_sources_count} sources`}
                />
                <StatusBadge label={`${experiment.candidates.length} models`} />
              </div>
              <div className="model-experiment-history-candidates">
                {experiment.candidates.slice(0, 3).map((candidate) => (
                  <span
                    key={`${experiment.id}/${candidate.provider}/${candidate.model}`}
                  >
                    {candidate.provider}/{candidate.model} ·{" "}
                    {candidate.latency_ms ?? "?"} ms ·{" "}
                    {candidate.quality_warnings_count} notes
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
    defaultCandidate
      ? (toOptionValue(defaultCandidate.provider, defaultCandidate.model) ?? "")
      : "",
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
  const [applyCandidate, setApplyCandidate] =
    useState<ModelExperimentRating | null>(null);
  const [isApplyingSelection, setIsApplyingSelection] = useState(false);

  useEffect(() => {
    setSelectedCandidate(
      defaultCandidate
        ? (toOptionValue(defaultCandidate.provider, defaultCandidate.model) ??
            "")
        : "",
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
      setRatingMessage(
        "Saved. Your project's model is unchanged — promote the winner below to actually switch to it.",
      );
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
        selected_reason: `Chosen from experiment ${result.id} after manual preferred rating.`,
      });
      setRatingMessage(
        `Chosen AI model updated to ${ratingToApply.provider}/${ratingToApply.model}. Backend settings, search context, and experiment results were not changed.`,
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
    <details className="experiment-rating-panel">
      <summary className="experiment-rating-summary">
        <strong>Remember this for later</strong>
        <span>Optional — save a score so this project recommends the better model next time.</span>
      </summary>
      <p className="experiment-rating-note">
        This doesn't retrain the model (local open-source models have fixed
        weights). It nudges which model <em>this app</em> recommends for this
        project. The “Use this model” button above already switches your model —
        this is just memory for next time.
      </p>
      <div className="experiment-rating-form">
        <label>
          <span>Model</span>
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
          <span>This was the better answer</span>
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
      {ratingMessage ? (
        <p className="model-selection-message">{ratingMessage}</p>
      ) : null}
      {ratingError ? (
        <p className="model-selection-error">{ratingError}</p>
      ) : null}
      <SavedRatingsList
        ratings={ratings}
        isLoading={isLoadingRatings}
        applyCandidate={applyCandidate}
        isApplyingSelection={isApplyingSelection}
        onRequestApply={setApplyCandidate}
        onCancelApply={() => setApplyCandidate(null)}
        onConfirmApply={(ratingToApply) =>
          void applyPreferredRating(ratingToApply)
        }
      />
    </details>
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
    return (
      <p className="model-experiment-rating-muted">Loading saved ratings…</p>
    );
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
          Use as chosen AI model
        </button>
        <small>
          This only updates workspace AI model preference. It does not restart
          the backend, rebuild search context, rerun experiments, or change
          search model settings.
        </small>
      </div>
    );
  }

  return (
    <div className="preferred-apply-confirmation">
      <StatusBadge label="confirmation required" />
      <div>
        <strong>Use {label} as chosen AI model?</strong>
        <p>
          This saves the preferred rated model as the workspace chosen AI model.
          Backend settings stay unchanged, and Ask will use it per question when
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
    return `Search context required. Chosen search model ${selectedEmbedding} already matches the backend default, but search context status is ${dashboard.usage_plan.index_status}. Rebuild it to make workspace search reliable.`;
  }

  if (embeddingStatus.requires_reindex) {
    if (selectedEmbedding && embeddingStatus.matches_active_runtime) {
      return `Search context required. Chosen search model ${selectedEmbedding} matches the backend default, but the workspace does not have a usable index for search yet.`;
    }

    return selectedEmbedding
      ? `Chosen search model ${selectedEmbedding} differs from the current retrieval setup. Rebuild search context after you intentionally switch the search model or vector store.`
      : "Chosen search model requires rebuilding search context before workspace search can use it reliably.";
  }

  if (
    selectedEmbedding &&
    activeEmbedding &&
    !dashboard.usage_plan.can_search_with_selected_embedding &&
    embeddingStatus.matches_active_runtime
  ) {
    return `Chosen search model ${selectedEmbedding} matches backend default ${activeEmbedding}, but search is not ready. Rebuild search context for the current retrieval setup.`;
  }

  return null;
}

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function normalizeGuidedModelSection(
  section: GuidedModelSetupSection | null | undefined,
  modelType: "llm" | "embedding",
): GuidedModelSetupSection {
  if (section) {
    return {
      ...section,
      options: asArray(section.options),
    };
  }

  return {
    model_type: modelType,
    title: modelType === "llm" ? "AI answer model" : "Search context model",
    purpose:
      modelType === "llm"
        ? "Used to generate answers for this workspace."
        : "Used to build and search local project context.",
    recommendation_summary: "Model guidance is temporarily unavailable.",
    custom_model_hint: "You can still enter a custom Ollama model name.",
    options: [],
  };
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
  addOption(options, activeProvider, activeModel, "Backend default");

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
  return value.length > maxLength
    ? `${value.slice(0, maxLength).trimEnd()}…`
    : value;
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

function friendlyStatus(value: string) {
  return value
    .replace(/needs_attention/gi, "review")
    .replace(/setup needed/gi, "review")
    .replace(/runtime_mismatch/gi, "review")
    .replaceAll("_", " ");
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
