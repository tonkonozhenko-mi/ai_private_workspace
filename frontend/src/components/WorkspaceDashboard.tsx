import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";
import { ModelsSummaryCard } from "./ModelsSummaryCard";
import { StatusBadge } from "./StatusBadge";
import type { StatusTone } from "./statusTone";

interface WorkspaceDashboardProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
  onOpenModels: () => void;
  onOpenCapabilities: () => void;
}

export function WorkspaceDashboard({
  dashboard,
  modelsSummary,
  onOpenAsk,
  onOpenModels,
  onOpenCapabilities,
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
          <span>{formatLabel(dashboard.assistant_mode)} mode</span>
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
          <span className="metric-label">Technologies found</span>
          <strong>{summary.detected_skills_count}</strong>
          <span>{summary.has_scan ? "Latest scan available" : "Project scan needed"}</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Context</span>
          <strong className="metric-word">{formatLabel(indexStatus.status)}</strong>
          <span>{indexStatus.chunks_count} context pieces</span>
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

      <WorkspaceOnboardingGuide
        dashboard={dashboard}
        modelsSummary={modelsSummary}
        onOpenAsk={onOpenAsk}
        onOpenModels={onOpenModels}
        onOpenCapabilities={onOpenCapabilities}
      />

      <ProductStatusSection
        dashboard={dashboard}
        modelsSummary={modelsSummary}
        onOpenAsk={onOpenAsk}
      />

      <div className="overview-grid">
        <ModelsSummaryCard summary={modelsSummary} compact />
        <section className="panel overview-next-action overview-secondary-action">
          <div>
            <p className="eyebrow">Next best step</p>
            <h2>Ask your first workspace question</h2>
            <p>
              Use the Ask tab to get a local answer grounded in this workspace
              context. Sources stay visible so you can verify important claims.
            </p>
          </div>
          <button className="overview-cta-button" type="button" onClick={onOpenAsk}>
            Go to Ask
          </button>
        </section>
      </div>
    </>
  );
}


function WorkspaceOnboardingGuide({
  dashboard,
  modelsSummary,
  onOpenAsk,
  onOpenModels,
  onOpenCapabilities,
}: {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
  onOpenModels: () => void;
  onOpenCapabilities: () => void;
}) {
  const summary = dashboard.summary;
  const hasScan = summary.has_scan;
  const indexReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
  const readyToAsk = hasScan && indexReady && localAIReady;

  const steps = [
    {
      title: "Scan project",
      description: hasScan
        ? `${summary.detected_skills_count} technologies were found.`
        : "Start by detecting project files, technologies, and setup signals.",
      status: hasScan ? "done" : "next",
    },
    {
      title: "Build search context",
      description: indexReady
        ? `${summary.index_status.chunks_count} context pieces are ready for search.`
        : "Create searchable local context before asking grounded questions.",
      status: indexReady ? "done" : hasScan ? "next" : "waiting",
    },
    {
      title: "Ask a question",
      description: readyToAsk
        ? "Ask is ready and will keep retrieved sources visible."
        : "Ask becomes useful after scan, context, and local AI are ready.",
      status: readyToAsk ? "next" : "waiting",
    },
    {
      title: "Compare models later",
      description: "Optional: compare local models only when you want to improve answer quality.",
      status: "optional",
    },
  ];

  const primaryAction = !hasScan || !indexReady
    ? { label: "Open Capabilities", onClick: onOpenCapabilities }
    : !localAIReady
      ? { label: "Review Models", onClick: onOpenModels }
      : { label: "Go to Ask", onClick: onOpenAsk };

  return (
    <section className="panel onboarding-guide-panel">
      <div className="onboarding-guide-heading">
        <div>
          <p className="eyebrow">Guided path</p>
          <h2>{readyToAsk ? "Ready to ask questions" : "Set up this workspace"}</h2>
          <p>
            Follow these steps to move from a local project folder to source-backed
            answers. The frontend keeps setup explicit and does not run shell commands.
          </p>
        </div>
        <button className="overview-cta-button" type="button" onClick={primaryAction.onClick}>
          {primaryAction.label}
        </button>
      </div>
      <div className="onboarding-steps-grid">
        {steps.map((step, index) => (
          <article className={`onboarding-step-card is-${step.status}`} key={step.title}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <p>{step.description}</p>
            </div>
            <StatusBadge label={step.status} />
          </article>
        ))}
      </div>
    </section>
  );
}

function ProductStatusSection({
  dashboard,
  modelsSummary,
  onOpenAsk,
}: {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
}) {
  const summary = dashboard.summary;
  const indexReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
  const experimentsSeen = dashboard.recent_events.some((event) =>
    event.event_type.toLowerCase().includes("experiment") ||
    event.title.toLowerCase().includes("model")
  );

  const statuses: Array<{ title: string; description: string; badge: string; tone: StatusTone }> = [
    {
      title: "Local AI",
      description: localAIReady
        ? "Chosen models are ready for workspace questions."
        : "Review model setup before relying on answers.",
      badge: localAIReady ? "ready" : modelsSummary.overall_status,
      tone: localAIReady ? "success" : "warning",
    },
    {
      title: "Workspace context",
      description: indexReady
        ? `${summary.index_status.chunks_count} indexed context pieces are available.`
        : "Scan and index the project before asking grounded questions.",
      badge: indexReady ? "indexed" : summary.index_status.status,
      tone: indexReady ? "success" : "warning",
    },
    {
      title: "Model learning",
      description: experimentsSeen
        ? "Experiment feedback is available for this workspace."
        : "Run comparisons to learn which local model works best.",
      badge: experimentsSeen ? "feedback ready" : "not started",
      tone: experimentsSeen ? "success" : "neutral",
    },
    {
      title: "Safety posture",
      description: "Frontend actions stay explicit and do not execute shell commands.",
      badge: "local only",
      tone: "info",
    },
  ];

  return (
    <section className="panel product-status-panel">
      <div className="product-status-heading">
        <div>
          <p className="eyebrow">Product status</p>
          <h2>Ready to work with this project</h2>
          <p>
            This workspace is prepared for local questions, source-backed answers,
            and model comparison. Technical setup stays manual and transparent.
          </p>
        </div>
        <StatusBadge
          label={localAIReady && indexReady ? "demo ready" : "needs attention"}
          tone={localAIReady && indexReady ? "success" : "warning"}
          size="md"
        />
      </div>

      <div className="product-status-grid">
        {statuses.map((item) => (
          <article className="product-status-card" key={item.title}>
            <div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </div>
            <StatusBadge label={item.badge} tone={item.tone} />
          </article>
        ))}
      </div>

      <div className="product-status-next product-status-cta">
        <div>
          <span>Recommended next</span>
          <strong>Ask your first question</strong>
          <p>
            Start with a project question. The answer stays local and includes
            retrieved sources for verification.
          </p>
        </div>
        <button className="overview-cta-button" type="button" onClick={onOpenAsk}>
          Go to Ask
        </button>
      </div>
    </section>
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
          <p className="eyebrow">AI setup</p>
          <h2>Local AI setup needs attention</h2>
        </div>
        <StatusBadge label={summary.overall_status} size="md" />
      </div>

      <div className="local-ai-runtime-comparison">
        <ModelComparisonRow
          label="AI model"
          selected={summary.selected_llm}
          active={summary.active_llm}
        />
        <ModelComparisonRow
          label="Search model"
          selected={summary.selected_embedding}
          active={summary.active_embedding}
        />
      </div>

      <div className="local-ai-setup-messages">
        {summary.can_ask_with_selected_llm ? (
          <p className="is-available">
            Chosen AI model can already be used for Ask.
          </p>
        ) : null}
        {!summary.can_search_with_selected_embedding ? (
          <p className="is-warning">
            Chosen search model is not active for search yet.
          </p>
        ) : null}
      </div>

      <div className="local-ai-setup-next">
        <div>
          <span>Recommended AI setup action</span>
          <strong>
            {summary.primary_next_action_title ?? "Review AI setup"}
          </strong>
        </div>
        <div className="local-ai-setup-navigation">
          <p>Open Models to review setup steps.</p>
          <button
            className="local-ai-models-button"
            type="button"
            onClick={onOpenModels}
          >
            Open Models
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
          <dt>Chosen</dt>
          <dd>{selected ?? "Not selected"}</dd>
        </div>
        <div>
          <dt>Backend default</dt>
          <dd>{active}</dd>
        </div>
      </dl>
    </div>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
