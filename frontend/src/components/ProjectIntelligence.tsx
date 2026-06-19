import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildProjectIntelligence,
  getProjectIntelligence,
  getProjectIntelligenceOverviewText,
  getWorkspaceLatestScan,
} from "../api/client";
import type {
  ProjectGraphEntity,
  ProjectGraphFinding,
  ProjectIntelligenceResponse,
  ProjectIntelligenceView,
  WorkspaceDashboard,
} from "../api/types";

// Roles offered in the lens selector. The backend falls back to the developer
// lens for any other assistant_mode, so this list stays small and canonical.
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "developer", label: "Developer" },
  { value: "devops", label: "DevOps" },
  { value: "tester", label: "Tester / QA" },
  { value: "business_analyst", label: "Business analyst" },
];

const SECTION_LABELS: Record<string, string> = {
  summary: "Summary",
  infrastructure: "Infrastructure",
  deployment: "Deployment",
  environments: "Environments",
  risks: "Risks",
  important_files: "Important files",
  questions: "Questions for the team",
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

  const tabs = useMemo(() => {
    if (!view) return [];
    return view.section_order.filter((s) => TAB_SECTIONS.has(s));
  }, [view]);

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
            {activeTab === "deployment" ? <DeploymentSection view={view} /> : null}
            {activeTab === "environments" ? <EnvironmentsSection view={view} /> : null}
            {activeTab === "risks" ? <RisksSection view={view} /> : null}
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

      <div className="pi-counts">
        <Count label="Services" value={summary.counts.services} />
        <Count label="Environments" value={summary.counts.environments} />
        <Count label="Pipelines" value={summary.counts.pipelines} />
        <Count label="Infra tools" value={summary.counts.infrastructure} />
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

function InfrastructureSection({ view }: { view: ProjectIntelligenceView }) {
  const { components, images } = view.infrastructure;
  if (components.length === 0 && images.length === 0) {
    return <EmptyNote text="No infrastructure tooling was detected in this project." />;
  }
  return (
    <div className="pi-entity-groups">
      {components.length > 0 ? (
        <EntityList title="Infrastructure tools" entities={components} />
      ) : null}
      {images.length > 0 ? <EntityList title="Container images" entities={images} /> : null}
    </div>
  );
}

function DeploymentSection({ view }: { view: ProjectIntelligenceView }) {
  const { pipelines } = view.deployment;
  if (pipelines.length === 0) {
    return <EmptyNote text="No CI/CD pipelines were detected in this project." />;
  }
  return (
    <div className="pi-pipelines">
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

function EnvironmentsSection({ view }: { view: ProjectIntelligenceView }) {
  const { environments } = view.environments;
  if (environments.length === 0) {
    return (
      <EmptyNote text="No environments were detected from the project's directory structure." />
    );
  }
  return (
    <div>
      <p className="pi-muted pi-env-note">
        Environments are inferred from naming conventions — confirm them with your team.
      </p>
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
    </div>
  );
}

function RisksSection({ view }: { view: ProjectIntelligenceView }) {
  const { findings } = view.risks;
  if (findings.length === 0) {
    return <EmptyNote text="No risks were flagged by the deterministic analyzers." />;
  }
  return (
    <ul className="pi-findings">
      {findings.map((f) => (
        <FindingItem key={f.id} finding={f} />
      ))}
    </ul>
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

function EntityList({ title, entities }: { title: string; entities: ProjectGraphEntity[] }) {
  return (
    <div className="pi-entity-group">
      <p className="pi-eyebrow">{title}</p>
      <ul className="pi-entity-list">
        {entities.map((e) => {
          const note = statusNote(e);
          return (
            <li key={e.id} className="pi-entity">
              <span className="pi-entity-name">{e.name}</span>
              {note ? <span className="pi-entity-note">{note}</span> : null}
              {e.source_file ? <code className="pi-source">{e.source_file}</code> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="pi-count">
      <span className="pi-count-value">{value}</span>
      <span className="pi-count-label">{label}</span>
    </div>
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
