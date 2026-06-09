import { useState } from "react";

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
  onScanWorkspace: () => Promise<void>;
  onIndexWorkspace: () => Promise<void>;
}

export function WorkspaceDashboard({
  dashboard,
  modelsSummary,
  onOpenAsk,
  onOpenModels,
  onOpenCapabilities,
  onScanWorkspace,
  onIndexWorkspace,
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
        onScanWorkspace={onScanWorkspace}
        onIndexWorkspace={onIndexWorkspace}
      />

      <WorkspaceSkillsSection
        dashboard={dashboard}
        onOpenAsk={onOpenAsk}
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
  onScanWorkspace,
  onIndexWorkspace,
}: {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
  onOpenModels: () => void;
  onOpenCapabilities: () => void;
  onScanWorkspace: () => Promise<void>;
  onIndexWorkspace: () => Promise<void>;
}) {
  const summary = dashboard.summary;
  const hasScan = summary.has_scan;
  const indexReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
  const readyToAsk = hasScan && indexReady && localAIReady;
  const [setupAction, setSetupAction] = useState<"scan" | "index" | null>(null);
  const [setupMessage, setSetupMessage] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);

  async function runSetupAction(action: "scan" | "index") {
    setSetupAction(action);
    setSetupMessage(null);
    setSetupError(null);
    try {
      if (action === "scan") {
        await onScanWorkspace();
        setSetupMessage("Project scan finished. Review the detected technologies, then build search context.");
      } else {
        await onIndexWorkspace();
        setSetupMessage("Search context is ready. You can now ask source-backed questions.");
      }
    } catch (error) {
      setSetupError(
        error instanceof Error
          ? error.message
          : action === "scan"
            ? "Could not scan this project."
            : "Could not build search context.",
      );
    } finally {
      setSetupAction(null);
    }
  }

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

  const primaryAction = !hasScan
    ? { label: setupAction === "scan" ? "Scanning..." : "Scan project", onClick: () => void runSetupAction("scan"), disabled: setupAction !== null }
    : !indexReady
      ? { label: setupAction === "index" ? "Building..." : "Build search context", onClick: () => void runSetupAction("index"), disabled: setupAction !== null }
      : !localAIReady
        ? { label: "Review Models", onClick: onOpenModels, disabled: false }
        : { label: "Go to Ask", onClick: onOpenAsk, disabled: false };

  return (
    <section className="panel onboarding-guide-panel">
      <div className="onboarding-guide-heading">
        <div>
          <p className="eyebrow">Guided path</p>
          <h2>{readyToAsk ? "Ready to ask questions" : "Set up this workspace"}</h2>
          <p>
            Follow this path to turn a local project folder into source-backed answers.
          </p>
          <span className="onboarding-safety-note">Setup stays manual. The frontend never runs shell commands.</span>
        </div>
        <button
          className="overview-cta-button"
          type="button"
          disabled={primaryAction.disabled}
          onClick={primaryAction.onClick}
        >
          {primaryAction.label}
        </button>
      </div>

      {!readyToAsk ? (
        <div className="workspace-setup-actions" aria-label="Workspace setup actions">
          <div>
            <strong>{!hasScan ? "Start with a project scan" : !indexReady ? "Build searchable context" : "Review local AI setup"}</strong>
            <p>
              {!hasScan
                ? "This reads the local project through the backend and records detected technologies."
                : !indexReady
                  ? "This creates source-backed search context from the latest scan."
                  : "Open Models to confirm the chosen local AI models before asking questions."}
            </p>
          </div>
          <div className="workspace-setup-action-buttons">
            {!hasScan ? (
              <button
                className="primary-action"
                type="button"
                disabled={setupAction !== null}
                onClick={() => void runSetupAction("scan")}
              >
                {setupAction === "scan" ? "Scanning..." : "Scan project"}
              </button>
            ) : !indexReady ? (
              <button
                className="primary-action"
                type="button"
                disabled={setupAction !== null}
                onClick={() => void runSetupAction("index")}
              >
                {setupAction === "index" ? "Building..." : "Build search context"}
              </button>
            ) : (
              <button className="secondary-action" type="button" onClick={onOpenModels}>
                Review Models
              </button>
            )}
            <button className="secondary-action" type="button" onClick={onOpenCapabilities}>
              View capabilities
            </button>
          </div>
        </div>
      ) : null}

      {setupMessage ? <p className="settings-message success">{setupMessage}</p> : null}
      {setupError ? <p className="settings-message error">{setupError}</p> : null}
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


function WorkspaceSkillsSection({
  dashboard,
  onOpenAsk,
  onOpenCapabilities,
}: {
  dashboard: WorkspaceDashboardData;
  onOpenAsk: () => void;
  onOpenCapabilities: () => void;
}) {
  const summary = dashboard.summary;
  const skills = getWorkspaceSkillCards(dashboard.assistant_mode, summary.detected_skills_count, summary.has_scan);
  const suggestedFocus = getAssistantFocus(dashboard.assistant_mode);

  return (
    <section className="panel workspace-skills-panel">
      <div className="workspace-skills-heading">
        <div>
          <p className="eyebrow">Workspace skills</p>
          <h2>Use the right project lens</h2>
          <p>
            Skills help AI Private Workspace frame answers around the technologies and work style detected in this project.
          </p>
        </div>
        <StatusBadge
          label={summary.has_scan ? `${summary.detected_skills_count} found` : "scan first"}
          tone={summary.has_scan ? "success" : "warning"}
          size="md"
        />
      </div>

      <div className="assistant-focus-card">
        <div>
          <span>Current assistant focus</span>
          <strong>{suggestedFocus.title}</strong>
          <p>{suggestedFocus.description}</p>
        </div>
        <button className="secondary-action" type="button" onClick={onOpenAsk}>
          Ask with this focus
        </button>
      </div>

      <div className="skill-card-grid">
        {skills.map((skill) => (
          <article className="skill-card" key={skill.title}>
            <div className="skill-card-icon" aria-hidden="true">
              {skill.icon}
            </div>
            <div>
              <strong>{skill.title}</strong>
              <p>{skill.description}</p>
              <span>{skill.hint}</span>
            </div>
          </article>
        ))}
      </div>

      <div className="skill-library-note">
        <div>
          <strong>Skill library coming next</strong>
          <p>
            Start with presets like DevOps, Developer, Documentation, Incident Support, and Manager Summary. Later you will be able to customize them, for example by extending DevOps with Jenkins pipelines or company-specific deployment rules.
          </p>
        </div>
        <button className="secondary-action" type="button" onClick={onOpenCapabilities}>
          View capabilities
        </button>
      </div>
    </section>
  );
}

function getAssistantFocus(mode: string) {
  const focuses: Record<string, { title: string; description: string }> = {
    devops: {
      title: "DevOps and platform focus",
      description: "Answers prioritize infrastructure, CI/CD, runtime, cloud, containers, and operational setup.",
    },
    developer: {
      title: "Developer focus",
      description: "Answers prioritize application structure, implementation details, tests, and code navigation.",
    },
    documentation: {
      title: "Documentation focus",
      description: "Answers prioritize README files, architecture notes, onboarding context, and clear summaries.",
    },
    support_incident: {
      title: "Incident support focus",
      description: "Answers prioritize troubleshooting, symptoms, likely causes, operational context, and next checks.",
    },
    manager_summary: {
      title: "Manager summary focus",
      description: "Answers prioritize concise summaries, risks, progress, decisions, and stakeholder-friendly wording.",
    },
  };

  return focuses[mode] ?? focuses.devops;
}

function getWorkspaceSkillCards(mode: string, detectedCount: number, hasScan: boolean) {
  if (!hasScan) {
    return [
      {
        icon: "1",
        title: "Scan project first",
        description: "Run a project scan to detect languages, infrastructure files, CI/CD, and documentation signals.",
        hint: "Setup step",
      },
      {
        icon: "2",
        title: "Choose a focus",
        description: "The current assistant mode gives answers a starting lens before deeper skill customization is available.",
        hint: "Assistant mode",
      },
      {
        icon: "3",
        title: "Build context",
        description: "After scan, build searchable local context so answers can cite source files.",
        hint: "Source-backed answers",
      },
    ];
  }

  const base = [
    {
      icon: "⌘",
      title: "Detected project skills",
      description: `${detectedCount} technology signals are available from the latest scan.`,
      hint: "From local scan",
    },
    {
      icon: "↳",
      title: "Answer focus",
      description: getAssistantFocus(mode).description,
      hint: "Assistant lens",
    },
  ];

  const presetByMode: Record<string, { icon: string; title: string; description: string; hint: string }> = {
    devops: {
      icon: "☁",
      title: "DevOps preset",
      description: "Best for Terraform, Terragrunt, Kubernetes, Docker, Helm, CI/CD, cloud resources, and deployment flow.",
      hint: "Preset",
    },
    developer: {
      icon: "{}",
      title: "Developer preset",
      description: "Best for code structure, tests, dependencies, implementation details, and change impact.",
      hint: "Preset",
    },
    documentation: {
      icon: "¶",
      title: "Documentation preset",
      description: "Best for onboarding, README quality, architecture notes, project summaries, and missing docs.",
      hint: "Preset",
    },
    support_incident: {
      icon: "!",
      title: "Incident preset",
      description: "Best for troubleshooting, operational checks, likely root causes, and investigation steps.",
      hint: "Preset",
    },
    manager_summary: {
      icon: "✓",
      title: "Manager summary preset",
      description: "Best for risks, progress, decision points, executive summaries, and stakeholder updates.",
      hint: "Preset",
    },
  };

  return [...base, presetByMode[mode] ?? presetByMode.devops];
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
        : "Compare models later if you want to improve answer quality.",
      badge: experimentsSeen ? "feedback ready" : "not started",
      tone: experimentsSeen ? "success" : "neutral",
    },
    {
      title: "Safety posture",
      description: "Workspace actions stay explicit. The frontend never runs shell commands.",
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
            Ask local questions with visible sources. Model comparison and technical setup stay optional.
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
          <span>Best next step</span>
          <strong>Ask a project question</strong>
          <p>Get a local answer with sources you can verify.</p>
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
