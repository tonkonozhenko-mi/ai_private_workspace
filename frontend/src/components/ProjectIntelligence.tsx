import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  askProjectIntelligence,
  buildProjectIntelligence,
  getProjectIntelligence,
  getProjectIntelligenceOverviewText,
  getWorkspaceLatestScan,
  investigateProject,
  addProjectMemory,
} from "../api/client";
import { AnswerFeedback } from "./AnswerFeedback";
import type {
  InvestigationResponse,
  ProjectCi,
  ProjectCloud,
  ProjectDeploymentFlow,
  ProjectEnvironmentComparison,
  ProjectGraphEntity,
  ProjectGraphFinding,
  ProjectGraphPayload,
  ProjectIntelligenceResponse,
  ProjectIntelligenceView,
  ProjectReferences,
  WorkspaceDashboard,
} from "../api/types";
import { ProjectMap } from "./ProjectMap";

// Roles offered in the lens selector. The backend falls back to the developer
// lens for any other assistant_mode, so this list stays small and canonical.
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "developer", label: "Developer" },
  { value: "devops", label: "DevOps" },
  { value: "tester", label: "Tester / QA" },
  { value: "business_analyst", label: "Business analyst" },
];

const SECTION_LABELS: Record<string, string> = {
  summary: "Overview",
  infrastructure: "Infrastructure",
  deployment: "Deployment",
  environments: "Environments",
  risks: "Risks",
  important_files: "Important files",
  questions: "Questions for the team",
  cloud: "Cloud",
  references: "References",
  map: "Map",
  investigate: "Ask the map",
};

const MAP_TAB = "map";
const CLOUD_TAB = "cloud";
const REFERENCES_TAB = "references";
const INVESTIGATE_TAB = "investigate";

const REFERENCE_KIND_LABELS: Record<string, string> = {
  url: "URLs",
  module_source: "Module sources",
  aws_arn: "AWS ARNs",
  s3_bucket: "S3 buckets",
};

// Only these appear as sub-nav tabs; files/questions ride along inside Summary.
const TAB_SECTIONS = new Set([
  "summary",
  "infrastructure",
  "deployment",
  "environments",
  "risks",
]);

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return `${days} d ago`;
}

function statusNote(entity: ProjectGraphEntity): string | null {
  if (entity.status === "inferred") return "inferred";
  if (entity.status === "needs_confirmation") return "needs confirming";
  return null;
}

interface ProjectIntelligenceProps {
  dashboard: WorkspaceDashboard;
}

export function ProjectIntelligence({ dashboard }: ProjectIntelligenceProps) {
  const workspaceId = dashboard.workspace_id;

  const [data, setData] = useState<ProjectIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null); // null = workspace default
  const [activeTab, setActiveTab] = useState<string>("summary");
  const [stale, setStale] = useState(false);

  const [overview, setOverview] = useState<string | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(
    async (roleOverride: string | null) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setLoading(true);
      setError(null);
      try {
        const result = await getProjectIntelligence(
          workspaceId,
          roleOverride ?? undefined,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setData(result);
        // Honest stale check: compare the snapshot's file count to the current scan.
        if (result.built && result.snapshot) {
          checkStale(workspaceId, result.snapshot.scan_signature, controller.signal)
            .then(setStale)
            .catch(() => setStale(false));
        } else {
          setStale(false);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Could not load project intelligence.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    load(role);
    return () => abortRef.current?.abort();
  }, [load, role]);

  const handleBuild = useCallback(async () => {
    setBuilding(true);
    setError(null);
    setOverview(null);
    setOverviewError(null);
    try {
      await buildProjectIntelligence(workspaceId);
      await load(role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not build the project map.");
    } finally {
      setBuilding(false);
    }
  }, [workspaceId, role, load]);

  const handleOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const result = await getProjectIntelligenceOverviewText(workspaceId, role ?? undefined);
      setOverview(result.overview);
    } catch (err) {
      setOverviewError(
        err instanceof Error ? err.message : "The local model could not write an overview.",
      );
    } finally {
      setOverviewLoading(false);
    }
  }, [workspaceId, role]);

  const view = data?.built ? data.view : undefined;
  const graph: ProjectGraphPayload | undefined = data?.built ? data.graph : undefined;
  const flow: ProjectDeploymentFlow | undefined = data?.built ? data.flow : undefined;
  const comparison: ProjectEnvironmentComparison | undefined = data?.built
    ? data.environment_comparison
    : undefined;
  const cloud: ProjectCloud | undefined = data?.built ? data.cloud : undefined;
  const references: ProjectReferences | undefined = data?.built ? data.references : undefined;
  const ci: ProjectCi | undefined = data?.built ? data.ci : undefined;
  const hasMap = Boolean(graph && graph.nodes.length > 0);
  const hasCloud = Boolean(cloud && cloud.total_services > 0);
  const hasReferences = Boolean(references && references.total > 0);

  const tabs = useMemo(() => {
    if (!view) return [];
    const sectionTabs = view.section_order.filter((s) => TAB_SECTIONS.has(s));
    const extra: string[] = [];
    if (hasCloud) extra.push(CLOUD_TAB);
    if (hasReferences) extra.push(REFERENCES_TAB);
    if (hasMap) extra.push(MAP_TAB);
    extra.push(INVESTIGATE_TAB);
    return [...sectionTabs, ...extra];
  }, [view, hasMap, hasCloud, hasReferences]);

  useEffect(() => {
    // Keep the active tab valid when the lens reorders sections.
    if (tabs.length > 0 && !tabs.includes(activeTab)) setActiveTab(tabs[0]);
  }, [tabs, activeTab]);

  return (
    <section className="pi-card">
      <header className="pi-head">
        <div className="pi-head-text">
          <p className="pi-eyebrow">Project intelligence</p>
          <h2 className="pi-title">A map of this project</h2>
          <p className="pi-subtitle">
            Built only from your project's own files — every statement is backed by what was found.
          </p>
        </div>
        <div className="pi-head-controls">
          <label className="pi-role">
            <span>Viewed as</span>
            <select
              value={role ?? "__default__"}
              onChange={(e) =>
                setRole(e.target.value === "__default__" ? null : e.target.value)
              }
              disabled={building || loading}
            >
              <option value="__default__">
                Workspace default
                {view ? ` (${view.role_label})` : ""}
              </option>
              {ROLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          {data?.built ? (
            <button
              type="button"
              className="pi-button"
              onClick={handleBuild}
              disabled={building}
            >
              {building ? "Rebuilding…" : "Rebuild"}
            </button>
          ) : null}
        </div>
      </header>

      {error ? <p className="pi-error">{error}</p> : null}

      {loading && !data ? (
        <p className="pi-muted">Loading…</p>
      ) : !data?.built ? (
        <div className="pi-empty">
          <p className="pi-empty-lead">No project map yet.</p>
          <p className="pi-muted">
            Build a deterministic map of the infrastructure, pipelines, environments and risks
            found in this project. Nothing runs and no files are changed.
          </p>
          <button
            type="button"
            className="pi-button pi-button-primary"
            onClick={handleBuild}
            disabled={building}
          >
            {building ? "Building the map…" : "Build project map"}
          </button>
        </div>
      ) : view ? (
        <>
          {stale ? (
            <div className="pi-stale">
              <span>The project files have changed since this map was built.</span>
              <button type="button" className="pi-link" onClick={handleBuild} disabled={building}>
                {building ? "Rebuilding…" : "Rebuild map"}
              </button>
            </div>
          ) : null}

          <p className="pi-built-meta">
            {data.snapshot ? `Last analyzed ${relativeTime(data.snapshot.created_at)}` : ""}
            {view.analyzers_skipped.length > 0
              ? ` · not detected: ${view.analyzers_skipped.join(", ")}`
              : ""}
          </p>

          <nav className="pi-tabs" role="tablist">
            {tabs.map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                className={`pi-tab${activeTab === tab ? " pi-tab-active" : ""}`}
                onClick={() => setActiveTab(tab)}
              >
                {SECTION_LABELS[tab] ?? tab}
              </button>
            ))}
          </nav>

          <div className="pi-section">
            {activeTab === "summary" ? (
              <SummarySection
                view={view}
                overview={overview}
                overviewLoading={overviewLoading}
                overviewError={overviewError}
                onGenerateOverview={handleOverview}
              />
            ) : null}
            {activeTab === "infrastructure" ? <InfrastructureSection view={view} /> : null}
            {activeTab === "deployment" ? (
              <DeploymentSection view={view} flow={flow} ci={ci} />
            ) : null}
            {activeTab === "environments" ? (
              <EnvironmentsSection view={view} comparison={comparison} />
            ) : null}
            {activeTab === "risks" ? <RisksSection view={view} /> : null}
            {activeTab === CLOUD_TAB && cloud ? <CloudSection cloud={cloud} /> : null}
            {activeTab === REFERENCES_TAB && references ? (
              <ReferencesSection references={references} />
            ) : null}
            {activeTab === MAP_TAB && graph ? <ProjectMap graph={graph} /> : null}
            {activeTab === INVESTIGATE_TAB ? (
              <ProjectQa workspaceId={workspaceId} role={role} />
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}

// --- Sections ---

function SummarySection({
  view,
  overview,
  overviewLoading,
  overviewError,
  onGenerateOverview,
}: {
  view: ProjectIntelligenceView;
  overview: string | null;
  overviewLoading: boolean;
  overviewError: string | null;
  onGenerateOverview: () => void;
}) {
  const { summary, important_files, questions } = view;
  const envNames = view.environments.environments.map((e) => e.name);
  const pipelineNames = view.deployment.pipelines.map((p) => p.name);
  const infraNames = view.infrastructure.components.map((c) => c.name);

  // Each headline number gets a plain-language sub so it means something at a
  // glance — names of the actual environments, pipelines and tools we found.
  const metrics: Array<{ value: number; label: string; sub?: string }> = [
    {
      value: summary.counts.services,
      label: summary.counts.services === 1 ? "service" : "services",
      sub: "apps, modules & images",
    },
    {
      value: summary.counts.environments,
      label: summary.counts.environments === 1 ? "environment" : "environments",
      sub: joinNames(envNames),
    },
    {
      value: summary.counts.pipelines,
      label: summary.counts.pipelines === 1 ? "pipeline" : "pipelines",
      sub: joinNames(pipelineNames) || "CI/CD",
    },
    {
      value: summary.counts.infrastructure,
      label: summary.counts.infrastructure === 1 ? "infra tool" : "infra tools",
      sub: joinNames(infraNames),
    },
  ];

  return (
    <div className="pi-summary">
      <p className="pi-summary-desc">{summary.description}</p>

      {summary.technology_chips.length > 0 ? (
        <div className="pi-chips">
          {summary.technology_chips.map((chip) => (
            <span key={chip} className="pi-chip">
              {chip}
            </span>
          ))}
        </div>
      ) : null}

      <div className="pi-metrics">
        {metrics.map((m) => (
          <div className="pi-metric" key={m.label}>
            <strong>{m.value}</strong>
            <span className="pi-metric-label">{m.label}</span>
            {m.sub ? (
              <span className="pi-metric-sub" title={m.sub}>{m.sub}</span>
            ) : null}
          </div>
        ))}
      </div>

      <div className="pi-overview">
        {overview ? (
          <p className="pi-overview-text">{overview}</p>
        ) : overviewError ? (
          <p className="pi-muted">{overviewError}</p>
        ) : (
          <button
            type="button"
            className="pi-button"
            onClick={onGenerateOverview}
            disabled={overviewLoading}
          >
            {overviewLoading ? "Writing overview…" : "Explain in plain language"}
          </button>
        )}
        {overview ? (
          <p className="pi-overview-note">Written by the local model from the facts above.</p>
        ) : null}
      </div>

      {important_files.files.length > 0 ? (
        <div className="pi-subblock">
          <p className="pi-eyebrow">Where to start reading</p>
          <p className="pi-hint">The files that explain the most about how this project fits together.</p>
          <ul className="pi-file-list">
            {important_files.files.map((f) => (
              <li key={f.path}>
                <code>{f.path}</code>
                {f.reason ? <span className="pi-file-reason">{f.reason}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {questions.questions.length > 0 ? (
        <div className="pi-subblock">
          <p className="pi-eyebrow">Questions for the team</p>
          <p className="pi-hint">Things the files can't answer on their own — worth confirming with a person.</p>
          <ul className="pi-question-list">
            {questions.questions.map((q) => (
              <li key={q.question}>
                <span className="pi-question-text">{q.question}</span>
                <span className="pi-question-reason">{q.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// Joins a few names for a metric sub-line: "dev, staging, prod" or "a, b +3".
function joinNames(names: string[], max = 3): string {
  if (names.length === 0) return "";
  const shown = names.slice(0, max).join(", ");
  return names.length > max ? `${shown} +${names.length - max}` : shown;
}

function InfrastructureSection({ view }: { view: ProjectIntelligenceView }) {
  const { components, images } = view.infrastructure;
  if (components.length === 0 && images.length === 0) {
    return <EmptyNote text="No infrastructure tooling was detected in this project." />;
  }
  return (
    <div className="pi-entity-groups">
      <p className="pi-hint">What provisions and packages this project — each item links back to the file it came from.</p>
      {components.length > 0 ? (
        <EntityList title="Infrastructure tools" entities={components} />
      ) : null}
      {images.length > 0 ? <EntityList title="Container images" entities={images} /> : null}
    </div>
  );
}

function DeploymentSection({
  view,
  flow,
  ci,
}: {
  view: ProjectIntelligenceView;
  flow?: ProjectDeploymentFlow;
  ci?: ProjectCi;
}) {
  const { pipelines } = view.deployment;
  return (
    <div className="pi-deploy">
      {flow ? <FlowRail flow={flow} /> : null}
      {ci && ci.has_data ? <CiScenarios ci={ci} /> : null}
      {pipelines.length === 0 ? (
        <EmptyNote text="No CI/CD pipelines were detected in this project." />
      ) : (
        <PipelineList pipelines={pipelines} />
      )}
    </div>
  );
}

function FlowRail({ flow }: { flow: ProjectDeploymentFlow }) {
  return (
    <div className="pi-flow">
      <p className="pi-eyebrow">How code reaches an environment</p>
      <p className="pi-hint">Each stage is counted from what was found in the project — follow it left to right.</p>
      <div className="pi-flow-rail">
        {flow.stages.map((stage, i) => (
          <div key={stage.key} className="pi-flow-stage-wrap">
            <div className="pi-flow-stage">
              <span className="pi-flow-count">{stage.count}</span>
              <span className="pi-flow-label">{stage.label}</span>
              <span className="pi-flow-detail">{stage.detail}</span>
            </div>
            {i < flow.stages.length - 1 ? <span className="pi-flow-arrow">→</span> : null}
          </div>
        ))}
      </div>
      {flow.gaps.length > 0 ? (
        <ul className="pi-flow-gaps">
          {flow.gaps.map((gap) => (
            <li key={gap.title}>
              <span className="pi-flow-gap-title">{gap.title}</span>
              <span className="pi-flow-gap-explain">{gap.explanation}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="pi-muted">No gaps detected in the deployment chain.</p>
      )}
    </div>
  );
}

function CiScenarios({ ci }: { ci: ProjectCi }) {
  return (
    <div className="pi-ci">
      <p className="pi-eyebrow">What runs when</p>
      <p className="pi-hint">Which CI workflows fire on each kind of event — inferred from their triggers.</p>
      <div className="pi-ci-list">
        {ci.scenarios.map((s) => (
          <div key={s.key} className="pi-ci-scenario">
            <span className="pi-ci-trigger">{s.label}</span>
            <div className="pi-ci-workflows">
              {s.workflows.map((w) => (
                <span key={w.name} className="pi-ci-workflow" title={w.jobs.join(", ")}>
                  {w.name}
                  {w.jobs.length > 0 ? (
                    <em>{w.jobs.length} job{w.jobs.length === 1 ? "" : "s"}</em>
                  ) : null}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="pi-ci-note">
        Inferred from GitHub Actions triggers — job-level rules may gate some steps further.
      </p>
    </div>
  );
}

function PipelineList({
  pipelines,
}: {
  pipelines: ProjectIntelligenceView["deployment"]["pipelines"];
}) {
  return (
    <div className="pi-pipelines">
      <p className="pi-eyebrow">Pipelines</p>
      <p className="pi-hint">Every CI/CD pipeline found, with the jobs inside it.</p>
      {pipelines.map((p) => (
        <div key={p.id} className="pi-pipeline">
          <div className="pi-pipeline-head">
            <span className="pi-entity-name">{p.name}</span>
            {p.source_file ? <code className="pi-source">{p.source_file}</code> : null}
          </div>
          {p.jobs.length > 0 ? (
            <div className="pi-jobs">
              {p.jobs.map((j) => (
                <span key={j.id} className="pi-job">
                  {j.name}
                  {j.metadata.stage ? <em>{j.metadata.stage}</em> : null}
                </span>
              ))}
            </div>
          ) : (
            <p className="pi-muted">No individual jobs were detected for this pipeline.</p>
          )}
        </div>
      ))}
    </div>
  );
}

function EnvironmentsSection({
  view,
  comparison,
}: {
  view: ProjectIntelligenceView;
  comparison?: ProjectEnvironmentComparison;
}) {
  const { environments } = view.environments;
  if (environments.length === 0) {
    return (
      <EmptyNote text="No environments were detected from the project's directory structure." />
    );
  }
  const rows = comparison?.environments ?? [];
  const maxEvidence = rows.reduce((m, r) => Math.max(m, r.evidence_count), 0) || 1;
  return (
    <div className="pi-envs">
      <p className="pi-hint">
        Inferred from directory and file naming — confirm them with your team. "Evidence" is
        how many paths point at each environment.
      </p>
      {comparison ? <p className="pi-env-summary">{comparison.summary}</p> : null}

      {rows.length > 0 ? (
        <ul className="pi-env-list">
          {rows.map((row) => {
            const isProd = /(^|[^a-z])(prod|prd)([^a-z]|$)/i.test(row.name);
            return (
              <li key={row.name} className={`pi-env-row${isProd ? " is-prod" : ""}`}>
                <span className="pi-env-name">
                  {row.name}
                  {isProd ? <em>production</em> : null}
                </span>
                <span className="pi-env-detector">{row.analyzer}</span>
                <span className="pi-env-evidence">
                  <span className="pi-env-evidence-bar">
                    <span style={{ width: `${Math.round((row.evidence_count / maxEvidence) * 100)}%` }} />
                  </span>
                  {row.evidence_count} paths
                </span>
                {row.source_file ? (
                  <code className="pi-env-source" title={row.source_file}>{row.source_file}</code>
                ) : (
                  <span className="pi-env-source pi-env-source-empty">—</span>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="pi-chips">
          {environments.map((e) => {
            const note = statusNote(e);
            return (
              <span key={e.id} className="pi-chip pi-chip-env">
                {e.name}
                {note ? <em>{note}</em> : null}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

const TOOL_LABELS: Record<string, string> = {
  search_code: "Searched code",
  read_file: "Read file",
  graph_query: "Queried the map",
  list_files: "Listed files",
  git_history: "Checked git history",
  "(format)": "Retried",
};

// One place to ask about the project, with two depths: a quick answer from the
// map facts, or a read-only agent that investigates step by step. This replaces
// the old split between a quick "Ask" box and a separate "Investigate" panel.
function ProjectQa({
  workspaceId,
  role,
}: {
  workspaceId: string;
  role: string | null;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResponse | null>(null);
  const [loading, setLoading] = useState<null | "ask" | "investigate">(null);
  const [error, setError] = useState<string | null>(null);

  const empty = question.trim().length === 0;

  async function runAsk() {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    setLoading("ask");
    setError(null);
    setAnswer(null);
    setResult(null);
    try {
      const res = await askProjectIntelligence(workspaceId, trimmed, role ?? undefined);
      setAnswer(res.answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The local model could not answer.");
    } finally {
      setLoading(null);
    }
  }

  async function runInvestigate() {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    setLoading("investigate");
    setError(null);
    setAnswer(null);
    setResult(null);
    try {
      const res = await investigateProject(workspaceId, trimmed, role ?? undefined);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The investigation could not run.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="pi-qa">
      <p className="pi-hint">
        Ask for a quick answer from the project map, or send a read-only agent to
        investigate — it searches code, reads files and shows its steps. Nothing is changed.
      </p>
      <div className="pi-ask-row">
        <input
          className="pi-ask-input"
          type="text"
          value={question}
          placeholder="e.g. How does a request reach the database?"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") runAsk();
          }}
          disabled={loading !== null}
        />
        <button
          type="button"
          className="pi-button"
          onClick={runAsk}
          disabled={loading !== null || empty}
        >
          {loading === "ask" ? "Asking…" : "Ask"}
        </button>
        <button
          type="button"
          className="pi-button pi-button-primary"
          onClick={runInvestigate}
          disabled={loading !== null || empty}
        >
          {loading === "investigate" ? "Investigating…" : "Investigate"}
        </button>
      </div>

      {loading === "investigate" ? (
        <p className="pi-muted">Working through the project step by step…</p>
      ) : null}
      {error ? <p className="pi-muted">{error}</p> : null}

      {answer ? (
        <div className="pi-qa-answer">
          <p className="pi-eyebrow">Answer</p>
          <p className="pi-ask-answer">{answer}</p>
          <p className="pi-ask-note">A quick answer from the analyzed project files.</p>
          <AnswerFeedback
            question={question}
            answer={answer}
            onSave={(text, k) => addProjectMemory(workspaceId, text, k)}
          />
        </div>
      ) : null}

      {result ? (
        <div className="pi-inv-result">
          <div className="pi-inv-answer">
            <p className="pi-eyebrow">Answer</p>
            <p className="pi-inv-answer-text">{result.answer}</p>
            {result.stopped_reason === "budget_exhausted" ? (
              <p className="pi-inv-note">
                Reached the step limit — this is the best answer from what was gathered.
              </p>
            ) : null}
            {result.context_used &&
            (result.context_used.memory > 0 || result.context_used.facts > 0) ? (
              <p className="pi-inv-note">
                Used {result.context_used.memory} memory note(s) and{" "}
                {result.context_used.facts} map fact(s) as background.
              </p>
            ) : null}
            <AnswerFeedback
              question={question}
              answer={result.answer}
              onSave={(text, k) => addProjectMemory(workspaceId, text, k)}
            />
          </div>

          {result.steps.length > 0 ? (
            <details className="pi-inv-trace">
              <summary>
                How it figured this out · {result.steps.length} step(s)
              </summary>
              <ol className="pi-inv-steps">
                {result.steps.map((step, i) => (
                  <li key={i} className="pi-inv-step">
                    <div className="pi-inv-step-head">
                      <span className="pi-inv-tool">
                        {TOOL_LABELS[step.tool] ?? step.tool}
                      </span>
                      {step.tool_input ? (
                        <code className="pi-inv-input">{step.tool_input}</code>
                      ) : null}
                    </div>
                    {step.thought ? (
                      <p className="pi-inv-thought">{step.thought}</p>
                    ) : null}
                    <pre className="pi-inv-obs">{step.observation}</pre>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}

          {result.sources.length > 0 ? (
            <div className="pi-inv-sources">
              <p className="pi-eyebrow">Sources consulted</p>
              <div className="pi-chips">
                {result.sources.map((s) => (
                  <span key={s} className="pi-chip">
                    <code>{s}</code>
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function RisksSection({ view }: { view: ProjectIntelligenceView }) {
  const { findings } = view.risks;
  if (findings.length === 0) {
    return <EmptyNote text="Nothing looked risky to the deterministic analyzers — no findings to show." />;
  }
  const high = findings.filter((f) => f.severity === "high").length;
  const medium = findings.filter((f) => f.severity === "medium").length;
  const parts = [`${findings.length} thing${findings.length === 1 ? "" : "s"} worth a look`];
  if (high > 0) parts.push(`${high} high`);
  if (medium > 0) parts.push(`${medium} medium`);
  return (
    <div className="pi-risks">
      <p className="pi-hint">{parts.join(" · ")}. Each finding shows its evidence — open “Show sources” to see where it came from.</p>
      <ul className="pi-findings">
        {findings.map((f) => (
          <FindingItem key={f.id} finding={f} />
        ))}
      </ul>
    </div>
  );
}

// --- Small pieces ---

function FindingItem({ finding }: { finding: ProjectGraphFinding }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const hasEvidence = finding.evidence.length > 0 || Boolean(finding.source_file);
  return (
    <li className="pi-finding">
      <div className="pi-finding-head">
        <span className={`pi-severity pi-severity-${finding.severity}`}>{finding.severity}</span>
        <span className="pi-finding-title">{finding.title}</span>
      </div>
      <p className="pi-finding-explain">{finding.explanation}</p>
      {finding.recommendation ? (
        <p className="pi-finding-reco">{finding.recommendation}</p>
      ) : null}
      {hasEvidence ? (
        <>
          <button
            type="button"
            className="pi-link"
            onClick={() => setShowEvidence((v) => !v)}
          >
            {showEvidence ? "Hide sources" : "Show sources"}
          </button>
          {showEvidence ? (
            <div className="pi-evidence">
              {finding.source_file ? (
                <code className="pi-source">{finding.source_file}</code>
              ) : null}
              {finding.evidence.map((ev, i) => (
                <span key={i} className="pi-evidence-line">
                  {ev}
                </span>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </li>
  );
}

function infraMetaChips(e: ProjectGraphEntity): string[] {
  const chips: string[] = [];
  const m = e.metadata || {};
  if (m.files) chips.push(`${m.files} files`);
  if (m.providers) chips.push(m.providers);
  // Only the positive signal is reliable: a Terraform stack managed by Terragrunt
  // keeps its backend in terragrunt.hcl, so "no backend block in .tf" is not the
  // same as "no remote state" — don't assert the negative.
  if (m.remote_state === "True") {
    chips.push(m.remote_state_via ? `remote state · ${m.remote_state_via}` : "remote state");
  }
  if (m.modules === "True") chips.push("modules");
  if (m.charts) chips.push(`${m.charts} chart(s)`);
  if (m.workloads) chips.push(`${m.workloads} workload(s)`);
  if (m.namespaces) chips.push(m.namespaces);
  return chips;
}

function EntityList({ title, entities }: { title: string; entities: ProjectGraphEntity[] }) {
  return (
    <div className="pi-entity-group">
      <p className="pi-eyebrow">{title}</p>
      <ul className="pi-entity-list">
        {entities.map((e) => {
          const note = statusNote(e);
          const chips = infraMetaChips(e);
          return (
            <li key={e.id} className="pi-entity pi-entity-block">
              <div className="pi-entity-row">
                <span className="pi-entity-name">{e.name}</span>
                {note ? <span className="pi-entity-note">{note}</span> : null}
                {e.source_file ? <code className="pi-source">{e.source_file}</code> : null}
              </div>
              {chips.length > 0 ? (
                <div className="pi-entity-meta">
                  {chips.map((c) => (
                    <span key={c} className="pi-meta-chip">
                      {c}
                    </span>
                  ))}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CloudSection({ cloud }: { cloud: ProjectCloud }) {
  if (cloud.providers.length === 0) {
    return <EmptyNote text="No managed cloud services were detected in the infrastructure." />;
  }
  return (
    <div className="pi-cloud">
      <p className="pi-hint">
        Managed cloud services provisioned by the project's infrastructure-as-code. The number is
        how many resources of that service were found; the bar shows its relative footprint.
      </p>
      {cloud.providers.map((provider) => {
        const max = provider.services.reduce((m, s) => Math.max(m, s.resources), 0) || 1;
        const top = provider.services.slice(0, 3).map((s) => s.service).join(", ");
        return (
          <section key={provider.provider} className="pi-cloud-provider">
            <div className="pi-cloud-provider-head">
              <span className="pi-cloud-provider-name">{provider.provider}</span>
              <span className="pi-cloud-provider-count">{provider.service_count} services</span>
              {top ? <span className="pi-cloud-top">most used: {top}</span> : null}
            </div>
            <div className="pi-cloud-services">
              {provider.services.map((s) => (
                <div key={s.service} className="pi-cloud-service" title={s.source_file ?? ""}>
                  <div className="pi-cloud-service-row">
                    <span className="pi-cloud-service-name">{s.service}</span>
                    <span className="pi-cloud-service-count">{s.resources}</span>
                  </div>
                  <span className="pi-cloud-bar">
                    <span style={{ width: `${Math.round((s.resources / max) * 100)}%` }} />
                  </span>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function ReferencesSection({ references }: { references: ProjectReferences }) {
  if (references.groups.length === 0) {
    return <EmptyNote text="No external references were found in the project's files." />;
  }
  return (
    <div className="pi-refs">
      <p className="pi-hint">
        External things the project points at — ARNs, URLs and module sources pulled from its
        files. The number is how many times each appears.
      </p>
      {references.groups.map((group) => (
        <ReferenceGroup key={group.kind} group={group} />
      ))}
    </div>
  );
}

function ReferenceGroup({
  group,
}: {
  group: ProjectReferences["groups"][number];
}) {
  const [showAll, setShowAll] = useState(false);
  const LIMIT = 12;
  const items = showAll ? group.items : group.items.slice(0, LIMIT);
  return (
    <section className="pi-ref-group">
      <div className="pi-ga-head">
        <span className="pi-eyebrow">{REFERENCE_KIND_LABELS[group.kind] ?? group.kind}</span>
        <span className="pi-ga-hint">{group.items.length}</span>
      </div>
      <ul className="pi-ref-list">
        {items.map((item) => (
          <li
            key={item.value}
            className="pi-ref-item"
            title={`${item.value}${item.source_file ? ` — ${item.source_file}` : ""}`}
          >
            <code className="pi-ref-value">{item.value}</code>
            {item.count > 1 ? <span className="pi-ref-count">×{item.count}</span> : null}
          </li>
        ))}
      </ul>
      {group.items.length > LIMIT ? (
        <button type="button" className="pi-link" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Show fewer" : `Show all ${group.items.length}`}
        </button>
      ) : null}
    </section>
  );
}

function EmptyNote({ text }: { text: string }) {
  return <p className="pi-muted pi-empty-note">{text}</p>;
}

// Compares the snapshot's "files:N" signature to the current scan's file count.
// Returns true when they differ (the map is out of date). Best-effort only.
async function checkStale(
  workspaceId: string,
  scanSignature: string | null,
  signal: AbortSignal,
): Promise<boolean> {
  if (!scanSignature || !scanSignature.startsWith("files:")) return false;
  const builtCount = Number.parseInt(scanSignature.slice("files:".length), 10);
  if (Number.isNaN(builtCount)) return false;
  try {
    const scan = await getWorkspaceLatestScan(workspaceId, { signal });
    if (!scan || !Array.isArray(scan.files)) return false;
    return scan.files.length !== builtCount;
  } catch {
    return false;
  }
}
