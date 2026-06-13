import { useEffect, useMemo, useState } from "react";

import {
  archiveAgentWorkflow,
  createAgentPlanningPreview,
  createAgentWorkflow,
  createLocalModelInstallDraft,
  deleteAgentWorkflow,
  createMCPConfigPreview,
  createMCPConnectionCheck,
  createWorkspaceMCPConfig,
  deleteWorkspaceMCPConfig,
  getAgentWorkflowExecutionReadiness,
  getFirstLaunchReadiness,
  getGuidedModelSetup,
  getLocalModelInstallGuide,
  getOllamaModelRecommendations,
  getLocalModelInstallStatus,
  getLocalModelDownloadWorkerPlan,
  getLocalModelDownloadExecutionCapability,
  startLocalModelDownloadJob,
  getLocalModelDownloadJob,
  listLocalModelDownloadJobs,
  cancelLocalModelDownloadJob,
  getWorkspaceMCPToolInventory,
  listWorkspaceMCPConfigs,
  previewWorkspaceMCPApproval,
  previewAgentWorkflowStepApproval,
  getAgentCapabilities,
  getMCPServerCatalog,
  listAgentWorkflows,
  getModelExperimentRatings,
  getWorkspaceModelExperiments,
  planModelExperiment,
  runModelExperiment,
  saveModelExperimentRating,
  updateAgentWorkflowStep,
  updateAgentWorkflowStepApproval,
  updateAgentWorkflowStepEvidence,
  updateWorkspaceMCPConfig,
  updateWorkspaceModelSelection,
  updateWorkspaceSkillProfile,
} from "../api/client";
import type {
  AgentCapability,
  AgentCapabilityCatalog,
  AgentPlanningPreview,
  AgentWorkflow,
  AgentWorkflowExecutionReadiness,
  AgentWorkflowStepApprovalPreview,
  MCPServerCatalog,
  MCPServerConfigPreview,
  MCPServerConnectionCheck,
  MCPApprovalPreview,
  MCPToolInventory,
  WorkspaceMCPServerConfig,
  FirstLaunchReadiness,
  GuidedModelSetupGuide,
  GuidedModelSetupSection,
  LocalAIActivationGuide,
  LocalModelInstallDraft,
  LocalModelInstallGuide,
  LocalModelStatusItem,
  OllamaModelRecommendationGuide,
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
  ModelPerformanceItem,
  UpdateWorkspaceModelSelectionRequest,
  WorkspaceModelRecommendation,
  WorkspaceModelsDashboard,
  WorkspaceJob,
} from "../api/types";
import { CopyButton } from "./CopyButton";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";
import {
  SKILL_PROFILE_TEMPLATES,
  applySkillProfileTemplate,
  normalizeSkillPreferences,
  toSkillProfileRequest,
  type SkillProfileTemplateId,
} from "./skillLibrary";

interface ModelsDetailProps {
  workspaceId: string;
  hasScan: boolean;
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

type ModelsSection = "setup" | "catalog" | "skills" | "compare" | "tools" | "advanced";

export function ModelsDetail({
  workspaceId,
  hasScan,
  dashboard,
  activationGuide,
  onSelectionUpdated,
  onStartIndexJob,
  onGetWorkspaceJob,
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
  const llmDiffersFromBackendDefault =
    Boolean(dashboard.selected_llm_provider && dashboard.selected_llm_model) &&
    !dashboard.selection_status.llm_status.matches_active_runtime;
  const needsContextBuild = dashboard.overall_status === "needs_context_index";
  const [contextBuildJob, setContextBuildJob] = useState<WorkspaceJob | null>(null);
  const [contextBuildError, setContextBuildError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<ModelsSection>("setup");

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

  return (
    <div className="models-detail models-detail-simple">
      <section className="panel models-native-hero models-native-hero-clean">
        <div>
          <p className="eyebrow">Models</p>
          <h2>Local AI for this workspace</h2>
          <p>Choose models, install missing ones, and keep the runtime state visible without digging through technical panels.</p>
        </div>
        <div className="models-native-hero-badges">
          <StatusBadge label={dashboard.usage_plan.can_use_selected_models_fully ? "Ready" : "Needs action"} />
        </div>
      </section>

      <nav className="models-section-nav" aria-label="Model settings sections">
        {([
          ["setup", "Overview"],
          ["catalog", "Choose & install"],
          ["skills", "Skills"],
          ["compare", "Compare"],
          ["tools", "MCP tools"],
          ["advanced", "Advanced"],
        ] as Array<[ModelsSection, string]>).map(([id, label]) => (
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

      {activeSection === "setup" ? (
        <>
          <section className="panel models-simple-panel models-simple-panel-clean">
            <PanelHeading
              eyebrow="Current setup"
              title="Models used by this workspace"
              status={dashboard.overall_status}
            />
            <div className="models-simple-grid">
              <SimpleModelCard
                label="AI answer model"
                provider={dashboard.selected_llm_provider ?? usage.active_llm_provider}
                model={dashboard.selected_llm_model ?? usage.active_llm_model}
                description="Used when you ask questions."
                status={usage.can_ask_with_selected_llm ? "Ready" : "Needs setup"}
              />
              <SimpleModelCard
                label="Search context model"
                provider={dashboard.selected_embedding_provider ?? usage.active_embedding_provider}
                model={dashboard.selected_embedding_model ?? usage.active_embedding_model}
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
          <ProductFitPanel />
        </>
      ) : null}

      {activeSection === "catalog" ? (
        <>
          <GuidedModelSetupPanel
            workspaceId={workspaceId}
            onApplySelection={applyGuidedSelection}
          />
          <LocalModelInstallPanel
            key={[
              workspaceId,
              dashboard.selected_llm_provider,
              dashboard.selected_llm_model,
              dashboard.selected_embedding_provider,
              dashboard.selected_embedding_model,
            ].join("-")}
            workspaceId={workspaceId}
          />
        </>
      ) : null}

      {activeSection === "skills" ? (
        <ModelSkillPresetPanel
          workspaceId={workspaceId}
          dashboard={dashboard}
          onSelectionUpdated={onSelectionUpdated}
        />
      ) : null}

      {activeSection === "compare" ? (
        <ModelExperimentPlanner
          workspaceId={workspaceId}
          llmOptions={llmOptions}
          selectedLlmProvider={dashboard.selected_llm_provider}
          selectedLlmModel={dashboard.selected_llm_model}
          activeLlmProvider={usage.active_llm_provider}
          activeLlmModel={usage.active_llm_model}
          onSelectionUpdated={onSelectionUpdated}
        />
      ) : null}

      {activeSection === "tools" ? (
        <MCPServerRegistryPanel workspaceId={workspaceId} />
      ) : null}

      {activeSection === "advanced" ? (
        <div className="models-advanced-stack">
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
          <details className="panel models-disclosure-panel activation-panel">
            <summary>
              <div>
                <p className="eyebrow">Manual commands</p>
                <h2>Copy-only setup notes</h2>
                <span>Only for troubleshooting when the built-in model manager is not enough.</span>
              </div>
            </summary>
            <p className="activation-safety-note">Commands are copied only. The frontend never executes them.</p>
            <div className="activation-step-list">
              {activationGuide.steps.slice(0, 4).map((step) => (
                <article className="activation-step" key={step.id}>
                  <div className="activation-step-heading">
                    <div>
                      <span>{formatLabel(step.category)}</span>
                      <strong>{step.title}</strong>
                    </div>
                    <StatusBadge label={friendlyStatus(step.status)} />
                  </div>
                  <p>{step.description}</p>
                  <CommandList primaryCommand={step.command} commands={step.commands ?? []} />
                </article>
              ))}
            </div>
          </details>
        </div>
      ) : null}
    </div>
  );
}


function ProductFitPanel() {
  return (
    <section className="panel product-fit-panel" aria-label="Original product goal">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Product goal</p>
          <h2>Local AI workspace, not a developer dashboard.</h2>
          <p className="panel-helper">
            The app should help you choose a project folder, build local context, pick a model that fits your Mac, and ask questions safely. Advanced tools stay available only when they are useful.
          </p>
        </div>
        <StatusBadge label="Local-first" />
      </div>
      <div className="product-fit-grid">
        <article><strong>1. Choose folder</strong><span>Project files stay on this Mac.</span></article>
        <article><strong>2. Build context</strong><span>Search uses local chunks and sources.</span></article>
        <article><strong>3. Pick model</strong><span>Recommended choices are sized for laptop use.</span></article>
        <article><strong>4. Approve tools</strong><span>MCP/edit/command actions are never hidden.</span></article>
      </div>
    </section>
  );
}

function ModelCatalogPanel({
  workspaceId,
  onSelectionUpdated,
}: {
  workspaceId: string;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const answerModels = [
    {
      name: "Qwen2.5 Coder 7B",
      model: "qwen2.5-coder:7b",
      fit: "Best coding default",
      memory: "Good on Apple Silicon with 16 GB+ RAM",
      use: "Code, scripts, DevOps config, CI/CD, Terraform and troubleshooting.",
      provider: "ollama",
      skill: "devops_review" as SkillProfileTemplateId,
    },
    {
      name: "Llama 3.2 3B",
      model: "llama3.2:3b",
      fit: "Fast and light",
      memory: "Good on 8–16 GB RAM",
      use: "Quick summaries, README questions, light project help.",
      provider: "ollama",
      skill: "documentation_review" as SkillProfileTemplateId,
    },
    {
      name: "Mistral 7B",
      model: "mistral:7b",
      fit: "Balanced general model",
      memory: "Good on 16 GB+ RAM",
      use: "General reasoning, docs, project explanations, mixed tasks.",
      provider: "ollama",
      skill: "code_review" as SkillProfileTemplateId,
    },
    {
      name: "Gemma 2 9B",
      model: "gemma2:9b",
      fit: "Stronger but heavier",
      memory: "Better on 24–32 GB+ RAM",
      use: "Deeper explanations and reviews when speed is less important.",
      provider: "ollama",
      skill: "manager_summary" as SkillProfileTemplateId,
    },
  ];
  const searchModels = [
    {
      name: "Nomic Embed Text",
      model: "nomic-embed-text",
      fit: "Recommended search model",
      memory: "Lightweight",
      use: "Builds searchable local project context for RAG.",
      provider: "ollama",
    },
    {
      name: "mxbai Embed Large",
      model: "mxbai-embed-large",
      fit: "Higher quality search",
      memory: "Heavier than nomic",
      use: "Use for larger docs/projects when retrieval quality matters more than speed.",
      provider: "ollama",
    },
  ];
  const [catalogMessage, setCatalogMessage] = useState<string | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogBusy, setCatalogBusy] = useState<string | null>(null);

  async function chooseAnswerModel(item: (typeof answerModels)[number]) {
    setCatalogBusy(item.model);
    setCatalogMessage(null);
    setCatalogError(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: item.provider,
        model: item.model,
        model_type: "llm",
        selected_reason: `Selected from local model catalog. Suggested skill: ${item.skill}.`,
      });
      const preset = readModelSkillPreset(item.model) ?? item.skill;
      const nextSkillPreferences = applySkillProfileTemplate(preset, undefined);
      await updateWorkspaceSkillProfile(workspaceId, toSkillProfileRequest(nextSkillPreferences));
      setCatalogMessage(`${item.name} selected. Applied ${friendlySkillTemplateName(preset)} guidance for this workspace.`);
      await onSelectionUpdated();
    } catch (error) {
      setCatalogError(errorMessage(error));
    } finally {
      setCatalogBusy(null);
    }
  }

  async function chooseSearchModel(item: (typeof searchModels)[number]) {
    setCatalogBusy(item.model);
    setCatalogMessage(null);
    setCatalogError(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: item.provider,
        model: item.model,
        model_type: "embedding",
        selected_reason: "Selected from local search model catalog.",
      });
      setCatalogMessage(`${item.name} selected. Rebuild context when you want Ask to use this search model.`);
      await onSelectionUpdated();
    } catch (error) {
      setCatalogError(errorMessage(error));
    } finally {
      setCatalogBusy(null);
    }
  }

  return (
    <section className="panel model-catalog-panel" aria-label="Local model catalog">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Model catalog</p>
          <h2>Pick a local model without guessing.</h2>
          <p className="panel-helper">
            Start with Qwen2.5 Coder for DevOps/code work and Nomic Embed Text for search. Avoid very large models unless your Mac has enough memory.
          </p>
        </div>
        <StatusBadge label="Local only" />
      </div>
      <div className="model-catalog-grid">
        <div>
          <h3>AI answer models</h3>
          <div className="model-catalog-list">
            {answerModels.map((item) => (
              <article key={item.model} className="model-catalog-card">
                <div>
                  <strong>{item.name}</strong>
                  <code>{item.model}</code>
                </div>
                <span>{item.fit}</span>
                <p>{item.use}</p>
                <small>{item.memory}</small>
                <button className="secondary-button model-catalog-choose" type="button" disabled={catalogBusy === item.model} onClick={() => void chooseAnswerModel(item)}>
                  {catalogBusy === item.model ? "Applying…" : "Use for this workspace"}
                </button>
              </article>
            ))}
          </div>
        </div>
        <div>
          <h3>Search context models</h3>
          <div className="model-catalog-list">
            {searchModels.map((item) => (
              <article key={item.model} className="model-catalog-card">
                <div>
                  <strong>{item.name}</strong>
                  <code>{item.model}</code>
                </div>
                <span>{item.fit}</span>
                <p>{item.use}</p>
                <small>{item.memory}</small>
                <button className="secondary-button model-catalog-choose" type="button" disabled={catalogBusy === item.model} onClick={() => void chooseSearchModel(item)}>
                  {catalogBusy === item.model ? "Applying…" : "Use for search"}
                </button>
              </article>
            ))}
          </div>
        </div>
      </div>
      {catalogMessage ? <p className="model-selection-message">{catalogMessage}</p> : null}
      {catalogError ? <p className="model-selection-error">{catalogError}</p> : null}
      <details className="model-catalog-details">
        <summary>What should I use on my Mac?</summary>
        <div className="model-catalog-advice-grid">
          <article><strong>8 GB RAM</strong><span>Llama 3.2 3B + Nomic Embed Text. Keep source snippets low.</span></article>
          <article><strong>16 GB RAM</strong><span>Qwen2.5 Coder 7B or Mistral 7B + Nomic Embed Text.</span></article>
          <article><strong>24–32 GB+ RAM</strong><span>Try Gemma 2 9B or larger 7B/8B models. Avoid 70B/120B locally.</span></article>
        </div>
      </details>
    </section>
  );
}

function WorkspacePermissionsPanel({ workspaceId }: { workspaceId: string }) {
  const [mcpMode, setMcpMode] = useState<"off" | "ask" | "allow">("ask");
  const [fileWriteMode, setFileWriteMode] = useState<"ask" | "off">("ask");
  const [commandMode, setCommandMode] = useState<"off" | "ask">("off");

  return (
    <section className="panel workspace-permissions-panel" aria-label="Agent and MCP permissions">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Tools and permissions</p>
          <h2>Agent and MCP access stay approval-based.</h2>
          <p className="panel-helper">
            MCP is still part of the product. MCP means external tools the assistant may ask to use, for example a filesystem helper, browser helper, Jira/Git helper, or a project-specific tool server. Nothing runs automatically.
          </p>
        </div>
        <StatusBadge label="Ask first" />
      </div>

      <div className="mcp-simple-flow">
        <article><span>1</span><strong>Choose a tool server</strong><p>Start with Filesystem/project tools. More servers can be added later.</p></article>
        <article><span>2</span><strong>Preview what it can do</strong><p>Show readable tool names before enabling anything.</p></article>
        <article><span>3</span><strong>Approve per action</strong><p>The assistant asks before reading, editing, or running a tool.</p></article>
      </div>

      <div className="permission-grid permission-grid-controls">
        <label>
          <strong>MCP tools</strong>
          <span>When the assistant needs a tool, should it ask?</span>
          <select value={mcpMode} onChange={(event) => setMcpMode(event.target.value as "off" | "ask" | "allow")}>
            <option value="off">Off for now</option>
            <option value="ask">Ask before each use</option>
            <option value="allow">Allow trusted read-only tools</option>
          </select>
        </label>
        <label>
          <strong>Edit or create files</strong>
          <span>Useful later for code/doc changes. Always preview before applying.</span>
          <select value={fileWriteMode} onChange={(event) => setFileWriteMode(event.target.value as "ask" | "off")}>
            <option value="ask">Ask and preview changes</option>
            <option value="off">Off</option>
          </select>
        </label>
        <label>
          <strong>Run commands</strong>
          <span>Keep disabled until a safe backend approval flow is ready.</span>
          <select value={commandMode} onChange={(event) => setCommandMode(event.target.value as "off" | "ask")}>
            <option value="off">Off</option>
            <option value="ask">Ask before every command</option>
          </select>
        </label>
      </div>

      <div className="mcp-simple-note">
        <strong>Recommended now:</strong>
        <span>MCP tools: {formatLabel(mcpMode)} · File edits: {formatLabel(fileWriteMode)} · Commands: {formatLabel(commandMode)}.</span>
        <p>These controls are prepared for the product flow. Frontend still does not execute shell commands.</p>
      </div>
    </section>
  );
}

function ModelSkillPresetPanel({
  workspaceId,
  dashboard,
  onSelectionUpdated,
}: {
  workspaceId: string;
  dashboard: WorkspaceModelsDashboard;
  onSelectionUpdated: () => Promise<void> | void;
}) {
  const currentModel = dashboard.selected_llm_model ?? dashboard.usage_plan.active_llm_model;
  const [selectedTemplate, setSelectedTemplate] = useState<SkillProfileTemplateId>(
    readModelSkillPreset(currentModel) ?? inferSkillTemplateForModel(currentModel),
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const template = SKILL_PROFILE_TEMPLATES.find((item) => item.id === selectedTemplate) ?? SKILL_PROFILE_TEMPLATES[0];

  async function savePreset() {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      writeModelSkillPreset(currentModel, selectedTemplate);
      const skillPreferences = applySkillProfileTemplate(selectedTemplate, undefined);
      await updateWorkspaceSkillProfile(workspaceId, toSkillProfileRequest(skillPreferences));
      setMessage(`${friendlySkillTemplateName(selectedTemplate)} saved for ${currentModel}. Ask will use this guidance in this workspace.`);
      await onSelectionUpdated();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel model-skill-preset-panel">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Skills</p>
          <h2>Pair each model with the work it should do.</h2>
          <p className="panel-helper">Example: Qwen for Developer, Llama for Documentation, Mistral for DevOps. Presets are remembered per model on this Mac.</p>
        </div>
        <StatusBadge label="Per model" />
      </div>
      <div className="model-skill-preset-body">
        <label>
          <span>Current answer model</span>
          <strong>{dashboard.selected_llm_provider ?? dashboard.usage_plan.active_llm_provider}/{currentModel}</strong>
        </label>
        <label>
          <span>Skill preset</span>
          <select value={selectedTemplate} onChange={(event) => setSelectedTemplate(event.target.value as SkillProfileTemplateId)}>
            {SKILL_PROFILE_TEMPLATES.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
        <article>
          <strong>{template.name}</strong>
          <p>{template.purpose}</p>
        </article>
        <button className="primary-button" type="button" disabled={saving} onClick={() => void savePreset()}>
          {saving ? "Saving…" : "Save skill for this model"}
        </button>
      </div>
      {message ? <p className="model-selection-message">{message}</p> : null}
      {error ? <p className="model-selection-error">{error}</p> : null}
    </section>
  );
}

const MODEL_SKILL_PRESET_STORAGE_KEY = "ai-private-workspace.model-skill-presets.v1";

function readModelSkillPreset(model: string | null | undefined): SkillProfileTemplateId | null {
  if (!model) return null;
  try {
    const raw = window.localStorage.getItem(MODEL_SKILL_PRESET_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) as Record<string, SkillProfileTemplateId> : {};
    return parsed[model] ?? null;
  } catch {
    return null;
  }
}

function writeModelSkillPreset(model: string | null | undefined, preset: SkillProfileTemplateId): void {
  if (!model) return;
  try {
    const raw = window.localStorage.getItem(MODEL_SKILL_PRESET_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) as Record<string, SkillProfileTemplateId> : {};
    parsed[model] = preset;
    window.localStorage.setItem(MODEL_SKILL_PRESET_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // Local presets are convenience state only.
  }
}

function inferSkillTemplateForModel(model: string | null | undefined): SkillProfileTemplateId {
  const normalized = (model ?? "").toLowerCase();
  if (normalized.includes("coder") || normalized.includes("qwen")) return "code_review";
  if (normalized.includes("llama")) return "documentation_review";
  if (normalized.includes("mistral")) return "devops_review";
  if (normalized.includes("gemma")) return "manager_summary";
  return "devops_review";
}

function friendlySkillTemplateName(id: SkillProfileTemplateId): string {
  return SKILL_PROFILE_TEMPLATES.find((item) => item.id === id)?.name ?? formatLabel(id);
}

function DesktopPackagingRealityPanel() {
  return (
    <div className="desktop-packaging-inner">
      <PanelHeading
        eyebrow="Product packaging"
        title="Desktop app target"
        status="planned"
      />
      <p className="panel-intro">
        This screen is not the real startup instruction. It documents the
        product target: a real macOS/Windows app where the user downloads a
        package, double-clicks it, and continues without cloning the repo or
        running scripts manually.
      </p>
      <div className="packaging-roadmap-grid">
        <article>
          <span>Current build</span>
          <strong>Developer-safe bridge</strong>
          <p>
            Backend, frontend, runtime checks, guided models, and local data
            safety are wired. Scripts still exist only because this is not the
            final packaged app yet.
          </p>
        </article>
        <article>
          <span>Packaging target</span>
          <strong>Double-click app</strong>
          <p>
            Package a desktop shell that supervises the local backend, opens the
            UI, stores runtime data locally, and recovers gracefully when
            something is not ready.
          </p>
        </article>
        <article>
          <span>Models</span>
          <strong>Explicit download manager</strong>
          <p>
            Model downloads should be a user-approved flow: choose model, see
            size/purpose, copy or approve pull, then verify availability. No
            hidden downloads.
          </p>
        </article>
        <article>
          <span>MCP</span>
          <strong>Registry before execution</strong>
          <p>
            MCP servers should be configured, explained, checked, and
            approval-gated before any real tool execution. Current work stays
            planning/manual by design.
          </p>
        </article>
      </div>
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
            {actionBusy === "recheck" ? "Checking…" : "Re-check runtime"}
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
            Re-check runtime
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
      <div className="runtime-next-action-panel runtime-next-action-panel-ready">
        <div className="runtime-next-action-copy">
          <StatusBadge label="Ready" />
          <div>
            <strong>Ready to ask questions.</strong>
            <p>
              AI model <code>{selectedLlm || activeLlm}</code> and search model <code>{selectedEmbedding || activeEmbedding}</code> are ready for this workspace.
            </p>
          </div>
        </div>
        <div className="runtime-next-action-buttons">
          <button className="secondary-action" type="button" onClick={() => void recheckRuntime()}>
            Re-check runtime
          </button>
        </div>
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
        </div>
      </div>
      <div className="runtime-next-action-buttons">
        <button className="secondary-action" type="button" onClick={() => void recheckRuntime()}>
          Re-check runtime
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

function ContextBuildCallout({
  job,
  error,
  onBuildContext,
}: {
  job: WorkspaceJob | null;
  error: string | null;
  onBuildContext: () => Promise<void> | void;
}) {
  const isRunning = job ? ["queued", "running"].includes(job.status) : false;
  const isDone = job?.status === "completed";

  return (
    <section className="panel context-build-callout-panel">
      <div className="context-build-callout-copy">
        <p className="eyebrow">Search context</p>
        <h2>Build context with the selected search model.</h2>
        <p>
          Your AI and search models are selected. Build the workspace context once
          so Ask can use local project files as sources.
        </p>
      </div>
      <div className="context-build-callout-action">
        {job ? (
          <StatusBadge
            label={isDone ? "Context built" : friendlyStatus(job.status)}
          />
        ) : null}
        <button
          className="primary-button"
          type="button"
          onClick={onBuildContext}
          disabled={isRunning || isDone}
        >
          {isRunning ? "Building context…" : isDone ? "Context built" : "Build context"}
        </button>
      </div>
      {job?.message ? (
        <p className="context-build-callout-note">{job.message}</p>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
    </section>
  );
}

function ModelUsageFlowPanel() {
  const steps = [
    {
      title: "Choose",
      text: "Pick the AI answer model and the search context model for this workspace.",
    },
    {
      title: "Download",
      text: "Use copy-only Ollama commands or the approved backend job flow when trusted execution is enabled.",
    },
    {
      title: "Verify",
      text: "Refresh installed models so the app can confirm what Ollama can actually run.",
    },
    {
      title: "Use",
      text: "Ask questions, rebuild context only when the search model changes, and keep every action explicit.",
    },
  ];

  return (
    <section className="panel model-usage-flow-panel">
      <PanelHeading eyebrow="Model flow" title="From model choice to local answers" />
      <p className="panel-intro">
        Models are handled as a clear user flow: choose what you need, download
        only when you approve it, verify locally, then use it for this workspace.
      </p>
      <div className="model-usage-flow-grid">
        {steps.map((step, index) => (
          <article key={step.title}>
            <span>{index + 1}</span>
            <strong>{step.title}</strong>
            <p>{step.text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}


function OllamaRecommendationPanel() {
  const [guide, setGuide] = useState<OllamaModelRecommendationGuide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getOllamaModelRecommendations()
      .then((result) => {
        if (!cancelled) {
          setGuide(result);
          setError(null);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(errorMessage(loadError));
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
  }, []);

  if (loading) {
    return (
      <section className="panel model-hardware-panel">
        <PanelHeading eyebrow="Ollama guide" title="Model recommendations" />
        <p className="panel-intro">Loading recommended local model profiles…</p>
      </section>
    );
  }

  if (error || !guide) {
    return (
      <section className="panel model-hardware-panel">
        <PanelHeading eyebrow="Ollama guide" title="Model recommendations" />
        <p className="model-selection-error">
          {error ?? "Could not load Ollama recommendations."}
        </p>
      </section>
    );
  }

  const defaultProfile =
    asArray(guide.profiles).find((profile) => profile.id === guide.default_profile_id) ??
    asArray(guide.profiles)[0];

  return (
    <section className="panel model-hardware-panel">
      <PanelHeading
        eyebrow="Ollama guide"
        title="Which models should I use?"
        status={defaultProfile ? "Balanced default" : "Guide"}
      />
      <p className="panel-intro">{guide.summary}</p>

      <div className="model-role-grid">
        {asArray(guide.roles).map((role) => (
          <article key={role.id}>
            <span>{role.title}</span>
            <strong>{role.default_model}</strong>
            <p>{role.purpose}</p>
            <small>{role.why_it_matters}</small>
          </article>
        ))}
      </div>

      <details className="models-disclosure-panel model-hardware-details" open>
        <summary>Recommended Mac profiles</summary>
        <div className="model-profile-grid">
          {asArray(guide.profiles).map((profile) => (
            <article
              key={profile.id}
              className={
                profile.id === guide.default_profile_id ? "is-recommended" : undefined
              }
            >
              <span>{profile.title}</span>
              <strong>{profile.recommended_llm}</strong>
              <p>{profile.summary}</p>
              <small>Search model: {profile.recommended_embedding}</small>
            </article>
          ))}
        </div>
      </details>

      <details className="models-disclosure-panel model-hardware-details">
        <summary>Safety and next steps</summary>
        <div className="model-safe-list">
          {asArray(guide.safety_notes).map((note) => (
            <p key={note}>{note}</p>
          ))}
          {asArray(guide.next_steps).map((step) => (
            <p key={step}>{step}</p>
          ))}
        </div>
      </details>
    </section>
  );
}

function LocalModelInstallPanel({ workspaceId }: { workspaceId: string }) {
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
      <p className="panel-intro model-install-summary">
        A calm place to check what is installed, download missing recommended
        models, and keep every action explicit.
      </p>

      <div
        className="model-manager-summary-grid"
        aria-label="Local model manager summary"
      >
        <article>
          <span>Installed</span>
          <strong>
            {installStatus?.runtime_reachable
              ? `${installedRecommendedCount}/${recommendedInstallItems.length} recommended`
              : "Ollama offline"}
          </strong>
          <p>
            {installStatus?.runtime_reachable
              ? installStatus.summary
              : "Start Ollama, then refresh this read-only check."}
          </p>
        </article>
        <article>
          <span>Downloads</span>
          <strong>
            {activeJobs.length > 0
              ? `${activeJobs.length} active`
              : "No active downloads"}
          </strong>
          <p>
            {jobList?.summary ??
              "Download history will appear after you start a backend job."}
          </p>
        </article>
        <article>
          <span>Safety</span>
          <strong>
            {executionCapability?.execution_enabled
              ? "Backend execution enabled"
              : "Manual by default"}
          </strong>
          <p>
            {executionCapability?.execution_enabled
              ? "Only allowlisted Ollama pulls can run."
              : "Commands are copy-only unless trusted local execution is enabled."}
          </p>
        </article>
      </div>

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

      <details className="model-manager-section" open={openDownloads}>
        <summary>
          <div>
            <span className="eyebrow">Download</span>
            <strong>
              {missingRecommended.length > 0
                ? "Recommended models need attention"
                : "Choose or download a model"}
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
                  <CopyButton
                    text={option.install_command}
                    label="Copy pull command"
                  />
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
                        : "Create download draft"}
                  </button>
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
              <span className="eyebrow">Download draft</span>
              <strong>{draft.display_name}</strong>
              <p>{draft.safety_summary}</p>
            </div>
            <div className="model-install-draft-actions">
              <CopyButton text={draft.command} label="Copy command" />
              <button
                className="secondary-button model-install-draft-button"
                type="button"
                disabled={
                  !executionCapability?.execution_enabled || runningDraft
                }
                onClick={() => void startDownloadJob()}
                title={executionCapability?.disabled_reason ?? undefined}
              >
                {runningDraft ? "Starting…" : "Run approved download"}
              </button>
            </div>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{draft.status}</dd>
              </div>
              <div>
                <dt>Execution</dt>
                <dd>
                  {draft.execution_supported ? "Supported" : "Manual only"}
                </dd>
              </div>
              <div>
                <dt>Safety</dt>
                <dd>{draft.command_proposal.policy_mode ?? "manual only"}</dd>
              </div>
            </dl>
          </div>
        ) : null}
      </details>

      <details
        className="model-manager-section"
        open={!installStatus?.runtime_reachable}
      >
        <summary>
          <div>
            <span className="eyebrow">Verify</span>
            <strong>Installed models</strong>
            <p>Read-only check against Ollama. No model changes happen here.</p>
          </div>
        </summary>
        {installStatus ? (
          <InstalledModelsStatusPanel
            status={installStatus}
            isRefreshing={refreshingInstallStatus}
            onRefresh={() => void refreshInstallStatus()}
          />
        ) : null}
      </details>

      {jobList ? (
        <ModelDownloadJobsPanel
          jobs={jobList}
          installedModels={installStatus?.items ?? []}
          isRefreshing={refreshingJobs}
          cancellingJobId={cancellingJobId}
          onRefresh={() => void refreshDownloadJobs()}
          onCancel={(jobId) => void requestCancelJob(jobId)}
        />
      ) : null}

      <details className="model-manager-section is-quiet">
        <summary>
          <div>
            <span className="eyebrow">Safety</span>
            <strong>How downloads are controlled</strong>
            <p>
              Open this when you need implementation details or manual install
              notes.
            </p>
          </div>
        </summary>
        {executionCapability ? (
          <ModelDownloadExecutionCapabilityPanel
            capability={executionCapability}
          />
        ) : null}
        {workerPlan ? <ModelDownloadWorkerPlanPanel plan={workerPlan} /> : null}
        <details className="model-install-details">
          <summary>Manual install notes</summary>
          <ol>
            {asArray(guide.next_steps).map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p>{asArray(guide.safety_notes).join(" ")}</p>
        </details>
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

function ModelDownloadJobsPanel({
  jobs,
  installedModels,
  isRefreshing,
  cancellingJobId,
  onRefresh,
  onCancel,
}: {
  jobs: LocalModelDownloadJobList;
  installedModels: LocalModelStatusItem[];
  isRefreshing: boolean;
  cancellingJobId: string | null;
  onRefresh: () => void;
  onCancel: (jobId: string) => void;
}) {
  const visibleJobs = asArray(jobs.jobs).slice(0, 5);
  const recentInstalled = asArray(installedModels)
    .filter((item) => item.status === "installed" && item.modified_at)
    .sort(
      (left, right) =>
        new Date(right.modified_at ?? 0).getTime() -
        new Date(left.modified_at ?? 0).getTime(),
    )
    .slice(0, 5);

  return (
    <details className="model-download-history" open={jobs.running_count > 0}>
      <summary>
        <div>
          <span className="eyebrow">Download history</span>
          <strong>
            {jobs.running_count > 0
              ? "Active model downloads"
              : "Recent model downloads"}
          </strong>
          <p>{jobs.summary}</p>
        </div>
      </summary>
      <div className="model-download-history-body">
        <div className="model-download-history-actions">
          <button
            className="secondary-button"
            type="button"
            disabled={isRefreshing}
            onClick={onRefresh}
          >
            {isRefreshing ? "Refreshing…" : "Refresh downloads"}
          </button>
        </div>
        {visibleJobs.length === 0 ? (
          <p className="panel-intro">
            No app-managed download jobs yet. Models installed directly with
            Ollama are detected separately below.
          </p>
        ) : (
          <div className="model-download-history-list">
            {visibleJobs.map((job) => (
              <article className="model-download-history-row" key={job.id}>
                <div>
                  <strong>{job.display_name}</strong>
                  <p>{getFriendlyDownloadJobStatus(job).message}</p>
                  {job.cancel_requested_at ? (
                    <small>{job.cancellation_summary}</small>
                  ) : null}
                </div>
                <div className="model-download-history-row-actions">
                  <StatusBadge
                    label={getFriendlyDownloadJobStatus(job).badge}
                  />
                  {job.cancellable &&
                  (job.status === "queued" || job.status === "running") ? (
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={cancellingJobId === job.id}
                      onClick={() => onCancel(job.id)}
                    >
                      {cancellingJobId === job.id ? "Requesting…" : "Cancel"}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
        {recentInstalled.length > 0 ? (
          <section className="recent-installed-models">
            <div className="recent-installed-models-heading">
              <div>
                <span className="eyebrow">Detected locally</span>
                <strong>Recent Ollama installs</strong>
                <p>
                  Includes models downloaded in Terminal or through this app.
                </p>
              </div>
              <StatusBadge label={`${recentInstalled.length} visible`} />
            </div>
            <div className="model-download-history-list">
              {recentInstalled.map((item) => (
                <article
                  className="model-download-history-row"
                  key={`recent-${item.provider}-${item.model}`}
                >
                  <div>
                    <strong>{item.display_name}</strong>
                    <p>
                      {item.provider}/{item.installed_as ?? item.model}
                    </p>
                    <small>
                      Installed or updated {formatModelTimestamp(item.modified_at)}
                    </small>
                  </div>
                  <div className="model-download-history-row-actions">
                    <StatusBadge label="Installed" />
                    <span className="model-install-type">{item.model_type}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </details>
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
}: {
  status: LocalModelInstallStatus;
  isRefreshing: boolean;
  onRefresh: () => void;
}) {
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
      <div
        className="installed-models-grid"
        aria-label="Installed local model status"
      >
        {asArray(status.items).map((item) => (
          <article
            className="installed-model-card"
            key={`${item.provider}-${item.model}`}
          >
            <div>
              <span className="model-install-type">{item.model_type}</span>
              <strong>{item.display_name}</strong>
              <p>{item.detail}</p>
            </div>
            <span className={`model-status-pill model-status-${item.status}`}>
              {item.status}
            </span>
            <small>
              {item.installed_as
                ? `Installed as ${item.installed_as}`
                : `${item.provider}/${item.model}`}
            </small>
            {item.status === "installed" ? (
              <dl className="installed-model-metadata">
                <div>
                  <dt>Size</dt>
                  <dd>{formatModelBytes(item.size_bytes)}</dd>
                </div>
                <div>
                  <dt>Parameters</dt>
                  <dd>{item.parameter_size ?? "Not reported"}</dd>
                </div>
                <div>
                  <dt>Quantization</dt>
                  <dd>{item.quantization_level ?? "Not reported"}</dd>
                </div>
                <div>
                  <dt>Installed / updated</dt>
                  <dd>{formatModelTimestamp(item.modified_at)}</dd>
                </div>
                <div>
                  <dt>Capabilities</dt>
                  <dd>{asArray(item.capabilities).join(", ") || "Not reported"}</dd>
                </div>
              </dl>
            ) : null}
          </article>
        ))}
      </div>
      <p className="installed-models-note">
        Read-only check: this only reads {status.runtime_url}/api/tags. It never
        pulls, removes, starts, or changes models.
      </p>
    </div>
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

function ModelDownloadExecutionCapabilityPanel({
  capability,
}: {
  capability: LocalModelDownloadExecutionCapability;
}) {
  return (
    <div className="model-download-execution-capability">
      <div>
        <span className="eyebrow">Backend execution</span>
        <strong>{capability.title}</strong>
        <p>{capability.safety_summary}</p>
        {capability.disabled_reason ? (
          <small>{capability.disabled_reason}</small>
        ) : null}
      </div>
      <StatusBadge
        label={capability.execution_enabled ? "Enabled" : "Disabled"}
      />
    </div>
  );
}

function ModelDownloadWorkerPlanPanel({
  plan,
}: {
  plan: LocalModelDownloadWorkerPlan;
}) {
  return (
    <details className="model-worker-plan">
      <summary>Backend download worker plan</summary>
      <div className="model-worker-plan-body">
        <div className="model-worker-plan-summary">
          <StatusBadge
            label={plan.worker_enabled ? "Enabled" : "Design only"}
          />
          <p>{plan.summary}</p>
        </div>
        <div
          className="model-worker-flow"
          aria-label="Future model download worker flow"
        >
          {asArray(plan.user_flow).slice(0, 4).map((step, index) => (
            <div key={step}>
              <span>{index + 1}</span>
              <p>{step}</p>
            </div>
          ))}
        </div>
        <div className="model-worker-guardrails">
          {asArray(plan.guardrails).slice(0, 3).map((guardrail) => (
            <article key={guardrail.id}>
              <strong>{guardrail.label}</strong>
              <p>{guardrail.detail}</p>
            </article>
          ))}
        </div>
      </div>
    </details>
  );
}

function FirstLaunchSetupPanel() {
  const [readiness, setReadiness] = useState<FirstLaunchReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getFirstLaunchReadiness()
      .then((result) => {
        if (!cancelled) {
          setReadiness(result);
          setError(null);
        }
      })
      .catch((readinessError) => {
        if (!cancelled) {
          setError(errorMessage(readinessError));
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
  }, []);

  if (loading) {
    return (
      <section className="panel first-launch-panel">
        <PanelHeading
          eyebrow="After launch"
          title="Workspace setup checklist"
        />
        <p className="panel-intro">Loading post-launch readiness checks…</p>
      </section>
    );
  }

  if (error || !readiness) {
    return (
      <section className="panel first-launch-panel">
        <PanelHeading
          eyebrow="After launch"
          title="Workspace setup checklist"
        />
        <p className="model-selection-error">
          {error ?? "Could not load first-launch readiness."}
        </p>
      </section>
    );
  }

  return (
    <section className="panel first-launch-panel">
      <PanelHeading
        eyebrow="Start here"
        title="Workspace setup"
        status={readiness.status}
      />
      <p className="panel-intro first-launch-summary">{readiness.summary}</p>
      <div
        className="first-launch-flow"
        aria-label="Recommended workspace setup flow"
      >
        {asArray(readiness.recommended_flow).slice(0, 6).map((step, index) => (
          <article className="first-launch-flow-step" key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </article>
        ))}
      </div>
      <details className="first-launch-details">
        <summary>Readiness checks</summary>
        <div className="first-launch-grid">
          {asArray(readiness.checklist).map((item) => (
            <article className="first-launch-card" key={item.id}>
              <div>
                <span>{item.title}</span>
                <StatusBadge label={item.status} />
              </div>
              <strong>{item.summary}</strong>
              <p>{item.detail}</p>
              {item.user_action ? <small>{item.user_action}</small> : null}
            </article>
          ))}
        </div>
      </details>
      <details className="first-launch-details is-secondary">
        <summary>Developer commands</summary>
        <div className="first-launch-command-list">
          {asArray(readiness.copy_commands).map((command) => (
            <div key={command.label}>
              <strong>{command.label}</strong>
              <p>{command.description}</p>
              <CopyButton text={command.command} label="Copy command" />
            </div>
          ))}
        </div>
      </details>
      <p className="first-launch-footnote">{readiness.safety_note}</p>
    </section>
  );
}

function GuidedModelSetupPanel({
  workspaceId,
  onApplySelection,
}: {
  workspaceId: string;
  onApplySelection: (
    modelType: "llm" | "embedding",
    provider: string,
    model: string,
  ) => Promise<void> | void;
}) {
  const [guide, setGuide] = useState<GuidedModelSetupGuide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [llmChoice, setLlmChoice] = useState("");
  const [embeddingChoice, setEmbeddingChoice] = useState("");
  const [customLlm, setCustomLlm] = useState("");
  const [customEmbedding, setCustomEmbedding] = useState("");
  const [saving, setSaving] = useState<"llm" | "embedding" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
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
  }, [workspaceId]);

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

      const draft = await createLocalModelInstallDraft({
        workspace_id: workspaceId,
        provider,
        model,
        model_type: modelType,
      });
      const capability = await getLocalModelDownloadExecutionCapability();
      if (capability.execution_enabled) {
        const job = await startLocalModelDownloadJob(draft.command_proposal.id);
        setMessage(
          `${provider}/${model} is selected and download ${job.status}. Recent model downloads will keep the result after restart.`,
        );
      } else {
        setMessage(
          `${provider}/${model} is selected but not installed. A safe download draft is ready in the model manager below.`,
        );
      }
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(null);
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
          onChange={setEmbeddingChoice}
          onCustomChange={setCustomEmbedding}
          onSave={() => void saveGuidedSelection("embedding")}
        />
      </div>
      <div className="guided-model-note-grid">
        <GuidedModelNotes
          title="Packaging ready"
          notes={asArray(guide.packaging_notes)}
        />
        <GuidedModelNotes title="Safety" notes={asArray(guide.safety_notes)} />
      </div>
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
  onChange,
  onCustomChange,
  onSave,
}: {
  section: GuidedModelSetupSection;
  value: string;
  customValue: string;
  disabled: boolean;
  isSaving: boolean;
  onChange: (value: string) => void;
  onCustomChange: (value: string) => void;
  onSave: () => void;
}) {
  const isCustom = parseSetupChoiceValue(value)?.model === "__custom__";
  return (
    <article className="guided-model-card">
      <div className="guided-model-card-heading">
        <div>
          <span>{section.model_type}</span>
          <strong>{section.title}</strong>
        </div>
        <StatusBadge label="recommended defaults" />
      </div>
      <p>{section.purpose}</p>
      <small>{section.recommendation_summary}</small>
      <label>
        <span>Choose model</span>
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {asArray(section.options).map((option) => (
            <option
              key={`${option.provider}/${option.model}`}
              value={toSetupChoiceValue(option.provider, option.model)}
            >
              {option.recommendation_label}: {option.display_name} (
              {option.provider}/{option.model})
            </option>
          ))}
          <option value="ollama||__custom__">Custom Ollama model…</option>
        </select>
      </label>
      {isCustom ? (
        <label>
          <span>Custom model name</span>
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
      ) : null}
      <p className="guided-model-custom-hint">{section.custom_model_hint}</p>
      <button
        className="model-selection-save-button"
        type="button"
        disabled={disabled}
        onClick={onSave}
      >
        {isSaving
          ? "Preparing…"
          : isCustom
            ? `Use & install ${section.title}`
            : `Use this ${section.title}`}
      </button>
    </article>
  );
}

function GuidedModelNotes({
  title,
  notes,
}: {
  title: string;
  notes: string[];
}) {
  return (
    <div className="guided-model-notes">
      <strong>{title}</strong>
      {asArray(notes).map((note) => (
        <span key={note}>{note}</span>
      ))}
    </div>
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

function getModelWorkspaceStatusLabel(dashboard: WorkspaceModelsDashboard): string {
  if (dashboard.usage_plan.can_use_selected_models_fully) {
    return "Ready";
  }
  if (dashboard.embedding_indexing_plan.plan_status === "needs_index") {
    return "Needs context build";
  }
  if (dashboard.embedding_indexing_plan.plan_status === "runtime_mismatch") {
    return "Needs runtime review";
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
  const displayModel = model
    ? `${provider ?? "unknown"}/${model}`
    : "Not selected";

  return (
    <article className="simple-model-card">
      <div>
        <span>{label}</span>
        <strong>{displayModel}</strong>
      </div>
      <p>{description}</p>
      <StatusBadge label={status} />
    </article>
  );
}

function ModelsWorkflowSteps({
  canAsk,
  canSearch,
}: {
  canAsk: boolean;
  canSearch: boolean;
}) {
  const steps = [
    {
      title: "Ready check",
      description: "Confirm answers and search are available.",
      status: canAsk && canSearch ? "ready" : "review",
    },
    {
      title: "Model choices",
      description: "Optional: change models only when needed.",
      status: canAsk ? "ready" : "review",
    },
    {
      title: "Optional comparison",
      description: "Try later if you want to improve answers.",
      status: "advisory",
    },
    {
      title: "Technical setup",
      description: "Copy setup commands only when needed.",
      status: canSearch ? "ready" : "review",
    },
  ];

  return (
    <section className="models-workflow-panel">
      {steps.map((step, index) => (
        <article key={step.title}>
          <span>{index + 1}</span>
          <div>
            <strong>{step.title}</strong>
            <p>{step.description}</p>
          </div>
          {step.status !== "ready" ? <StatusBadge label={step.status} /> : null}
        </article>
      ))}
    </section>
  );
}

function AgentMCPReadinessOverview() {
  return (
    <section className="panel agent-mcp-overview-panel">
      <div className="agent-mcp-hero">
        <div>
          <p className="eyebrow">Safe automation</p>
          <h2>Agent plans first. Tools come later.</h2>
          <p>
            This area is the bridge from a local AI assistant to a safe
            agent-style workflow: plan the task, choose visible tools, approve
            risky steps, then verify the result. It is intentionally calm and
            non-automatic.
          </p>
        </div>
        <StatusBadge label="planning only" />
      </div>
      <div className="agent-mcp-path">
        <span>1. Describe the goal</span>
        <span>2. Preview the plan</span>
        <span>3. Review MCP tools</span>
        <span>4. Approve & verify manually</span>
      </div>
      <div className="agent-mcp-safety-row">
        <span>No browser shell</span>
        <span>No auto MCP start</span>
        <span>No file edits without future sandbox gates</span>
      </div>
    </section>
  );
}

function AgentModeReadinessPanel({
  workspaceId,
  selectedProvider,
  selectedModel,
}: {
  workspaceId: string;
  selectedProvider: string;
  selectedModel: string;
}) {
  const [catalog, setCatalog] = useState<AgentCapabilityCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [goal, setGoal] = useState(
    "Review the project, identify risky deployment areas, propose checks, then re-check the result before continuing.",
  );
  const [preview, setPreview] = useState<AgentPlanningPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [workflows, setWorkflows] = useState<AgentWorkflow[]>([]);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [isSavingWorkflow, setIsSavingWorkflow] = useState(false);
  const [stepApprovalPreview, setStepApprovalPreview] =
    useState<AgentWorkflowStepApprovalPreview | null>(null);
  const [executionReadiness, setExecutionReadiness] =
    useState<AgentWorkflowExecutionReadiness | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAgentCapabilities()
      .then((result) => {
        if (!cancelled) {
          setCatalog(result);
          setCatalogError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setCatalogError(errorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void loadAgentWorkflows();
  }, [workspaceId]);

  async function loadAgentWorkflows() {
    setWorkflowError(null);
    try {
      const result = await listAgentWorkflows(workspaceId);
      setWorkflows(result.items);
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  const selectedCapability = useMemo(
    () =>
      catalog?.models.find(
        (model) =>
          model.provider === selectedProvider && model.model === selectedModel,
      ) ?? null,
    [catalog?.models, selectedModel, selectedProvider],
  );

  const recommendedModels =
    catalog?.models.filter(
      (model) =>
        model.model_type === "llm" &&
        ["agent_ready", "planning_ready"].includes(model.readiness),
    ) ?? [];

  async function handlePreviewPlan() {
    setIsPlanning(true);
    setPreviewError(null);
    try {
      const result = await createAgentPlanningPreview({
        goal,
        provider: selectedProvider,
        model: selectedModel,
      });
      setPreview(result);
    } catch (error) {
      setPreviewError(errorMessage(error));
    } finally {
      setIsPlanning(false);
    }
  }

  async function handleSaveWorkflowDraft() {
    setIsSavingWorkflow(true);
    setWorkflowError(null);
    try {
      const saved = await createAgentWorkflow(workspaceId, {
        goal,
        provider: selectedProvider,
        model: selectedModel,
      });
      setWorkflows((current) => [
        saved,
        ...current.filter((item) => item.id !== saved.id),
      ]);
    } catch (error) {
      setWorkflowError(errorMessage(error));
    } finally {
      setIsSavingWorkflow(false);
    }
  }

  async function handleExecutionReadiness(workflow: AgentWorkflow) {
    setWorkflowError(null);
    try {
      const result = await getAgentWorkflowExecutionReadiness(
        workspaceId,
        workflow.id,
      );
      setExecutionReadiness(result);
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  async function handleStepEvidence(
    workflow: AgentWorkflow,
    stepId: string,
    evidenceStatus: "provided" | "verified" | "needs_review",
  ) {
    setWorkflowError(null);
    try {
      const updated = await updateAgentWorkflowStepEvidence(
        workspaceId,
        workflow.id,
        stepId,
        {
          evidence_status: evidenceStatus,
          evidence_summary:
            evidenceStatus === "verified"
              ? "Manual evidence was reviewed and marked as verified."
              : "Manual evidence should be checked outside the browser UI.",
          evidence_sources: [],
        },
      );
      setWorkflows((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  async function handleStepStatus(
    workflow: AgentWorkflow,
    stepId: string,
    status: "todo" | "in_progress" | "done" | "skipped" | "needs_review",
  ) {
    setWorkflowError(null);
    try {
      const updated = await updateAgentWorkflowStep(
        workspaceId,
        workflow.id,
        stepId,
        { status },
      );
      setWorkflows((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  async function handleApprovalPreview(
    workflow: AgentWorkflow,
    stepId: string,
  ) {
    setWorkflowError(null);
    try {
      const result = await previewAgentWorkflowStepApproval(
        workspaceId,
        workflow.id,
        stepId,
      );
      setStepApprovalPreview(result);
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  async function handleStepApproval(
    workflow: AgentWorkflow,
    stepId: string,
    approvalStatus: "approved" | "rejected" | "revoked",
  ) {
    setWorkflowError(null);
    try {
      const updated = await updateAgentWorkflowStepApproval(
        workspaceId,
        workflow.id,
        stepId,
        {
          approval_status: approvalStatus,
          approval_note:
            approvalStatus === "approved"
              ? "Approved for manual tracking. No automatic execution was performed."
              : "Marked by user in the manual approval gate.",
        },
      );
      setWorkflows((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  async function handleArchiveWorkflow(workflow: AgentWorkflow) {
    setWorkflowError(null);
    try {
      const updated = await archiveAgentWorkflow(
        workspaceId,
        workflow.id,
        true,
      );
      setWorkflows((current) =>
        current.filter((item) => item.id !== updated.id),
      );
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  async function handleDeleteWorkflow(workflow: AgentWorkflow) {
    setWorkflowError(null);
    try {
      await deleteAgentWorkflow(workspaceId, workflow.id);
      setWorkflows((current) =>
        current.filter((item) => item.id !== workflow.id),
      );
    } catch (error) {
      setWorkflowError(errorMessage(error));
    }
  }

  return (
    <section className="panel agent-mode-panel">
      <div className="panel-heading-row">
        <div>
          <p className="eyebrow">Agent planner</p>
          <h2>Create a safe work plan</h2>
          <p className="panel-intro">
            Turn a broad request into a reviewable checklist. The assistant can
            suggest steps and tool gates, but it does not execute commands or
            change project files from the browser.
          </p>
        </div>
        <StatusBadge label={selectedCapability?.readiness ?? "Checking"} />
      </div>

      {catalogError ? <p className="form-error">{catalogError}</p> : null}

      <details className="mcp-calm-section agent-calm-section">
        <summary>
          <div>
            <h3>Model readiness and safety rules</h3>
            <span>Open when you want to inspect model capability and guardrails.</span>
          </div>
        </summary>
      <div className="agent-readiness-grid">
        <div className="agent-readiness-card is-selected">
          <span className="eyebrow">Current AI model</span>
          <strong>
            {selectedProvider}/{selectedModel}
          </strong>
          <p>
            {selectedCapability?.recommended_use ??
              "Loading model capability metadata."}
          </p>
          <div className="agent-capability-flags">
            <StatusBadge
              label={
                selectedCapability?.planning_supported ? "Planning" : "Ask only"
              }
            />
            <StatusBadge
              label={
                selectedCapability?.tool_calling_supported
                  ? "Tool calling declared"
                  : "No declared tools"
              }
            />
            <StatusBadge
              label={
                selectedCapability?.json_mode_supported
                  ? "Structured output"
                  : "Free text"
              }
            />
          </div>
        </div>
        <div className="agent-readiness-card">
          <span className="eyebrow">Recommended local models</span>
          {recommendedModels.length > 0 ? (
            <div className="agent-model-list">
              {recommendedModels.slice(0, 4).map((model) => (
                <span key={`${model.provider}/${model.model}`}>
                  {model.provider}/{model.model} ·{" "}
                  {formatLabel(model.readiness)}
                </span>
              ))}
            </div>
          ) : (
            <p>No planning-ready local LLMs found in the catalog yet.</p>
          )}
        </div>
      </div>

      <div className="agent-execution-ladder">
        <div>
          <strong>1. Plan</strong>
          <span>LLM creates a step-by-step draft.</span>
        </div>
        <div>
          <strong>2. Approve</strong>
          <span>User reviews tool gates and risk.</span>
        </div>
        <div>
          <strong>3. Run manually</strong>
          <span>Commands stay outside the browser UI.</span>
        </div>
        <div>
          <strong>4. Verify</strong>
          <span>Paste evidence and mark step status.</span>
        </div>
      </div>

      <div className="agent-guardrail-strip">
        <strong>Guardrails</strong>
        <span>Plans are reviewable guidance only.</span>
        <span>Every risky action needs approval.</span>
        <span>Facts still need retrieved sources.</span>
      </div>

      </details>

      <div className="agent-planner-card">
        <label>
          Try a multi-step agent-style request
          <textarea
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            rows={3}
          />
        </label>
        <button
          type="button"
          onClick={handlePreviewPlan}
          disabled={isPlanning || goal.trim().length < 3}
        >
          {isPlanning ? "Preparing…" : "Preview safe plan"}
        </button>
        {previewError ? <p className="form-error">{previewError}</p> : null}
      </div>

      {preview ? (
        <div className="agent-plan-preview">
          <div className="panel-heading-row compact">
            <div>
              <p className="eyebrow">Planning preview</p>
              <h3>{formatLabel(preview.agent_mode)}</h3>
            </div>
            <StatusBadge label={preview.readiness} />
          </div>
          <ol className="agent-plan-steps">
            {preview.steps.map((step) => (
              <li key={step.order}>
                <strong>{step.title}</strong>
                <p>{step.description}</p>
                <span>
                  {step.requires_user_confirmation
                    ? "Requires confirmation"
                    : "Read-only"}{" "}
                  · {formatLabel(step.allowed_execution)}
                </span>
              </li>
            ))}
          </ol>
          <div className="agent-plan-actions">
            <button
              type="button"
              onClick={handleSaveWorkflowDraft}
              disabled={isSavingWorkflow}
            >
              {isSavingWorkflow ? "Saving…" : "Save as manual workflow"}
            </button>
            <span>
              Saved workflows add approval gates and step tracking. Nothing runs
              automatically.
            </span>
          </div>
          <p className="muted-text">{preview.safety_note}</p>
        </div>
      ) : null}

      <details className="mcp-calm-section agent-workflow-history" open={workflows.length > 0}>
        <summary>
          <div>
            <h3>Saved manual workflows</h3>
            <span>Track approved plans only when you need them.</span>
          </div>
        </summary>
        <div className="panel-heading-row compact">
          <div>
            <p className="eyebrow">Manual workflow drafts</p>
            <h3>Approval-gated agent plans</h3>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void loadAgentWorkflows()}
          >
            Refresh
          </button>
        </div>
        {workflowError ? <p className="form-error">{workflowError}</p> : null}
        {workflows.length === 0 ? (
          <p className="muted-text">
            No saved agent workflow drafts yet. Preview a plan, then save it for
            approval-gated tracking.
          </p>
        ) : (
          <div className="agent-workflow-list">
            {workflows.map((workflow) => (
              <article key={workflow.id} className="agent-workflow-card">
                <div className="agent-workflow-header">
                  <div>
                    <span className="eyebrow">
                      {formatLabel(workflow.status)} ·{" "}
                      {workflow.progress_percent}% ·{" "}
                      {formatLabel(workflow.approval_readiness)}
                    </span>
                    <h4>{workflow.title}</h4>
                    <p>
                      {workflow.provider}/{workflow.model} · approvals{" "}
                      {workflow.approved_steps_count}/
                      {workflow.approval_required_steps_count}
                    </p>
                  </div>
                  <div className="agent-workflow-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => void handleExecutionReadiness(workflow)}
                    >
                      Readiness
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => void handleArchiveWorkflow(workflow)}
                    >
                      Archive
                    </button>
                    <button
                      type="button"
                      className="danger-button"
                      onClick={() => void handleDeleteWorkflow(workflow)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="agent-workflow-progress">
                  <span style={{ width: `${workflow.progress_percent}%` }} />
                </div>
                <ol className="agent-workflow-steps">
                  {workflow.steps.map((step) => {
                    const blockedByApproval =
                      step.requires_user_confirmation &&
                      step.approval_status !== "approved";
                    return (
                      <li key={step.id}>
                        <div>
                          <strong>{step.title}</strong>
                          <p>{step.description}</p>
                          <span>
                            {formatLabel(step.status)} · approval{" "}
                            {formatLabel(step.approval_status)} ·{" "}
                            {step.proposed_tool ?? "manual checkpoint"} ·{" "}
                            {formatLabel(step.tool_risk)}
                          </span>
                          {step.execution_hint ? (
                            <small>{step.execution_hint}</small>
                          ) : null}
                          <small>
                            Evidence: {formatLabel(step.evidence_status)}
                            {step.evidence_summary
                              ? ` · ${step.evidence_summary}`
                              : ""}
                          </small>
                        </div>
                        <div className="agent-step-actions">
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              void handleApprovalPreview(workflow, step.id)
                            }
                          >
                            Gate
                          </button>
                          {step.requires_user_confirmation ? (
                            <>
                              <button
                                type="button"
                                onClick={() =>
                                  void handleStepApproval(
                                    workflow,
                                    step.id,
                                    "approved",
                                  )
                                }
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() =>
                                  void handleStepApproval(
                                    workflow,
                                    step.id,
                                    "rejected",
                                  )
                                }
                              >
                                Reject
                              </button>
                            </>
                          ) : null}
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              void handleStepEvidence(
                                workflow,
                                step.id,
                                "provided",
                              )
                            }
                          >
                            Evidence
                          </button>
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              void handleStepEvidence(
                                workflow,
                                step.id,
                                "verified",
                              )
                            }
                          >
                            Verified
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void handleStepStatus(workflow, step.id, "done")
                            }
                            disabled={blockedByApproval}
                          >
                            Done
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void handleStepStatus(
                                workflow,
                                step.id,
                                "needs_review",
                              )
                            }
                          >
                            Review
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              void handleStepStatus(
                                workflow,
                                step.id,
                                "skipped",
                              )
                            }
                          >
                            Skip
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <p className="muted-text">{workflow.safety_note}</p>
              </article>
            ))}
          </div>
        )}
      </details>

      {executionReadiness ? (
        <div className="agent-execution-readiness-card">
          <div className="panel-heading-row compact">
            <div>
              <p className="eyebrow">Execution readiness</p>
              <h3>{formatLabel(executionReadiness.status)}</h3>
            </div>
            <StatusBadge
              label={`${executionReadiness.ready_steps_count}/${executionReadiness.steps.length} ready`}
            />
          </div>
          <div className="agent-readiness-summary-grid">
            <span>
              Approved tools:{" "}
              <strong>{executionReadiness.approved_tools_count}</strong>
            </span>
            <span>
              Risky tools:{" "}
              <strong>{executionReadiness.risky_tools_count}</strong>
            </span>
            <span>
              Blocked steps:{" "}
              <strong>{executionReadiness.blocked_steps_count}</strong>
            </span>
          </div>
          <ol className="agent-readiness-steps">
            {executionReadiness.steps.map((step) => (
              <li key={step.step_id}>
                <div>
                  <strong>{step.title}</strong>
                  <span>
                    {step.proposed_tool ?? "manual checkpoint"} ·{" "}
                    {formatLabel(step.tool_status)} · evidence{" "}
                    {formatLabel(step.evidence_status)}
                  </span>
                  <small>{step.next_action}</small>
                </div>
                {step.blockers.length > 0 ? (
                  <ul>
                    {step.blockers.map((blocker) => (
                      <li key={blocker}>{blocker}</li>
                    ))}
                  </ul>
                ) : (
                  <StatusBadge label="Ready" />
                )}
              </li>
            ))}
          </ol>
          <p className="muted-text">{executionReadiness.safety_note}</p>
        </div>
      ) : null}

      {stepApprovalPreview ? (
        <div className="agent-approval-preview-card">
          <div className="panel-heading-row compact">
            <div>
              <p className="eyebrow">Approval gate preview</p>
              <h3>{stepApprovalPreview.title}</h3>
            </div>
            <StatusBadge label={stepApprovalPreview.tool_risk} />
          </div>
          <p>
            <strong>Proposed tool:</strong>{" "}
            {stepApprovalPreview.proposed_tool ?? "Manual checkpoint"}
          </p>
          <p>
            <strong>Execution:</strong> {stepApprovalPreview.execution_hint}
          </p>
          <p>
            <strong>Evidence:</strong> {stepApprovalPreview.evidence_hint}
          </p>
          <div className="agent-approval-grid">
            <div>
              <strong>Approval checklist</strong>
              <ul>
                {stepApprovalPreview.approval_checklist.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <strong>Blocked actions</strong>
              <ul>
                {stepApprovalPreview.blocked_actions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
          <p className="muted-text">{stepApprovalPreview.safety_note}</p>
        </div>
      ) : null}
    </section>
  );
}

function MCPServerRegistryPanel({ workspaceId }: { workspaceId: string }) {
  const [catalog, setCatalog] = useState<MCPServerCatalog | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState(
    "filesystem-readonly",
  );
  const [projectPath, setProjectPath] = useState("");
  const [preview, setPreview] = useState<MCPServerConfigPreview | null>(null);
  const [check, setCheck] = useState<MCPServerConnectionCheck | null>(null);
  const [savedConfigs, setSavedConfigs] = useState<WorkspaceMCPServerConfig[]>(
    [],
  );
  const [inventory, setInventory] = useState<MCPToolInventory | null>(null);
  const [approvalPreview, setApprovalPreview] =
    useState<MCPApprovalPreview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      getMCPServerCatalog(),
      listWorkspaceMCPConfigs(workspaceId),
      getWorkspaceMCPToolInventory(workspaceId),
    ])
      .then(([catalogResult, configResult, inventoryResult]) => {
        setCatalog(catalogResult);
        setSavedConfigs(configResult.items);
        setInventory(inventoryResult);
        if (catalogResult.templates.length > 0) {
          setSelectedTemplateId(
            (current) => current || catalogResult.templates[0].id,
          );
        }
      })
      .catch((loadError) => setError(errorMessage(loadError)))
      .finally(() => setIsLoading(false));
  }, [workspaceId]);

  const selectedTemplate = useMemo(
    () =>
      catalog?.templates.find(
        (template) => template.id === selectedTemplateId,
      ) ?? null,
    [catalog, selectedTemplateId],
  );

  const hasSavedConfigs = savedConfigs.length > 0;
  const hasApprovedTools = Boolean(inventory?.approved_tools_count);

  async function refreshWorkspaceMCPState() {
    const [configResult, inventoryResult] = await Promise.all([
      listWorkspaceMCPConfigs(workspaceId),
      getWorkspaceMCPToolInventory(workspaceId),
    ]);
    setSavedConfigs(configResult.items);
    setInventory(inventoryResult);
  }

  async function handlePreviewConfig() {
    setIsPreviewing(true);
    setError(null);
    setApprovalPreview(null);
    try {
      const result = await createMCPConfigPreview({
        template_id: selectedTemplateId,
        workspace_id: workspaceId,
        project_path: projectPath.trim() || null,
      });
      setPreview(result);
      const checkResult = await createMCPConnectionCheck({
        template_id: selectedTemplateId,
      });
      setCheck(checkResult);
    } catch (previewError) {
      setError(errorMessage(previewError));
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleSaveWorkspaceConfig() {
    setIsSavingConfig(true);
    setError(null);
    try {
      const created = await createWorkspaceMCPConfig(workspaceId, {
        template_id: selectedTemplateId,
        project_path: projectPath.trim() || null,
      });
      setPreview(null);
      setApprovalPreview(null);
      await refreshWorkspaceMCPState();
      const approval = await previewWorkspaceMCPApproval(
        workspaceId,
        created.id,
        { approved_tools: created.approved_tools },
      );
      setApprovalPreview(approval);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setIsSavingConfig(false);
    }
  }

  async function handleApproveReadOnly(config: WorkspaceMCPServerConfig) {
    setError(null);
    try {
      const readOnlyTools = config.available_tools.filter((tool) =>
        tool.toLowerCase().includes("read"),
      );
      const previewResult = await previewWorkspaceMCPApproval(
        workspaceId,
        config.id,
        { approved_tools: readOnlyTools },
      );
      await updateWorkspaceMCPConfig(workspaceId, config.id, {
        approved_tools: readOnlyTools,
        reviewed: true,
        enabled: false,
      });
      setApprovalPreview(previewResult);
      await refreshWorkspaceMCPState();
    } catch (approveError) {
      setError(errorMessage(approveError));
    }
  }

  async function handleDisableConfig(config: WorkspaceMCPServerConfig) {
    setError(null);
    try {
      await updateWorkspaceMCPConfig(workspaceId, config.id, {
        enabled: false,
      });
      await refreshWorkspaceMCPState();
    } catch (disableError) {
      setError(errorMessage(disableError));
    }
  }

  async function handleDeleteConfig(config: WorkspaceMCPServerConfig) {
    setError(null);
    try {
      await deleteWorkspaceMCPConfig(workspaceId, config.id);
      await refreshWorkspaceMCPState();
    } catch (deleteError) {
      setError(errorMessage(deleteError));
    }
  }

  return (
    <section className="panel mcp-registry-panel mcp-calm-panel">
      <div className="mcp-calm-hero">
        <div>
          <p className="eyebrow">MCP tools</p>
          <h2>Connect tools only when you need them.</h2>
          <p>
            MCP lets future agent plans see approved local tools. For now this
            screen is a safe setup area: review templates, save disabled
            configs, and approve the smallest read-only tool set.
          </p>
        </div>
        <StatusBadge label={inventory?.agent_readiness ?? "planning only"} />
      </div>

      {isLoading ? <p className="muted-text">Loading MCP setup…</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      <div className="mcp-calm-summary-grid">
        <MCPMetricCard
          label="Saved configs"
          value={String(inventory?.configs_count ?? 0)}
          detail="Disabled by default"
        />
        <MCPMetricCard
          label="Approved tools"
          value={String(inventory?.approved_tools_count ?? 0)}
          detail={hasApprovedTools ? "Visible to plans" : "None approved yet"}
        />
        <MCPMetricCard
          label="Safety mode"
          value="Manual"
          detail="No server auto-start"
        />
      </div>

      <div className="mcp-calm-flow">
        <span>1. Choose a template</span>
        <span>2. Preview config</span>
        <span>3. Save disabled</span>
        <span>4. Approve read-only tools</span>
      </div>

      {catalog ? (
        <details className="mcp-calm-section" open={!hasSavedConfigs}>
          <summary>
            <div>
              <p className="eyebrow">Setup</p>
              <h3>Prepare a workspace MCP config</h3>
              <span>Safe preview first. Nothing starts automatically.</span>
            </div>
          </summary>

          <div className="mcp-template-grid calm">
            <label>
              <span>Server template</span>
              <select
                value={selectedTemplateId}
                onChange={(event) => setSelectedTemplateId(event.target.value)}
              >
                {catalog.templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Project path or env value</span>
              <input
                value={projectPath}
                onChange={(event) => setProjectPath(event.target.value)}
                placeholder="Optional, for example /Users/me/project"
              />
            </label>
          </div>

          {selectedTemplate ? (
            <article className="mcp-template-card calm">
              <div>
                <p className="eyebrow">
                  {formatLabel(selectedTemplate.category)}
                </p>
                <h3>{selectedTemplate.name}</h3>
                <p>{selectedTemplate.description}</p>
              </div>
              <div className="mcp-template-badges">
                <StatusBadge label={selectedTemplate.risk_level} />
                <StatusBadge label={selectedTemplate.transport} />
                <StatusBadge label={selectedTemplate.default_scope} />
              </div>
              <div className="mcp-tools-list">
                {selectedTemplate.example_tools.slice(0, 8).map((tool) => (
                  <span key={tool}>{tool}</span>
                ))}
              </div>
            </article>
          ) : null}

          <div className="mcp-safety-note">
            <strong>Safe by default.</strong>
            <span>Configs are saved disabled.</span>
            <span>Read-only tools should be approved first.</span>
            <span>
              Write or shell tools stay blocked for future sandbox work.
            </span>
          </div>

          <div className="agent-plan-actions mcp-calm-actions">
            <button
              type="button"
              onClick={handlePreviewConfig}
              disabled={isPreviewing || !selectedTemplateId}
            >
              {isPreviewing ? "Preparing preview…" : "Preview config"}
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handleSaveWorkspaceConfig}
              disabled={isSavingConfig || !selectedTemplateId}
            >
              {isSavingConfig ? "Saving…" : "Save disabled config"}
            </button>
          </div>
        </details>
      ) : null}

      {preview ? (
        <details className="mcp-calm-section" open>
          <summary>
            <div>
              <p className="eyebrow">Preview</p>
              <h3>Generated config and manual check</h3>
              <span>Copy-only output. No MCP process is started.</span>
            </div>
          </summary>
          <div className="mcp-preview-grid calm">
            <article className="mcp-preview-card">
              <div className="panel-heading-row compact">
                <div>
                  <p className="eyebrow">Config preview</p>
                  <h3>{preview.name}</h3>
                </div>
                <StatusBadge
                  label={
                    preview.allowed_by_default
                      ? "enabled"
                      : "disabled by default"
                  }
                />
              </div>
              <pre className="copyable-code-block">
                {JSON.stringify(preview.config_json, null, 2)}
              </pre>
              <CopyButton
                text={JSON.stringify(preview.config_json, null, 2)}
                label="Copy config"
              />
            </article>
            <article className="mcp-preview-card">
              <p className="eyebrow">Manual check</p>
              <h3>
                {check?.status ? formatLabel(check.status) : "Review locally"}
              </h3>
              <ul>
                {(check?.checks ?? preview.test_plan)
                  .slice(0, 5)
                  .map((item) => (
                    <li key={item}>{item}</li>
                  ))}
              </ul>
              {check?.copy_commands.length ? (
                <div className="command-list compact">
                  {check.copy_commands.map((command) => (
                    <div className="command-card" key={command}>
                      <code>{command}</code>
                      <CopyButton text={command} label="Copy" />
                    </div>
                  ))}
                </div>
              ) : null}
              <p className="muted-text">
                {check?.safety_note ?? "No process is started by the UI."}
              </p>
            </article>
          </div>
        </details>
      ) : null}

      <details className="mcp-calm-section" open={hasSavedConfigs}>
        <summary>
          <div>
            <p className="eyebrow">Workspace configs</p>
            <h3>Approved tools visible to future plans</h3>
            <span>
              Keep this small. Approve only tools the agent should know about.
            </span>
          </div>
          <button
            type="button"
            className="secondary-button inline-summary-action"
            onClick={(event) => {
              event.preventDefault();
              void refreshWorkspaceMCPState();
            }}
          >
            Refresh
          </button>
        </summary>
        {savedConfigs.length === 0 ? (
          <p className="muted-text">
            No workspace MCP configs yet. Start with a read-only template, save
            it disabled, then approve only the tools you trust.
          </p>
        ) : (
          <div className="mcp-config-list calm">
            {savedConfigs.map((config) => (
              <article key={config.id} className="mcp-config-card calm">
                <div>
                  <p className="eyebrow">
                    {formatLabel(config.status)} ·{" "}
                    {formatLabel(config.risk_level)}
                  </p>
                  <h4>{config.name}</h4>
                  <p>
                    {config.approved_tools_count}/{config.available_tools_count}{" "}
                    tools approved · {config.enabled ? "Enabled" : "Disabled"}
                  </p>
                  <div className="mcp-tools-list">
                    {config.available_tools.slice(0, 12).map((tool) => (
                      <span
                        key={tool}
                        className={
                          config.approved_tools.includes(tool) ? "approved" : ""
                        }
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="agent-workflow-actions">
                  <button
                    type="button"
                    onClick={() => void handleApproveReadOnly(config)}
                  >
                    Approve read-only
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => void handleDisableConfig(config)}
                  >
                    Disable
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => void handleDeleteConfig(config)}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </details>

      {approvalPreview ? (
        <div className="mcp-safety-note approval">
          <strong>Approval preview</strong>
          <span>{formatLabel(approvalPreview.status)}</span>
          <span>{approvalPreview.approved_tools.length} approved</span>
          <span>{approvalPreview.denied_tools.length} denied</span>
          {approvalPreview.warnings.slice(0, 3).map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      <details className="mcp-calm-section">
        <summary>
          <div>
            <p className="eyebrow">Tool inventory</p>
            <h3>What future agent plans can see</h3>
            <span>{inventory?.safety_note ?? catalog?.safety_note}</span>
          </div>
        </summary>
        {inventory?.tools.length ? (
          <div className="mcp-tool-inventory calm">
            <div className="mcp-tools-list">
              {inventory.tools.slice(0, 16).map((tool) => (
                <span
                  key={`${tool.config_id}-${tool.tool}`}
                  className={tool.status === "approved" ? "approved" : ""}
                >
                  {tool.tool} · {formatLabel(tool.status)}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <p className="muted-text">
            No MCP tools are visible to agent plans yet.
          </p>
        )}
      </details>
    </section>
  );
}

function MCPMetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="mcp-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
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
  const [experimentHistory, setExperimentHistory] = useState<
    ModelExperimentRun[]
  >([]);
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
    <details className="panel model-experiment-planner-panel models-disclosure-panel">
      <summary>
        <div>
          <p className="eyebrow">Optional</p>
          <h2>Compare models</h2>
          <span>
            Try two local AI models on one question when you want to improve
            answer quality.
          </span>
        </div>
      </summary>
      <p className="panel-intro">
        Prepare a safe comparison before running a local model test. This does
        not change workspace models, restart the backend, or rebuild search
        context.
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
          className="model-selection-save-button"
          type="button"
          disabled={isPlanning || llmOptions.length < 2}
          onClick={() => void generatePlan()}
        >
          {isPlanning ? "Preparing comparison…" : "Prepare comparison"}
        </button>
      </div>
      <div className="model-selection-safety-note">
        <StatusBadge label="planning only" />
        <span>
          Planning is advisory. Run the comparison only after you explicitly
          confirm it below.
        </span>
      </div>
      {error ? <p className="model-selection-error">{error}</p> : null}
      {plan ? <ModelExperimentPlanResult plan={plan} /> : null}
      {plan ? (
        <div className="model-experiment-run-panel">
          <div className="model-experiment-run-heading">
            <StatusBadge label="local AI calls" />
            <div>
              <strong>Run local model comparison</strong>
              <p>
                This asks both selected local AI models through the backend. It
                may take time and can use CPU/RAM, but it does not execute shell
                commands, change workspace models, restart the backend, or
                rebuild search context.
              </p>
            </div>
          </div>
          <button
            className="model-selection-save-button"
            type="button"
            disabled={isRunning}
            onClick={() => void runComparisonExperiment()}
          >
            {isRunning ? "Running comparison…" : "Run model comparison"}
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
    </details>
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
  return (
    <article className="model-experiment-run-result">
      <div className="model-experiment-plan-summary">
        <StatusBadge label={result.status} />
        <StatusBadge
          label={`${result.shared_context_sources_count} shared sources`}
        />
        <strong>Comparison result</strong>
      </div>
      <div className="model-experiment-run-meta">
        <span>
          Comparison ID <code>{result.id}</code>
        </span>
        <span>Created {formatDateTime(result.created_at)}</span>
        {result.completed_at ? (
          <span>Completed {formatDateTime(result.completed_at)}</span>
        ) : null}
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
      <strong>Quick comparison hints</strong>
      <ul>
        <li>
          Fastest: {fastest.provider}/{fastest.model} (
          {fastest.latency_ms ?? "unknown"} ms)
        </li>
        <li>
          Fewest verification notes: {fewestWarnings.provider}/
          {fewestWarnings.model} ({fewestWarnings.quality_warnings_count})
        </li>
        <li>
          Most sources used: {mostSources.provider}/{mostSources.model} (
          {mostSources.sources_count})
        </li>
      </ul>
      <small>
        These are simple hints, not an automatic winner. Review answer quality
        and source grounding manually before changing the chosen AI model.
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
        "Experiment rating saved. Chosen model was not changed.",
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
    <div className="experiment-rating-panel">
      <div className="experiment-rating-heading">
        <StatusBadge label="manual rating" />
        <div>
          <strong>Rate this comparison</strong>
          <p>
            Save human feedback for model performance tracking. This does not
            change the chosen AI model or rerun the comparison.
          </p>
        </div>
      </div>
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
      setError("Choose a model before saving.");
      setMessage(null);
      return;
    }

    const payload: UpdateWorkspaceModelSelectionRequest = {
      provider: parsed.provider,
      model: parsed.model,
      model_type: modelType,
      selected_reason:
        modelType === "llm"
          ? "Chosen from the frontend Models tab."
          : "Chosen from the frontend Models tab for workspace retrieval.",
    };

    setSavingType(modelType);
    setError(null);
    setMessage(null);
    try {
      await updateWorkspaceModelSelection(workspaceId, payload);
      setMessage(
        `${modelType === "llm" ? "AI answer model" : "Search context model"} saved. Backend settings were not changed.`,
      );
      await onSelectionUpdated();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSavingType(null);
    }
  }

  return (
    <details className="panel model-selection-editor-panel models-disclosure-panel">
      <summary>
        <div>
          <p className="eyebrow">Optional settings</p>
          <h2>Change workspace models</h2>
          <span>
            Most users do not need this. Open it only to choose a different AI
            or search model.
          </span>
        </div>
      </summary>
      <div className="model-selection-editor-body">
        <p className="panel-intro">
          Saving only updates this workspace preference. It does not restart the
          backend, rebuild search context, or execute commands.
        </p>

        <div className="model-selection-grid">
          <ModelSelectionControl
            label="AI answer model"
            description="Used when you ask questions. Most users can keep the recommended model."
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
            label="Search context model"
            description="Used to build and search local project context. Change this only when you know the backend uses the same search model."
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
            Backend setup and search-context rebuild steps stay manual. Changing
            an AI model preference does not require rebuilding; changing the
            search model may require the guidance below.
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
      </div>
    </details>
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
        <strong>
          {hasScan ? "Rebuild search context" : "Scan and build search context"}
        </strong>
      </div>
      <p>{reason}</p>
      {!hasScan ? (
        <CommandGuidanceRow
          label="Step 1 · scan project"
          command={scanCommand}
        />
      ) : null}
      <CommandGuidanceRow
        label={
          hasScan ? "Rebuild search context" : "Step 2 · build search context"
        }
        command={indexCommand}
      />
      <small>
        The frontend does not run scan or indexing automatically. Copy and run
        these commands only when you intentionally want to rebuild workspace
        context. Changing an AI model does not require rebuilding.
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

function formatModelActionTitle(
  title: string | null | undefined,
): string | null {
  if (!title) {
    return null;
  }

  return title
    .replace(/Ask using selected LLM/gi, "Ask with chosen AI model")
    .replace(/selected LLM/gi, "chosen AI model")
    .replace(/LLM/gi, "AI model");
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
          Fit score <strong>{recommendation.final_score}</strong>
        </span>
        <span>
          Notes <strong>{recommendation.warnings.length}</strong>
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
          Fit score <strong>{item.score}</strong>
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
