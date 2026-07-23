import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildProjectIntelligence,
  getProjectIntelligence,
  getProjectIntelligenceOverviewText,
  getWorkspaceLatestScan,
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
  ProjectIntelligenceOverviewText,
  ProjectIntelligenceResponse,
  ProjectIntelligenceSnapshot,
  ProjectIntelligenceView,
  ProjectReferences,
  RoleBrief,
  WorkspaceDashboard,
} from "../api/types";
import { analyzersThatFound, readFromClause } from "../lib/analyzerSources";
import { rescanLabel } from "../lib/rescanLabels";
import { ProjectHandbook } from "./ProjectHandbook";
import { ProjectMap } from "./ProjectMap";
import { ProjectWatchHistory } from "./ProjectWatchHistory";
import { SKILL_PRESETS } from "./skillLibrary";
import {
  checkStale,
  CicdFlowSection,
  CloudSection,
  DeploymentSection,
  EnvironmentsSection,
  DocumentsSection,
  FactsSection,
  InfrastructureSection,
  ReferencesSection,
  RisksSection,
  RoleDashboardBrief,
  SecuritySection,
  SummarySection,
} from "./ProjectIntelligenceSections";
import { SCANNER_RE, SECURITY_FINDING_RE } from "./projectIntelligenceShared";

// Roles offered in the lens selector. The backend falls back to the developer
// One canonical role list, shared with Settings skills and the create form, so
// the same five names appear everywhere. The backend lens folds any legacy
// assistant_mode onto the nearest of these.
const ROLE_OPTIONS: { value: string; label: string }[] = SKILL_PRESETS.map((preset) => ({
  value: preset.id,
  label: preset.name,
}));

// What the map will show you, promised in your own vocabulary. The old list named
// environments, pipelines and cloud services to everyone — so a tester was invited
// to build a map that, as advertised, contained nothing they had come for. Each
// role now leads with what its own analyzer finds; the map itself is unchanged.
const EMPTY_PREVIEW_BY_ROLE: Record<string, string[]> = {
  developer: ["Modules", "Dependencies", "Tests", "Config files", "Important files", "Risks"],
  devops: ["Environments", "Pipelines (CI/CD)", "Cloud services", "Deployment flow", "Risks"],
  tester: ["Test suites", "What runs them in CI", "Modules no test mentions", "Risks"],
  business_analyst: ["API endpoints", "Domain entities", "Services", "Integrations", "Risks"],
  manager: ["What changed recently", "Who owns what", "Environments", "Risks"],
  dba: ["Tables", "Relationships", "Migrations", "Indexes", "Risks"],
};

function emptyPreviewForRole(role: string): string[] {
  return EMPTY_PREVIEW_BY_ROLE[role] ?? EMPTY_PREVIEW_BY_ROLE.developer;
}

/** What a rebuild actually did, in one line.
 *
 * The map is rebuilt from the files, so on files that have not changed it comes back
 * identical — which is right, and which is why the button looked dead. A rebuild that
 * found nothing new should say so as plainly as one that found something. */
function rebuildNote(
  before: ProjectIntelligenceSnapshot | null | undefined,
  after: ProjectIntelligenceSnapshot,
): string {
  const delta = (now: number, then: number | undefined) =>
    then === undefined || now === then ? "" : now > then ? ` (+${now - then})` : ` (${now - then})`;
  const same =
    before !== null &&
    before !== undefined &&
    before.entity_count === after.entity_count &&
    before.relation_count === after.relation_count &&
    before.finding_count === after.finding_count;
  const counts =
    `${after.entity_count} things${delta(after.entity_count, before?.entity_count)}, ` +
    `${after.finding_count} risks${delta(after.finding_count, before?.finding_count)}`;
  // The analyzers really did run again, so "because the files have not changed" was a
  // cause we did not know: the totals can match while a finding's words have changed.
  // Report what came back and claim nothing about why.
  return same ? `Map rebuilt — same totals: ${counts}.` : `Map rebuilt — ${counts}.`;
}

// The "read from your …" clause now lives in lib/analyzerSources.ts, and lists
// the analyzers that FOUND something rather than the ones that ran — see the bug
// it fixes there.

const SECTION_LABELS: Record<string, string> = {
  summary: "Overview",
  documents: "Documents",
  code: "Code",
  tests: "Tests",
  data: "Data",
  api: "API",
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

// How many tabs a person can take in at a glance. Beyond this the row wraps, and a
// wrapped row of tabs is a wall. The lens decides which six; the rest go behind "More".
const TAB_LIMIT = 6;

const MAP_TAB = "map";
const CLOUD_TAB = "cloud";
const REFERENCES_TAB = "references";
const SECURITY_TAB = "security";
const CICD_TAB = "cicd";
const HISTORY_TAB = "history";



// Only these appear as sub-nav tabs; files/questions ride along inside Summary.
// The backend omits any section the project has no facts for, so a code repository
// never shows "Documents" and a wiki never shows "Infrastructure" — each project is
// offered the tabs it can actually fill.
const TAB_SECTIONS = new Set([
  "summary",
  "documents",
  "code",
  "tests",
  "data",
  "api",
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
  // A workspace whose role was never chosen shows the neutral developer lens here,
  // so the picker never renders blank.
  const [role, setRole] = useState<string>(dashboard.assistant_mode || "developer");
  const [activeTab, setActiveTab] = useState<string>("summary");
  const [stale, setStale] = useState(false);
  // The paths in the current scan, so a risk pointing at a file that has moved
  // out from under it can be marked rather than left asserting a stale path.
  // null until loaded — an unloaded scan is not evidence a file is gone.
  const [livePaths, setLivePaths] = useState<ReadonlySet<string> | null>(null);
  // What the last action actually did. Rebuilding an unchanged project produces an
  // identical map — the correct answer, and one that looked exactly like a button
  // that does nothing.
  const [note, setNote] = useState<string | null>(null);

  // The whole reply, not just the prose: who wrote it and from which analyzers' facts
  // are shown under it, and the paragraph is written for one role — so switching role
  // must throw it away rather than leave the developer's briefing under the DBA's tabs.
  const [overview, setOverview] = useState<ProjectIntelligenceOverviewText | null>(null);
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

  // The current scan's file paths, so a finding whose file has moved can be
  // marked. Best-effort: a failure just leaves livePaths null, which reads as
  // "unknown" everywhere and marks nothing.
  useEffect(() => {
    let cancelled = false;
    getWorkspaceLatestScan(workspaceId)
      .then((scan) => {
        if (!cancelled) setLivePaths(new Set((scan?.files ?? []).map((f) => f.path)));
      })
      .catch(() => {
        if (!cancelled) setLivePaths(null);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, data]);

  // Keep in sync if the role is changed elsewhere (e.g. Settings).
  useEffect(() => {
    setRole(dashboard.assistant_mode || "developer");
  }, [dashboard.assistant_mode]);

  // The role is changed in the header now, and this panel follows it: the effect above
  // syncs `role` from the workspace, and the load effect re-frames the map. The panel
  // no longer owns a copy of the setting — one setting, one home.
  useEffect(() => {
    // A paragraph written for one role is not stale under another, it is addressed to
    // someone else. Drop it when the lens changes.
    setOverview(null);
    setOverviewError(null);
  }, [role]);

  const handleBuild = useCallback(async () => {
    setBuilding(true);
    setError(null);
    setNote(null);
    setOverview(null);
    setOverviewError(null);
    const before = data?.snapshot ?? null;
    try {
      const built = await buildProjectIntelligence(workspaceId);
      await load(role);
      // Rebuilding a map that has not changed produces the same map — which is the
      // right answer and looked exactly like a dead button. Say what came back, and
      // say plainly when nothing moved: a silent success is indistinguishable from
      // a silent failure.
      setNote(rebuildNote(before, built.snapshot));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not build the project map.");
    } finally {
      setBuilding(false);
    }
  }, [workspaceId, role, load, data?.snapshot]);

  const handleOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const result = await getProjectIntelligenceOverviewText(workspaceId, role ?? undefined);
      setOverview(result);
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

  // "read from your …" must name the analyzers that FOUND something, not the
  // ones that ran — every analyzer runs on every project. Derived from the graph
  // nodes, which each carry the analyzer that produced them.
  const readFromFound = readFromClause(analyzersThatFound(graph?.nodes));

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
  // A security review is about pipelines, dependencies and infrastructure. A wiki has
  // none, and offering it the tab produced a page whose only content was advice to add
  // scanning to pipelines it does not have.
  const hasSecurity =
    (security.scanners.length > 0 || security.findings.length > 0) &&
    (view?.infrastructure.components.length ?? 0) +
      (view?.deployment.pipelines.length ?? 0) +
      (view?.code?.applications.length ?? 0) +
      (view?.code?.modules.length ?? 0) >
      0;

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

  // The first few tabs are the ones this role opens on; the rest live behind "More".
  // The active tab is always among the visible ones, even when it was chosen from the
  // drawer — a tab you are reading must not be hidden behind a menu.
  const moreRef = useRef<HTMLDetailsElement | null>(null);
  const { visibleTabs, overflowTabs } = useMemo(() => {
    if (tabs.length <= TAB_LIMIT + 1) return { visibleTabs: tabs, overflowTabs: [] as string[] };
    const head = tabs.slice(0, TAB_LIMIT);
    const tail = tabs.slice(TAB_LIMIT);
    if (tail.includes(activeTab)) {
      return {
        visibleTabs: [...head.slice(0, TAB_LIMIT - 1), activeTab],
        overflowTabs: tabs.filter((t) => !head.slice(0, TAB_LIMIT - 1).includes(t) && t !== activeTab),
      };
    }
    return { visibleTabs: head, overflowTabs: tail };
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
          {/* One role, one place to change it. The picker lived here as well as in the
              header, so the same setting had two homes and a person had to learn which
              one they were looking at. The header owns it — the role is a property of
              you on this project, not of this tab. What belongs here is only the fact
              of it: which lens you are reading through. */}
          <span className="pi-role-note" title="Change your role in the header, next to the project name.">
            Viewed for {ROLE_OPTIONS.find((o) => o.value === role)?.label ?? role}
          </span>
          {/* Rebuild used to sit here beside the role, as though the two were a pair —
              so changing role and pressing it looked like one action that did nothing.
              They are unrelated: a role is a lens over the map that is already built,
              a rebuild re-reads the files. The button now appears only when it has
              something to do: when the files have changed (the banner below), or
              quietly in the provenance line for a map you want re-read anyway. */}
          {data?.built && building ? <span className="pi-working">Rebuilding…</span> : null}
        </div>
      </header>

      {error ? <p className="pi-error">{error}</p> : null}
      {note && !error ? (
        <p className="pi-note" role="status">
          {note}
        </p>
      ) : null}

      {loading && !data ? (
        <p className="pi-muted">Loading…</p>
      ) : !data?.built ? (
        <div className="pi-empty">
          <p className="pi-empty-lead">No project map yet.</p>
          <p className="pi-muted">
            Build a deterministic map of what this project is made of — code, tests, data,
            infrastructure — and the risks in it. Nothing runs and no files are changed.
          </p>
          <p className="pi-empty-preview-lead">Once built, it surfaces things like:</p>
          <ul className="pi-empty-preview" aria-hidden="true">
            {emptyPreviewForRole(role).map((label) => (
              <li className="pi-empty-preview-item" key={label}>
                <span className="pi-empty-preview-dot" />
                {label}
              </li>
            ))}
          </ul>
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

          {/* The list of analyzers that found nothing is a list of things this project
              is not. On a folder of documentation that is every analyzer we have, and
              reading it feels like a verdict. Say what WAS analyzed instead. */}
          <p className="pi-built-meta">
            {data.snapshot ? `Last analyzed ${relativeTime(data.snapshot.created_at)}` : ""}
            {readFromFound ? ` · read from your ${readFromFound}` : ""}
            {" · "}
            {/* The rebuild lives here, in the line that says how old the map is —
                next to the only fact that makes a person want it. */}
            <button type="button" className="pi-link" onClick={handleBuild} disabled={building}>
              {rescanLabel(building)}
            </button>
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

          {/* A rich repository has fourteen sections, and fourteen tabs wrap onto two
              rows — at which point a row of tabs stops being a place and becomes a
              wall. The lens already knows which come first; the rest are one click
              away and not one section is lost. The tab you are on is always visible,
              even when it came from the drawer. */}
          <nav className="pi-tabs" role="tablist">
            {visibleTabs.map((tab) => (
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
            {overflowTabs.length > 0 ? (
              <details className="pi-tab-more" ref={moreRef}>
                <summary className="pi-tab">More ({overflowTabs.length})</summary>
                <div className="pi-tab-menu">
                  {overflowTabs.map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      className="pi-tab-menu-item"
                      onClick={() => {
                        setActiveTab(tab);
                        moreRef.current?.removeAttribute("open");
                      }}
                    >
                      {SECTION_LABELS[tab] ?? tab}
                    </button>
                  ))}
                </div>
              </details>
            ) : null}
          </nav>

          {/* key={activeTab} remounts the panel so the enter fade plays on every
              tab switch — content stops "snapping" between tabs. */}
          <div className="pi-section" key={activeTab}>
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
            {activeTab === "documents" ? <DocumentsSection view={view} onInspectFile={onInspectFile} /> : null}
            {activeTab === "code" || activeTab === "tests" || activeTab === "data" || activeTab === "api" ? (
              <FactsSection view={view} section={activeTab} onInspectFile={onInspectFile} />
            ) : null}
            {activeTab === "infrastructure" ? <InfrastructureSection view={view} /> : null}
            {activeTab === "deployment" ? (
              <DeploymentSection view={view} flow={flow} ci={ci} />
            ) : null}
            {activeTab === "environments" ? (
              <EnvironmentsSection view={view} comparison={comparison} />
            ) : null}
            {activeTab === "risks" ? (
              <RisksSection
                view={view}
                livePaths={livePaths}
                onInspectFile={onInspectFile}
                onAskQuestion={onAskQuestion}
              />
            ) : null}
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

          {/* Working memory derived from the map — lives here, next to what it's
              built from, not on Home. Fed into every Ask/Investigate as background. */}
          <ProjectHandbook workspaceId={workspaceId} />
        </>
      ) : null}
    </section>
  );
}

