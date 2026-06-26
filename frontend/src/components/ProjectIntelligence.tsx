import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildProjectIntelligence,
  getProjectIntelligence,
  getProjectIntelligenceOverviewText,
  getWorkspaceLatestScan,
  updateWorkspaceAssistantMode,
} from "../api/client";
import type {
  ProjectCi,
  ProjectCloud,
  ProjectDeploymentFlow,
  ProjectEnvironmentComparison,
  ProjectGraphEntity,
  ProjectGraphFinding,
  ProjectGraphNode,
  ProjectGraphPayload,
  ProjectIntelligenceResponse,
  ProjectIntelligenceView,
  ProjectReferences,
  RoleBrief,
  WorkspaceDashboard,
} from "../api/types";
import { ProjectMap } from "./ProjectMap";
import { ProjectWatchHistory } from "./ProjectWatchHistory";
import { SKILL_PRESETS } from "./skillLibrary";

// Roles offered in the lens selector. The backend falls back to the developer
// One canonical role list, shared with Settings skills and the create form, so
// the same five names appear everywhere. The backend lens folds any legacy
// assistant_mode onto the nearest of these.
const ROLE_OPTIONS: { value: string; label: string }[] = SKILL_PRESETS.map((preset) => ({
  value: preset.id,
  label: preset.name,
}));

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
  security: "Security review",
  cicd: "CI/CD flow",
  history: "History",
};

const MAP_TAB = "map";
const CLOUD_TAB = "cloud";
const REFERENCES_TAB = "references";
const SECURITY_TAB = "security";
const CICD_TAB = "cicd";
const HISTORY_TAB = "history";

// Security-relevant concepts, detected generically by token — no project- or
// vendor-specific hardcoding beyond well-known scanner names that work anywhere.
const SCANNER_RE = /scan|security|audit|trivy|checkov|gitleaks|secret|sonar|snyk|semgrep|bandit|tfsec|dependabot|codeql|vuln/i;
const SECURITY_FINDING_RE = /secret|credential|password|permission|public|expos|encrypt|unencrypted|iam|access|policy|ssl|tls|cors|privileg|remote[_ ]state|0\.0\.0\.0|firewall|port|auth/i;

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
  onInspectFile?: (path: string) => void;
  onAskQuestion?: (question: string) => void;
  // Called after the role is saved to the workspace, so the rest of the app
  // (Ask especially) can pick up the new role.
  onRolePersisted?: (mode: string) => void;
}

export function ProjectIntelligence({
  dashboard,
  onInspectFile,
  onAskQuestion,
  onRolePersisted,
}: ProjectIntelligenceProps) {
  const workspaceId = dashboard.workspace_id;

  const [data, setData] = useState<ProjectIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The role is the workspace's saved assistant_mode — one setting, shared with
  // Ask. Changing it here persists it for the whole workspace.
  const [role, setRole] = useState<string>(dashboard.assistant_mode);
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

  // Keep in sync if the role is changed elsewhere (e.g. Settings).
  useEffect(() => {
    setRole(dashboard.assistant_mode);
  }, [dashboard.assistant_mode]);

  // Change the workspace's role: re-frame the map immediately (the load effect
  // reacts to `role`), persist it to the workspace, and tell the app so Ask
  // follows. Persisting failing shouldn't block the local re-frame.
  const changeRole = useCallback(
    (mode: string) => {
      setRole(mode);
      void updateWorkspaceAssistantMode(workspaceId, mode)
        .then(() => onRolePersisted?.(mode))
        .catch(() => {});
    },
    [workspaceId, onRolePersisted],
  );

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
  const brief = data?.built ? data.brief : undefined;
  const hasMap = Boolean(graph && graph.nodes.length > 0);
  const hasCloud = Boolean(cloud && cloud.total_services > 0);
  const hasReferences = Boolean(references && references.total > 0);

  const security = useMemo(() => {
    const scanners = graph
      ? Array.from(
          new Map(
            graph.nodes
              .filter((n) => (n.type === "pipeline_job" || n.type === "pipeline") && SCANNER_RE.test(n.name))
              .map((n) => [n.name, n]),
          ).values(),
        )
      : [];
    const findings = (view?.risks?.findings ?? []).filter(
      (f) => SECURITY_FINDING_RE.test(`${f.title} ${f.explanation} ${f.id} ${f.category}`),
    );
    return { scanners, findings };
  }, [graph, view]);
  const hasSecurity = security.scanners.length > 0 || security.findings.length > 0;

  const hasCicd = Boolean(ci?.has_data);

  const tabs = useMemo(() => {
    if (!view) return [];
    const sectionTabs = view.section_order.filter((s) => TAB_SECTIONS.has(s));
    const extra: string[] = [];
    if (hasCicd) extra.push(CICD_TAB);
    if (hasCloud) extra.push(CLOUD_TAB);
    if (hasReferences) extra.push(REFERENCES_TAB);
    if (hasSecurity) extra.push(SECURITY_TAB);
    if (hasMap) extra.push(MAP_TAB);
    // History is always available — it's a timeline that fills as checks run.
    extra.push(HISTORY_TAB);
    return [...sectionTabs, ...extra];
  }, [view, hasMap, hasCloud, hasReferences, hasSecurity, hasCicd]);

  useEffect(() => {
    // Keep the active tab valid when the lens reorders sections.
    if (tabs.length > 0 && !tabs.includes(activeTab)) setActiveTab(tabs[0]);
  }, [tabs, activeTab]);

  // When the role changes, land on the tab that role cares about most — the
  // first section its lens prioritises (after the overview). Switching role then
  // visibly takes you somewhere relevant, not just reshuffles the tab row. Only
  // fires on an actual role change, so it never fights the user's own clicks.
  const lastRoleRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (!data?.built || !view) return;
    const currentRole = data.role ?? null;
    if (lastRoleRef.current === currentRole) return;
    lastRoleRef.current = currentRole;
    const ordered = view.section_order.filter((s) => tabs.includes(s));
    const landing = ordered.find((s) => s !== "summary") ?? tabs[0];
    if (landing) setActiveTab(landing);
  }, [data?.role, data?.built, view, tabs]);

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
          <label className="pi-role" title="The workspace role. Re-frames the map and Ask, and is saved for this project. Applies instantly — no rebuild needed.">
            <span>Role</span>
            <select
              value={role}
              onChange={(e) => changeRole(e.target.value)}
              disabled={building || loading}
            >
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

          {brief ? <RoleDashboardBrief brief={brief} onAskQuestion={onAskQuestion} /> : null}

          {(graph?.nodes.length ?? 0) < 4 ? (
            <div className="pi-empty-project">
              <strong>Not much to map here yet.</strong>
              <p className="pi-hint">
                The analyzers found little infrastructure or code to connect — that's normal for a
                small, docs-only, or single-purpose repo, and isn't an error. The map (and the
                difference between role profiles) fills in as the project grows. The <em>Ask</em>{" "}
                tab still answers from this project's files.
              </p>
            </div>
          ) : null}

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
                onInspectFile={onInspectFile}
              />
            ) : null}
            {activeTab === "infrastructure" ? <InfrastructureSection view={view} /> : null}
            {activeTab === "deployment" ? (
              <DeploymentSection view={view} flow={flow} ci={ci} />
            ) : null}
            {activeTab === "environments" ? (
              <EnvironmentsSection view={view} comparison={comparison} />
            ) : null}
            {activeTab === "risks" ? <RisksSection view={view} onInspectFile={onInspectFile} /> : null}
            {activeTab === CICD_TAB && ci ? (
              <CicdFlowSection
                ci={ci}
                environments={view.environments.environments}
                onInspectFile={onInspectFile}
              />
            ) : null}
            {activeTab === CLOUD_TAB && cloud ? <CloudSection cloud={cloud} /> : null}
            {activeTab === REFERENCES_TAB && references ? (
              <ReferencesSection references={references} />
            ) : null}
            {activeTab === SECURITY_TAB ? (
              <SecuritySection scanners={security.scanners} findings={security.findings} />
            ) : null}
            {activeTab === MAP_TAB && graph ? <ProjectMap graph={graph} /> : null}
            {activeTab === HISTORY_TAB ? <ProjectWatchHistory workspaceId={workspaceId} /> : null}
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
  onInspectFile,
}: {
  view: ProjectIntelligenceView;
  overview: string | null;
  overviewLoading: boolean;
  overviewError: string | null;
  onGenerateOverview: () => void;
  onInspectFile?: (path: string) => void;
}) {
  const { summary, important_files, questions } = view;

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
                {onInspectFile ? (
                  <button type="button" className="pi-file-link" title={`Inspect ${f.path}`} onClick={() => onInspectFile(f.path)}>
                    {f.path}
                  </button>
                ) : (
                  <code>{f.path}</code>
                )}
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

// A visual CI/CD flow: for each kind of event, the workflows it fires and the
// jobs inside them, laid out left-to-right (trigger -> workflows -> jobs).
// Security-scan jobs are flagged using the same generic scanner vocabulary the
// Security lens uses. Everything is the deterministic CI data already extracted
// from the project's own workflow files — nothing here is invented.
function CicdFlowSection({
  ci,
  environments,
  onInspectFile,
}: {
  ci: ProjectCi;
  environments: ProjectGraphEntity[];
  onInspectFile?: (path: string) => void;
}) {
  if (!ci.has_data || ci.scenarios.length === 0) {
    return <EmptyNote text="No CI workflows were detected, so there is no pipeline flow to show." />;
  }
  return (
    <div className="pi-cicd">
      <p className="pi-hint">
        How this project's pipelines flow: each trigger, the workflows it fires, and the jobs inside
        them. Inferred from the workflow files — job-level rules may gate some steps further.
      </p>

      <div className="pi-cicd-flow">
        {ci.scenarios.map((s) => (
          <div key={s.key} className="pi-cicd-lane">
            <div className="pi-cicd-trigger">
              <span className="pi-cicd-trigger-dot" aria-hidden="true" />
              <span className="pi-cicd-trigger-label">{s.label}</span>
            </div>
            <span className="pi-cicd-arrow" aria-hidden="true">→</span>
            <div className="pi-cicd-workflows">
              {s.workflows.map((w) => (
                <div key={`${s.key}-${w.name}`} className="pi-cicd-workflow">
                  <div className="pi-cicd-workflow-head">
                    <span className="pi-cicd-workflow-name">{w.name}</span>
                    {w.source_file ? (
                      onInspectFile ? (
                        <button
                          type="button"
                          className="pi-file-link"
                          title={`Inspect ${w.source_file}`}
                          onClick={() => onInspectFile(w.source_file as string)}
                        >
                          {w.source_file}
                        </button>
                      ) : (
                        <code className="pi-source">{w.source_file}</code>
                      )
                    ) : null}
                  </div>
                  {w.cron && w.cron.length > 0 ? (
                    <span className="pi-cicd-cron">schedule: {w.cron.join(", ")}</span>
                  ) : null}
                  {w.jobs.length > 0 ? (
                    <div className="pi-cicd-jobs">
                      {w.jobs.map((job) => {
                        const isScan = SCANNER_RE.test(job);
                        return (
                          <span
                            key={job}
                            className={`pi-cicd-job${isScan ? " pi-cicd-job-scan" : ""}`}
                            title={isScan ? "Looks like a security/scan step" : undefined}
                          >
                            {job}
                          </span>
                        );
                      })}
                    </div>
                  ) : (
                    <span className="pi-cicd-nojobs">no named jobs detected</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {environments.length > 0 ? (
        <div className="pi-cicd-envs">
          <span className="pi-finding-label">Environments this project defines</span>
          <div className="pi-cicd-env-chips">
            {environments.map((e) => (
              <span key={e.id} className="pi-cicd-env">
                {e.name}
              </span>
            ))}
          </div>
          <p className="pi-ci-note">
            Which workflow deploys to which environment isn't always stated explicitly in the files,
            so this lists the environments rather than wiring each one to a trigger.
          </p>
        </div>
      ) : null}
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
        <ul className="pi-env-list pi-env-matrix">
          <li className="pi-env-row pi-env-head" aria-hidden="true">
            <span className="pi-env-name">Environment</span>
            <span className="pi-env-detector">Detected by</span>
            <span className="pi-env-evidence">Evidence</span>
            <span className="pi-env-source">Defined in</span>
          </li>
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

// A read-only security posture lens: which security checks already run in CI,
// and which deterministic findings are security-relevant. It reads what gates
// exist and where the gaps are — it does not run any scanner itself.
function SecuritySection({
  scanners,
  findings,
}: {
  scanners: ProjectGraphNode[];
  findings: ProjectGraphFinding[];
}) {
  const high = findings.filter((f) => f.severity === "high").length;
  const summary =
    scanners.length > 0
      ? `${scanners.length} security check${scanners.length === 1 ? "" : "s"} run in CI.`
      : "No automated security checks were detected in CI.";
  const findingLine =
    findings.length > 0
      ? ` ${findings.length} security-relevant finding${findings.length === 1 ? "" : "s"}${high ? ` (${high} high)` : ""} to review.`
      : " Nothing security-relevant flagged by the deterministic analyzers.";

  return (
    <div className="pi-security">
      <p className="pi-hint">{summary}{findingLine}</p>

      <div className="pi-sec-block">
        <p className="pi-eyebrow">Security checks in CI</p>
        {scanners.length > 0 ? (
          <ul className="pi-sec-scanners">
            {scanners.map((s) => (
              <li key={s.id} className="pi-sec-scanner" title={s.source_file ?? undefined}>
                <span className="pi-sec-dot" />
                <span className="pi-sec-scanner-name">{s.name}</span>
                {s.source_file ? <code className="pi-sec-src">{s.source_file}</code> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="pi-muted">
            No scan/audit steps found in the pipelines. Consider adding secret, dependency and IaC scanning.
          </p>
        )}
      </div>

      {findings.length > 0 ? (
        <div className="pi-sec-block">
          <p className="pi-eyebrow">Security-relevant findings</p>
          <ul className="pi-sec-findings">
            {findings.map((f) => (
              <li key={f.id} className="pi-sec-finding">
                <div className="pi-sec-finding-head">
                  <span className={`pi-sev pi-sev-${f.severity}`}>
                    {f.explained?.attention ?? f.severity}
                  </span>
                  <span className="pi-sec-finding-title">{f.title}</span>
                  {f.source_file ? <code className="pi-sec-src">{f.source_file}</code> : null}
                </div>
                {f.explained?.why_it_may_matter ? (
                  <p className="pi-sec-why">{f.explained.why_it_may_matter}</p>
                ) : null}
                {f.explained?.suggested_idea ?? f.recommendation ? (
                  <p className="pi-sec-rec">{f.explained?.suggested_idea ?? f.recommendation}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// The adaptive role dashboard header: one band that re-frames the same facts for
// whoever is looking. The role label, the facts it leads with, the risks that
// matter to it, and questions worth asking — all decided on the backend from the
// project's own evidence, never hardcoded here.
function RoleDashboardBrief({
  brief,
  onAskQuestion,
}: {
  brief: RoleBrief;
  onAskQuestion?: (question: string) => void;
}) {
  const hasFacts = brief.facts.length > 0;
  return (
    <section className="pi-brief" aria-label={`${brief.label} dashboard`}>
      <div className="pi-brief-head">
        <span className="pi-brief-eyebrow">{brief.label} dashboard</span>
      </div>
      <p className="pi-brief-focus">{brief.focus}</p>

      {hasFacts ? (
        <div className="pi-brief-facts">
          {brief.facts.map((fact) => (
            <span
              key={fact.label}
              className="pi-brief-fact"
              title={fact.examples.length > 0 ? fact.examples.join(", ") : undefined}
            >
              <span className="pi-brief-fact-count">{fact.count}</span>
              <span className="pi-brief-fact-label">{fact.label}</span>
            </span>
          ))}
        </div>
      ) : null}

      {brief.top_risks.length > 0 ? (
        <p className="pi-brief-risks">
          <span className="pi-finding-label">Worth your attention</span>
          {brief.top_risks.join(" · ")}
        </p>
      ) : null}

      {brief.suggested_questions.length > 0 && onAskQuestion ? (
        <div className="pi-brief-questions">
          <span className="pi-finding-label">Questions worth asking</span>
          <div className="pi-brief-qchips">
            {brief.suggested_questions.map((q) => (
              <button
                key={q}
                type="button"
                className="pi-brief-qchip"
                onClick={() => onAskQuestion(q)}
                title="Open this in Ask"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function RisksSection({
  view,
  onInspectFile,
}: {
  view: ProjectIntelligenceView;
  onInspectFile?: (path: string) => void;
}) {
  const { findings } = view.risks;
  if (findings.length === 0) {
    return <EmptyNote text="Nothing looked risky to the deterministic analyzers — no findings to show." />;
  }
  const highlighted = new Set(view.risks.highlighted_categories);
  const high = findings.filter((f) => f.severity === "high").length;
  const medium = findings.filter((f) => f.severity === "medium").length;
  const parts = [`${findings.length} thing${findings.length === 1 ? "" : "s"} to review`];
  if (high > 0) parts.push(`${high} worth a close look`);
  if (medium > 0) parts.push(`${medium} worth reviewing`);
  return (
    <div className="pi-risks">
      <p className="pi-hint">
        {parts.join(" · ")}. These are leads for a human, not verdicts — each one says why it may
        matter and what to check yourself. The ones most relevant to your role are marked and
        listed first.
      </p>
      <ul className="pi-findings">
        {findings.map((f) => (
          <FindingItem
            key={f.id}
            finding={f}
            roleRelevant={highlighted.has(f.category)}
            onInspectFile={onInspectFile}
          />
        ))}
      </ul>
    </div>
  );
}

// --- Small pieces ---

function FindingItem({
  finding,
  roleRelevant = false,
  onInspectFile,
}: {
  finding: ProjectGraphFinding;
  roleRelevant?: boolean;
  onInspectFile?: (path: string) => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const hasEvidence = finding.evidence.length > 0 || Boolean(finding.source_file);
  const ex = finding.explained;
  const where = ex?.where ?? finding.source_file;
  return (
    <li className={`pi-finding${roleRelevant ? " is-role-relevant" : ""}`}>
      <div className="pi-finding-head">
        <span className={`pi-severity pi-severity-${finding.severity}`}>
          {ex?.attention ?? finding.severity}
        </span>
        <span className="pi-finding-title">{finding.title}</span>
        {roleRelevant ? <span className="pi-finding-roletag">For your role</span> : null}
      </div>

      <p className="pi-finding-explain">{ex?.what || finding.explanation}</p>

      {ex ? (
        <>
          <p className="pi-finding-why">{ex.why_it_may_matter}</p>

          <div className="pi-finding-meta">
            {where ? (
              onInspectFile ? (
                <button
                  type="button"
                  className="pi-file-link"
                  title={`Inspect ${where}`}
                  onClick={() => onInspectFile(where)}
                >
                  {where}
                </button>
              ) : (
                <code className="pi-source">{where}</code>
              )
            ) : null}
            <span className="pi-finding-confidence">{ex.confidence_label}</span>
          </div>

          {ex.check_manually.length > 0 ? (
            <div className="pi-finding-check">
              <span className="pi-finding-label">What to check yourself</span>
              <ul className="pi-finding-checklist">
                {ex.check_manually.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {ex.suggested_idea ? (
            <p className="pi-finding-reco">
              <span className="pi-finding-label">Idea to consider</span>
              {ex.suggested_idea}
              <span className="pi-finding-reco-note"> — review, don’t auto-apply.</span>
            </p>
          ) : null}
        </>
      ) : (
        finding.recommendation && <p className="pi-finding-reco">{finding.recommendation}</p>
      )}

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
