import { useEffect } from "react";

import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
  WorkspaceJob,
  FileSelectionPreview,
} from "../api/types";
import {
  countPatterns,
} from "./fileIndexingPreferences";
import { activateWorkspaceRuntime } from "../api/client";

import { WorkspaceGettingReady } from "./WorkspaceGettingReady";
import { ProjectMemory } from "./ProjectMemory";
import { ProjectUnderstanding } from "./ProjectUnderstanding";
import { ProjectWatch } from "./ProjectWatch";
import { StatusBadge } from "./StatusBadge";

import {
  getEnabledSkillPresets,
} from "./skillLibrary";

interface WorkspaceDashboardProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
  onOpenModels: () => void;
  onOpenCapabilities: () => void;
  onPreviewSavedFileSelection: () => Promise<FileSelectionPreview>;
  onPreviewDraftFileSelection: () => Promise<FileSelectionPreview>;
  onStartScanJob: () => Promise<WorkspaceJob>;
  onStartIndexJob: () => Promise<WorkspaceJob>;
  onGetWorkspaceJob: (jobId: string) => Promise<WorkspaceJob>;
  onListWorkspaceJobs: () => Promise<WorkspaceJob[]>;
  onCancelWorkspaceJob: (jobId: string) => Promise<WorkspaceJob>;
  onRefreshWorkspaceState: () => Promise<void>;
  onOpenSettings: () => void;
  onInspectFile?: (path: string) => void;
  // A fact on Home is the beginning of a question; this is how it finishes it.
  onAskQuestion?: (question: string) => void;
  skillPreferences: SkillPreferences;
  fileIndexingPreferences: FileIndexingPreferences;
}

export function WorkspaceDashboard({
  dashboard,
  modelsSummary,
  onOpenAsk,
  onAskQuestion,
  onOpenModels,
  onOpenCapabilities,
  onPreviewSavedFileSelection,
  onPreviewDraftFileSelection,
  onStartScanJob,
  onStartIndexJob,
  onGetWorkspaceJob,
  onListWorkspaceJobs,
  onCancelWorkspaceJob,
  onRefreshWorkspaceState,
  onOpenSettings,
  onInspectFile,
  skillPreferences,
  fileIndexingPreferences,
}: WorkspaceDashboardProps) {
  const summary = dashboard.summary;
  const indexStatus = summary.index_status;

  // The active model backend is app-global, so opening this workspace re-points
  // the engine/embeddings at the backend it uses (Ollama or llama.cpp), then
  // refreshes so readiness reflects the now-correct runtime. Without this,
  // switching between projects on different backends would leave the wrong
  // engine active and a set-up project would wrongly show the setup screen.
  // Best-effort; failures never block the dashboard.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await activateWorkspaceRuntime(dashboard.workspace_id);
        if (!cancelled) await onRefreshWorkspaceState();
      } catch {
        /* leave current state; the user can still act manually */
      }
    })();
    return () => {
      cancelled = true;
    };
    // Only re-run when the opened workspace changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboard.workspace_id]);
  // Readiness must be a STABLE, per-workspace fact — not tied to the app-global
  // active runtime (which flips when you switch projects). A project is ready
  // once it is scanned, indexed, and has both models chosen. Opening it
  // re-activates its engine separately, so Ask uses the right backend.
  const fullyReady =
    summary.has_scan &&
    indexStatus.status === "indexed" &&
    modelsSummary.selected_llm != null &&
    modelsSummary.selected_embedding != null;

  return (
    <>
      {!fullyReady ? (
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Workspace overview</p>
            <h1>{dashboard.workspace_name}</h1>
            <p className="workspace-header-path">{summary.project_path}</p>
          </div>
          <div className="workspace-header-status">
            <StatusBadge label={dashboard.status} size="md" />
            {/* No role until setup asks for one — don't render a bare "mode". */}
            {dashboard.assistant_mode ? (
              <span>{formatLabel(dashboard.assistant_mode)} mode</span>
            ) : null}
          </div>
        </header>
      ) : null}

      {fullyReady ? (
        // Home in the order the role reads it. A manager opening a project they have
        // seen before does not want to be re-introduced to it — they want to know what
        // moved since last time; everyone else wants the project first. The blocks are
        // the same blocks: the lens changes what leads, never what is true.
        <div className="home-stack" data-role={dashboard.assistant_mode ?? "developer"}>
          <ProjectUnderstanding
            dashboard={dashboard}
            projectPath={summary.project_path}
            onOpenAsk={onOpenAsk}
            onOpenSettings={onOpenSettings}
            onStartScanJob={onStartScanJob}
            onStartIndexJob={onStartIndexJob}
            onRefreshWorkspaceState={onRefreshWorkspaceState}
            onInspectFile={onInspectFile}
            onAskQuestion={onAskQuestion}
          />
          <ProjectWatch dashboard={dashboard} />
          <ProjectMemory dashboard={dashboard} />
        </div>
      ) : (
        <WorkspaceGettingReady
          dashboard={dashboard}
          modelsSummary={modelsSummary}
          onOpenAsk={onOpenAsk}
          onOpenModels={onOpenModels}
          onStartScanJob={onStartScanJob}
          onStartIndexJob={onStartIndexJob}
          onRefreshWorkspaceState={onRefreshWorkspaceState}
        />
      )}

      {!fullyReady ? (
        <details className="panel overview-advanced-disclosure">
          <summary>
            <div>
              <p className="eyebrow">Advanced</p>
              <h2>Project details and detected skills</h2>
              <span>Open only when you need to inspect file rules or skill guidance.</span>
            </div>
          </summary>
          <WorkspaceSkillsSection
            dashboard={dashboard}
            onOpenAsk={onOpenAsk}
            onOpenSettings={onOpenSettings}
            skillPreferences={skillPreferences}
          />
          <WorkspaceFilesSection
            dashboard={dashboard}
            fileIndexingPreferences={fileIndexingPreferences}
            onOpenSettings={onOpenSettings}
          />
        </details>
      ) : null}
    </>
  );
}






function WorkspaceSkillsSection({
  dashboard,
  onOpenAsk,
  onOpenSettings,
  skillPreferences,
}: {
  dashboard: WorkspaceDashboardData;
  onOpenAsk: () => void;
  onOpenSettings: () => void;
  skillPreferences: SkillPreferences;
}) {
  const summary = dashboard.summary;
  const activeSkillPresets = getEnabledSkillPresets(skillPreferences);
  const suggestedFocus = getAssistantFocus(dashboard.assistant_mode);

  return (
    <section className="adv-card">
      <div className="adv-card-head">
        <span className="adv-card-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" /></svg>
        </span>
        <div className="adv-card-title">
          <strong>Project lens</strong>
          <span>{suggestedFocus.title}</span>
        </div>
        <button className="adv-card-link" type="button" onClick={onOpenSettings}>
          Manage in Settings
        </button>
      </div>
      <p className="adv-card-desc">{suggestedFocus.description}</p>
      <div className="adv-card-facts">
        <span>
          <b>{summary.has_scan ? summary.detected_skills_count : "—"}</b> technologies detected
        </span>
        <span>
          <b>{activeSkillPresets.length}</b> skill preset(s) active
        </span>
      </div>
    </section>
  );
}

function getAssistantFocus(mode: string) {
  const focuses: Record<string, { title: string; description: string }> = {
    devops: {
      title: "DevOps and platform focus",
      description:
        "Answers prioritize infrastructure, CI/CD, runtime, cloud, containers, and operational setup.",
    },
    developer: {
      title: "Developer focus",
      description:
        "Answers prioritize application structure, implementation details, tests, and code navigation.",
    },
    documentation: {
      title: "Documentation focus",
      description:
        "Answers prioritize README files, architecture notes, onboarding context, and clear summaries.",
    },
    support_incident: {
      title: "Incident support focus",
      description:
        "Answers prioritize troubleshooting, symptoms, likely causes, operational context, and next checks.",
    },
    manager_summary: {
      title: "Manager summary focus",
      description:
        "Answers prioritize concise summaries, risks, progress, decisions, and stakeholder-friendly wording.",
    },
  };

  return focuses[mode] ?? focuses.devops;
}

function WorkspaceFilesSection({
  dashboard,
  fileIndexingPreferences,
  onOpenSettings,
}: {
  dashboard: WorkspaceDashboardData;
  fileIndexingPreferences: FileIndexingPreferences;
  onOpenSettings: () => void;
}) {
  const summary = dashboard.summary;
  const includeCount = countPatterns(fileIndexingPreferences.includePatterns);
  const excludeCount = countPatterns(fileIndexingPreferences.excludePatterns);
  const contextReady = summary.index_status.status === "indexed";
  const scanReady = summary.has_scan;

  return (
    <section className="adv-card">
      <div className="adv-card-head">
        <span className="adv-card-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8" /></svg>
        </span>
        <div className="adv-card-title">
          <strong>Files &amp; context</strong>
          <span>What gets searched</span>
        </div>
        <button className="adv-card-link" type="button" onClick={onOpenSettings}>
          Edit rules in Settings
        </button>
      </div>
      <p className="adv-card-desc">
        Defaults keep source, docs, and infrastructure files and skip generated or
        heavy folders. Rebuilding context is always an explicit action.
      </p>
      <div className="adv-card-facts">
        <span>
          <b>{includeCount}</b> include rule(s)
        </span>
        <span>
          <b>{excludeCount}</b> exclude rule(s)
        </span>
        <span className={`adv-card-status${contextReady ? " is-ready" : ""}`}>
          {contextReady
            ? "Context ready"
            : scanReady
              ? "Review, then build context"
              : "Scan first"}
        </span>
      </div>
    </section>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
