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

          {/* Working memory derived from the map — lives here, next to what it's
              built from, not on Home. Fed into every Ask/Investigate as background. */}
          <ProjectHandbook workspaceId={workspaceId} />
        </>
      ) : null}
    </section>
  );
}

