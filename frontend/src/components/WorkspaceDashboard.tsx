import { useEffect, useRef, useState } from "react";

import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
  WorkspaceJob,
  FileSelectionPreview,
} from "../api/types";
import {
  countPatterns,
  patternLines,
  type FileIndexingPreferences,
} from "./fileIndexingPreferences";
import { activateWorkspaceRuntime } from "../api/client";
import { ModelsSummaryCard } from "./ModelsSummaryCard";
import { WorkspaceGettingReady } from "./WorkspaceGettingReady";
import { ProjectIntelligence } from "./ProjectIntelligence";
import { ProjectMemory } from "./ProjectMemory";
import { ProjectUnderstanding } from "./ProjectUnderstanding";
import { ProjectWatch } from "./ProjectWatch";
import { StatusBadge } from "./StatusBadge";
import type { StatusTone } from "./statusTone";
import {
  getEnabledSkillPresets,
  getSkillPresetByAssistantMode,
  type SkillPreferences,
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
  skillPreferences: SkillPreferences;
  fileIndexingPreferences: FileIndexingPreferences;
}

export function WorkspaceDashboard({
  dashboard,
  modelsSummary,
  onOpenAsk,
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
            <span>{formatLabel(dashboard.assistant_mode)} mode</span>
          </div>
        </header>
      ) : null}

      {fullyReady ? (
        <>
          <ProjectUnderstanding
            dashboard={dashboard}
            projectPath={summary.project_path}
            onOpenAsk={onOpenAsk}
            onOpenSettings={onOpenSettings}
            onStartScanJob={onStartScanJob}
            onStartIndexJob={onStartIndexJob}
            onRefreshWorkspaceState={onRefreshWorkspaceState}
          />
          <ProjectIntelligence dashboard={dashboard} />
          <ProjectWatch dashboard={dashboard} />
          <ProjectMemory dashboard={dashboard} />
        </>
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


function DailyUseStatusPanel({
  dashboard,
  modelsSummary,
  onOpenAsk,
  onOpenModels,
  onOpenCapabilities,
  onStartScan,
  onStartIndex,
}: {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
  onOpenModels: () => void;
  onOpenCapabilities: () => void;
  onStartScan: () => void;
  onStartIndex: () => void;
}) {
  const summary = dashboard.summary;
  const hasScan = summary.has_scan;
  const indexReady = summary.index_status.status === "indexed";
  const embeddingReady = modelsSummary.can_search_with_selected_embedding;
  const llmReady = modelsSummary.can_ask_with_selected_llm;
  const readyToUse = hasScan && embeddingReady && indexReady && llmReady;
  const nextAction = getDailyUseNextAction({
    hasScan,
    embeddingReady,
    indexReady,
    llmReady,
  });
  const [confirming, setConfirming] = useState<"scan" | "index" | null>(null);
  const [starting, setStarting] = useState<"scan" | "index" | null>(null);

  function handlePrimaryAction() {
    if (nextAction.id === "scan" || nextAction.id === "index") {
      setConfirming(nextAction.id);
      return;
    }
    if (nextAction.id === "models") {
      onOpenModels();
      return;
    }
    onOpenAsk();
  }

  function confirmStart() {
    const action = confirming;
    setConfirming(null);
    if (action === "scan") {
      onStartScan();
    } else if (action === "index") {
      onStartIndex();
    }
    if (action) {
      setStarting(action);
      window.setTimeout(() => setStarting(null), 6000);
    }
  }

  return (
    <section className={readyToUse ? "panel daily-use-panel is-ready" : "panel daily-use-panel"}>
      <div className="daily-use-main">
        <div>
          <p className="eyebrow">Use it now</p>
          <h2>{readyToUse ? "Workspace is ready for questions" : "Next step to make this workspace usable"}</h2>
          <p>{nextAction.description}</p>
        </div>
        <div className="daily-use-actions">
          {starting ? (
            <span className="daily-use-confirm-label">
              {starting === "scan"
                ? "Scan started — this updates when it finishes…"
                : "Building context — this updates when it finishes…"}
            </span>
          ) : confirming ? (
            <>
              <span className="daily-use-confirm-label">
                {confirming === "scan"
                  ? "Scan this project now?"
                  : "Build search context now?"}
              </span>
              <button className="overview-cta-button" type="button" onClick={confirmStart}>
                {confirming === "scan" ? "Confirm scan" : "Confirm build"}
              </button>
              <button className="secondary-action" type="button" onClick={() => setConfirming(null)}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <button className="overview-cta-button" type="button" onClick={handlePrimaryAction}>
                {nextAction.label}
              </button>
              <button className="secondary-action" type="button" onClick={onOpenModels}>
                Check models
              </button>
            </>
          )}
        </div>
      </div>

      <div className="daily-use-checklist" aria-label="Workspace setup steps">
        <DailyUseCheck label="1 · Scan project" ready={hasScan} detail={hasScan ? `${summary.detected_skills_count} skill(s) found` : "Lists your files"} />
        <DailyUseCheck label="2 · Search model" ready={embeddingReady} detail={embeddingReady ? (modelsSummary.selected_embedding ?? "Ready") : "Pick & install"} />
        <DailyUseCheck label="3 · Search context" ready={indexReady} detail={indexReady ? `${summary.index_status.chunks_count} chunk(s) indexed` : embeddingReady ? "Ready to build" : "Needs search model"} />
        <DailyUseCheck label="4 · Answer model" ready={llmReady} detail={llmReady ? (modelsSummary.selected_llm ?? "Ready") : "Pick & install"} />
      </div>

      {!readyToUse ? (
        <div className="daily-use-help">
          <span>No hidden automation.</span>
          <p>Scan, index, and Ask still start only after your click. Open Capabilities for deeper checks.</p>
          <button className="text-button" type="button" onClick={onOpenCapabilities}>
            View capabilities
          </button>
        </div>
      ) : null}
    </section>
  );
}

function DailyUseCheck({ label, ready, detail }: { label: string; ready: boolean; detail: string }) {
  return (
    <article className={ready ? "daily-use-check is-ready" : "daily-use-check"}>
      <StatusBadge label={ready ? "ready" : "needs action"} tone={ready ? "success" : "warning"} />
      <div>
        <strong>{label}</strong>
        <span>{detail}</span>
      </div>
    </article>
  );
}

function getDailyUseNextAction({
  hasScan,
  embeddingReady,
  indexReady,
  llmReady,
}: {
  hasScan: boolean;
  embeddingReady: boolean;
  indexReady: boolean;
  llmReady: boolean;
}) {
  // Order matters: each step unlocks the next. Indexing needs a search model,
  // so the search model must be set up before "Build search context".
  if (!hasScan) {
    return {
      id: "scan",
      label: "Scan project",
      description:
        "A safe local scan — it just lists the project's files (skipping junk like node_modules) so the app knows what it can search. Nothing leaves your computer.",
    };
  }
  if (!embeddingReady) {
    return {
      id: "models",
      label: "Set up the search model",
      description:
        "Indexing turns your files into searchable context, which needs a small search (embedding) model. Pick and install it in Models first.",
    };
  }
  if (!indexReady) {
    return {
      id: "index",
      label: "Build search context",
      description:
        "Turn the scanned files into searchable local context with your search model, so Ask can find the right sources.",
    };
  }
  if (!llmReady) {
    return {
      id: "models",
      label: "Set up the answer model",
      description:
        "Pick (and install) the local AI model this project uses to actually answer your questions.",
    };
  }
  return {
    id: "ask",
    label: "Ask this workspace",
    description:
      "Everything is ready. Ask uses your local context and keeps sources attached.",
  };
}

function WorkspaceOnboardingGuide({
  dashboard,
  modelsSummary,
  onOpenAsk,
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
  fileIndexingPreferences,
  externalSetupRequest,
}: {
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
  fileIndexingPreferences: FileIndexingPreferences;
  externalSetupRequest?: { action: "scan" | "index"; nonce: number } | null;
}) {
  const summary = dashboard.summary;
  const hasScan = summary.has_scan;
  const indexReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
  const embeddingReady = modelsSummary.can_search_with_selected_embedding;
  const llmReady = modelsSummary.can_ask_with_selected_llm;
  const readyToAsk = hasScan && indexReady && localAIReady;
  const includeRuleCount = countPatterns(
    fileIndexingPreferences.includePatterns,
  );
  const excludeRuleCount = countPatterns(
    fileIndexingPreferences.excludePatterns,
  );
  const includePreview = patternLines(
    fileIndexingPreferences.includePatterns,
  ).slice(0, 4);
  const excludePreview = patternLines(
    fileIndexingPreferences.excludePatterns,
  ).slice(0, 4);
  const [setupAction, setSetupAction] = useState<"scan" | "index" | null>(null);
  const [setupJob, setSetupJob] = useState<WorkspaceJob | null>(null);
  const [jobHistory, setJobHistory] = useState<WorkspaceJob[]>([]);
  const [jobHistoryError, setJobHistoryError] = useState<string | null>(null);
  const [setupMessage, setSetupMessage] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState<FileSelectionPreview | null>(null);
  const [filePreviewLoading, setFilePreviewLoading] = useState(false);
  const [filePreviewError, setFilePreviewError] = useState<string | null>(null);
  const [filePreviewOpen, setFilePreviewOpen] = useState(false);
  const [filePreviewMode, setFilePreviewMode] = useState<"saved" | "draft" | null>(null);
  const [confirmationAction, setConfirmationAction] = useState<"scan" | "index" | null>(null);
  const [stepsOpen, setStepsOpen] = useState(false);
  const pollingJobIdRef = useRef<string | null>(null);
  const lastSeenSetupJobRef = useRef<string | null | undefined>(undefined);

  async function refreshJobHistory() {
    setJobHistoryError(null);
    try {
      setJobHistory(await onListWorkspaceJobs());
    } catch (error) {
      setJobHistoryError(
        error instanceof Error ? error.message : "Could not load background jobs.",
      );
    }
  }

  async function previewFiles(mode: "saved" | "draft") {
    setFilePreviewLoading(true);
    setFilePreviewError(null);
    setFilePreviewOpen(true);
    setFilePreviewMode(mode);
    try {
      setFilePreview(
        mode === "saved"
          ? await onPreviewSavedFileSelection()
          : await onPreviewDraftFileSelection(),
      );
    } catch (error) {
      setFilePreviewError(
        error instanceof Error
          ? error.message
          : "Could not preview file selection.",
      );
    } finally {
      setFilePreviewLoading(false);
    }
  }

  async function requestSetupAction(action: "scan" | "index") {
    setConfirmationAction(action);
    setSetupError(null);
    setSetupMessage(null);
    await previewFiles("saved");
  }

  function clearSetupConfirmation() {
    setConfirmationAction(null);
  }

  async function runSetupAction(action: "scan" | "index") {
    setConfirmationAction(null);
    setSetupAction(action);
    setSetupJob(null);
    setSetupMessage(null);
    setSetupError(null);
    try {
      const job =
        action === "scan" ? await onStartScanJob() : await onStartIndexJob();
      setSetupJob(job);
      setJobHistory((current) => [job, ...current.filter((item) => item.job_id !== job.job_id)].slice(0, 8));
      pollingJobIdRef.current = job.job_id;
    } catch (error) {
      setSetupAction(null);
      setSetupError(
        error instanceof Error
          ? error.message
          : action === "scan"
            ? "Could not start project scan."
            : "Could not start search context build.",
      );
    }
  }

  async function cancelSetupAction() {
    if (!setupJob) {
      return;
    }
    try {
      const cancelledJob = await onCancelWorkspaceJob(setupJob.job_id);
      setSetupJob(cancelledJob);
      setJobHistory((current) => [cancelledJob, ...current.filter((item) => item.job_id !== cancelledJob.job_id)].slice(0, 8));
      setSetupMessage("Cancellation requested for this backend job.");
    } catch (error) {
      setSetupError(
        error instanceof Error ? error.message : "Could not cancel this job.",
      );
    }
  }

  useEffect(() => {
    if (
      !setupJob ||
      ["completed", "failed", "cancelled"].includes(setupJob.status)
    ) {
      return;
    }

    let cancelled = false;
    const intervalId = window.setInterval(async () => {
      try {
        const latestJob = await onGetWorkspaceJob(setupJob.job_id);
        if (cancelled || pollingJobIdRef.current !== setupJob.job_id) {
          return;
        }
        setSetupJob(latestJob);
        setJobHistory((current) => [latestJob, ...current.filter((item) => item.job_id !== latestJob.job_id)].slice(0, 8));
        if (["completed", "failed", "cancelled"].includes(latestJob.status)) {
          window.clearInterval(intervalId);
          pollingJobIdRef.current = null;
          setSetupAction(null);
          if (latestJob.status === "completed") {
            setSetupMessage(
              latestJob.job_type === "scan"
                ? "Project scan finished. Review the detected technologies, then build search context."
                : "Search context is ready. You can now ask source-backed questions.",
            );
            await onRefreshWorkspaceState();
          } else if (latestJob.status === "cancelled") {
            setSetupMessage("Backend job cancelled.");
          } else {
            setSetupError(latestJob.error ?? "Backend job failed.");
          }
        }
      } catch (error) {
        if (!cancelled) {
          setSetupError(
            error instanceof Error
              ? error.message
              : "Could not refresh job status.",
          );
        }
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [onGetWorkspaceJob, onRefreshWorkspaceState, setupJob]);

  useEffect(() => {
    void refreshJobHistory();
  }, []);

  // Adopt a scan/index job started elsewhere (e.g. the "Use it now" panel) so
  // its progress is visible here and the steps panel expands automatically.
  useEffect(() => {
    let cancelled = false;
    const adoptRunningJob = async () => {
      if (pollingJobIdRef.current) {
        return;
      }
      try {
        const jobs = await onListWorkspaceJobs();
        if (cancelled) {
          return;
        }
        const latestSetup = jobs.find(
          (job) => job.job_type === "scan" || job.job_type === "index",
        );
        // Refresh the dashboard once when a new setup job has finished, even if
        // it completed too fast to be caught while running.
        if (latestSetup) {
          if (lastSeenSetupJobRef.current === undefined) {
            lastSeenSetupJobRef.current = latestSetup.job_id;
          } else if (
            latestSetup.job_id !== lastSeenSetupJobRef.current &&
            latestSetup.status === "completed"
          ) {
            lastSeenSetupJobRef.current = latestSetup.job_id;
            void onRefreshWorkspaceState();
          }
        }
        if (pollingJobIdRef.current) {
          return;
        }
        const running =
          latestSetup &&
          !["completed", "failed", "cancelled"].includes(latestSetup.status)
            ? latestSetup
            : undefined;
        if (running) {
          pollingJobIdRef.current = running.job_id;
          setSetupJob(running);
          setSetupAction(running.job_type === "scan" ? "scan" : "index");
          setStepsOpen(true);
        }
      } catch {
        // best-effort: never break the dashboard over a polling hiccup
      }
    };
    void adoptRunningJob();
    const intervalId = window.setInterval(() => void adoptRunningJob(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [onListWorkspaceJobs, onRefreshWorkspaceState]);

  // When the "Use it now" panel asks to scan/index, open the steps and run the
  // guided flow (file preview + confirm) instead of a silent direct start.
  useEffect(() => {
    if (!externalSetupRequest) {
      return;
    }
    setStepsOpen(true);
    void requestSetupAction(externalSetupRequest.action);
    // Only react to a new request (nonce), not to identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalSetupRequest?.nonce]);

  useEffect(() => {
    if (setupAction) {
      setStepsOpen(true);
    }
  }, [setupAction]);

  return (
    <details
      className="panel onboarding-guide-panel"
      open={stepsOpen}
      onToggle={(event) =>
        setStepsOpen((event.currentTarget as HTMLDetailsElement).open)
      }
    >
      <summary className="onboarding-guide-summary">
        <span className="eyebrow">Setup activity &amp; files</span>
        <span className="onboarding-guide-summary-title">
          Live scan/index progress, background jobs, and which files are included
        </span>
      </summary>
      <div className="onboarding-guide-heading">
        <span className="onboarding-safety-note">
          Run steps from “Use it now” above. This shows live progress and details.
        </span>
        {setupAction ? (
          <button
            className="secondary-action"
            type="button"
            onClick={cancelSetupAction}
          >
            Cancel job
          </button>
        ) : null}
      </div>

      {setupJob && !["completed", "failed", "cancelled"].includes(setupJob.status) ? (
        <div className="workspace-job-status" role="status">
          <div className="workspace-job-main">
            <span>{formatLabel(setupJob.job_type)}</span>
            <strong>{setupJob.title}</strong>
            <p>{setupJob.message ?? "Running..."}</p>
            <JobProgress job={setupJob} />
            {setupJob.cancellation_requested ? (
              <p>Stopping when the backend reaches a safe checkpoint...</p>
            ) : null}
          </div>
          <StatusBadge label={setupJob.status} />
          <button
            className="secondary-action"
            type="button"
            onClick={cancelSetupAction}
            disabled={setupJob.cancellation_requested}
          >
            {setupJob.cancellation_requested ? "Stopping..." : "Cancel job"}
          </button>
        </div>
      ) : null}

      {setupMessage ? (
        <p className="settings-message success">{setupMessage}</p>
      ) : null}
      {setupError ? (
        <p className="settings-message error">{setupError}</p>
      ) : null}

      <BackgroundJobsPanel
        jobs={jobHistory}
        error={jobHistoryError}
        onRefresh={() => void refreshJobHistory()}
      />

      <details className="file-rules-plan file-rules-disclosure" aria-label="File selection plan">
        <summary>
          <div>
            <strong>Files included in scan and context</strong>
            <p>Open only to verify which files are scanned and indexed.</p>
          </div>
          <span>{includeRuleCount} include · {excludeRuleCount} exclude</span>
        </summary>
        <div className="file-rules-plan-grid">
          <div>
            <span>{includeRuleCount} include rules</span>
            <code>{includePreview.join(" · ") || "All files"}</code>
          </div>
          <div>
            <span>{excludeRuleCount} exclude rules</span>
            <code>{excludePreview.join(" · ") || "No exclusions"}</code>
          </div>
        </div>
        <div className="file-rules-plan-actions">
          <button
            className="secondary-action"
            type="button"
            onClick={() => void previewFiles("saved")}
            disabled={filePreviewLoading}
          >
            {filePreviewLoading && filePreviewMode === "saved" ? "Previewing..." : "Preview saved rules"}
          </button>
          <button
            className="secondary-action"
            type="button"
            onClick={() => void previewFiles("draft")}
            disabled={filePreviewLoading}
          >
            {filePreviewLoading && filePreviewMode === "draft" ? "Previewing..." : "Preview draft rules"}
          </button>
          {filePreview ? (
            <button
              className="text-button"
              type="button"
              onClick={() => setFilePreviewOpen((current) => !current)}
            >
              {filePreviewOpen ? "Hide preview" : "Show preview"}
            </button>
          ) : null}
        </div>
        {filePreviewError ? (
          <p className="settings-message error">{filePreviewError}</p>
        ) : null}
        {filePreview && filePreviewOpen ? (
          <FileSelectionPreviewPanel
            preview={filePreview}
            title={filePreviewMode === "draft" ? "Draft rules preview" : "Saved rules preview"}
          />
        ) : null}
      </details>
    </details>
  );
}


function BackgroundJobsPanel({
  jobs,
  error,
  onRefresh,
}: {
  jobs: WorkspaceJob[];
  error: string | null;
  onRefresh: () => void;
}) {
  const visibleJobs = jobs.slice(0, 6);

  return (
    <div className="background-jobs-panel" aria-label="Background jobs">
      <div className="background-jobs-heading">
        <div>
          <p className="eyebrow">Background jobs</p>
          <h3>Scan and context build history</h3>
          <p>Track local long-running operations without leaving this workspace.</p>
        </div>
        <button className="text-button" type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      {error ? <p className="settings-message error">{error}</p> : null}
      {visibleJobs.length === 0 ? (
        <p className="background-jobs-empty">No background jobs yet.</p>
      ) : (
        <div className="background-jobs-list">
          {visibleJobs.map((job) => (
            <article className="background-job-item" key={job.job_id}>
              <div>
                <strong>{job.title}</strong>
                <p>{job.message ?? job.error ?? "No job message."}</p>
                <JobRuleSummary job={job} />
                <JobProgress job={job} compact />
              </div>
              <div className="background-job-meta">
                <StatusBadge label={job.status} />
                <span>{formatJobDuration(job)}</span>
                <span>{formatJobTime(job)}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}


function JobRuleSummary({ job }: { job: WorkspaceJob }) {
  const profile = job.request_summary.file_rules_profile;
  const includeCount = job.request_summary.include_rules_count;
  const excludeCount = job.request_summary.exclude_rules_count;

  if (!profile && !includeCount && !excludeCount) {
    return null;
  }

  return (
    <p className="background-job-rules">
      Rules: {profile ?? "latest scan"}
      {includeCount ? ` · include ${includeCount}` : ""}
      {excludeCount ? ` · exclude ${excludeCount}` : ""}
    </p>
  );
}

function JobProgress({ job, compact = false }: { job: WorkspaceJob; compact?: boolean }) {
  const percent = job.progress_percent ?? null;
  const hasProgress = percent !== null || job.progress_current !== null || job.progress_total !== null;

  if (!hasProgress) {
    return null;
  }

  const value = Math.max(0, Math.min(100, percent ?? 0));
  const label = progressLabel(job);

  return (
    <div className={compact ? "job-progress is-compact" : "job-progress"}>
      <div className="job-progress-label">
        <span>{job.current_step ? formatLabel(job.current_step) : "Progress"}</span>
        <span>{label}</span>
      </div>
      <div className="job-progress-track" aria-hidden="true">
        <span style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function progressLabel(job: WorkspaceJob): string {
  const parts: string[] = [];
  if (job.progress_current !== null && job.progress_total !== null) {
    parts.push(`${job.progress_current}/${job.progress_total}`);
  }
  if (job.progress_percent !== null) {
    parts.push(`${job.progress_percent}%`);
  }
  return parts.join(" · ") || "In progress";
}

function formatJobDuration(job: WorkspaceJob): string {
  if (job.duration_ms === null) {
    return job.status === "running" ? "Running" : "—";
  }
  if (job.duration_ms < 1000) {
    return `${job.duration_ms} ms`;
  }
  return `${(job.duration_ms / 1000).toFixed(1)}s`;
}

function formatJobTime(job: WorkspaceJob): string {
  const timestamp = job.completed_at ?? job.started_at ?? job.created_at;
  return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}



function JobConfirmationPanel({
  action,
  preview,
  loading,
  onCancel,
  onConfirm,
}: {
  action: "scan" | "index";
  preview: FileSelectionPreview | null;
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const actionLabel = action === "scan" ? "Scan project" : "Build search context";
  const description =
    action === "scan"
      ? "This will read matching local files through the backend and update detected project skills."
      : "This will rebuild searchable context from the files selected by saved workspace rules.";

  return (
    <div className="job-confirmation-panel" role="alertdialog" aria-label={`Confirm ${actionLabel}`}>
      <div>
        <p className="eyebrow">Confirm manual action</p>
        <h3>{actionLabel} with saved rules?</h3>
        <p>{description}</p>
        <span className="onboarding-safety-note">
          Nothing starts automatically. Confirm only when the preview looks correct.
        </span>
      </div>
      <div className="job-confirmation-stats">
        <div>
          <span>Included</span>
          <strong>{loading ? "…" : preview?.included_files_count ?? "—"}</strong>
        </div>
        <div>
          <span>Excluded</span>
          <strong>{loading ? "…" : preview?.excluded_files_count ?? "—"}</strong>
        </div>
        <div>
          <span>Rules</span>
          <strong>
            {loading
              ? "…"
              : preview
                ? `${preview.include_rules_count}/${preview.exclude_rules_count}`
                : "—"}
          </strong>
        </div>
      </div>
      <div className="job-confirmation-actions">
        <button className="primary-action" type="button" onClick={onConfirm} disabled={loading || !preview}>
          Confirm and start
        </button>
        <button className="secondary-action" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function FileSelectionPreviewPanel({
  preview,
  title = "File selection preview",
}: {
  preview: FileSelectionPreview;
  title?: string;
}) {
  return (
    <div className="file-preview-panel">
      <div className="file-preview-heading">
        <strong>{title}</strong>
        <span>{preview.profile} profile · saved workspace rules are used for scan/index unless you save a new draft.</span>
      </div>
      <div className="file-preview-summary">
        <div>
          <span>Included</span>
          <strong>{preview.included_files_count}</strong>
        </div>
        <div>
          <span>Excluded</span>
          <strong>{preview.excluded_files_count}</strong>
        </div>
        <div>
          <span>Skipped</span>
          <strong>{preview.skipped_files_count}</strong>
        </div>
      </div>
      <div className="file-preview-columns">
        <FilePreviewList
          title="Included samples"
          emptyText="No files matched the current include rules."
          items={preview.included_samples}
        />
        <FilePreviewList
          title="Excluded samples"
          emptyText="No files were excluded by the current rules."
          items={preview.excluded_samples}
        />
      </div>
    </div>
  );
}

function FilePreviewList({
  title,
  emptyText,
  items,
}: {
  title: string;
  emptyText: string;
  items: FileSelectionPreview["included_samples"];
}) {
  return (
    <div className="file-preview-list">
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul>
          {items.map((item) => (
            <li key={`${item.decision}-${item.path}`}>
              <code>{item.path}</code>
              <span>
                {item.reason}
                {item.matched_rule ? `: ${item.matched_rule}` : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p>{emptyText}</p>
      )}
    </div>
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

function getWorkspaceSkillCards(
  mode: string,
  detectedCount: number,
  hasScan: boolean,
  skillPreferences: SkillPreferences,
) {
  if (!hasScan) {
    return [
      {
        icon: "1",
        title: "Scan project first",
        description:
          "Run a project scan to detect languages, infrastructure files, CI/CD, and documentation signals.",
        hint: "Setup step",
      },
      {
        icon: "2",
        title: "Choose a focus",
        description:
          "The current assistant mode gives answers a starting lens before deeper skill customization is available.",
        hint: "Assistant mode",
      },
      {
        icon: "3",
        title: "Build context",
        description:
          "After scan, build searchable local context so answers can cite source files.",
        hint: "Source-backed answers",
      },
    ];
  }

  const activePresets = getEnabledSkillPresets(skillPreferences);
  const activeNames =
    activePresets.map((preset) => preset.name).join(", ") ||
    "No custom skills enabled";
  const currentPreset = getSkillPresetByAssistantMode(mode);
  const currentPreference = skillPreferences[currentPreset.id];

  const base = [
    {
      icon: "⌘",
      title: "Detected project skills",
      description: `${detectedCount} technology signals are available from the latest scan.`,
      hint: "From local scan",
    },
    {
      icon: "↳",
      title: "Active skill presets",
      description: activeNames,
      hint: "Browser-local",
    },
    {
      icon: "✎",
      title: "Custom instructions",
      description: currentPreference?.customInstructions
        ? `${currentPreset.name} has editable instructions ready for future prompt integration.`
        : "Use Settings to tune how each skill should frame answers.",
      hint: "Editable",
    },
  ];

  return [
    ...base,
    {
      icon: "★",
      title: `${currentPreset.name} preset`,
      description: currentPreset.bestFor,
      hint: currentPreference?.enabled ? "Active preset" : "Available preset",
    },
  ];
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
  const experimentsSeen = dashboard.recent_events.some(
    (event) =>
      event.event_type.toLowerCase().includes("experiment") ||
      event.title.toLowerCase().includes("model"),
  );

  const statuses: Array<{
    title: string;
    description: string;
    badge: string;
    tone: StatusTone;
  }> = [
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
      description:
        "Workspace actions stay explicit. The frontend never runs shell commands.",
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
            Ask local questions with visible sources. Model comparison and
            technical setup stay optional.
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
        <button
          className="overview-cta-button"
          type="button"
          onClick={onOpenAsk}
        >
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
  const guidance = getLocalAISetupGuidance(summary);

  return (
    <section className="panel local-ai-setup-warning">
      <div className="local-ai-setup-warning-heading">
        <div>
          <p className="eyebrow">AI setup</p>
          <h2>{guidance.title}</h2>
          <p>{guidance.description}</p>
        </div>
        <StatusBadge label={guidance.badge} size="md" />
      </div>

      <div className="local-ai-runtime-comparison">
        <ModelComparisonRow
          label="AI answer model"
          selected={summary.selected_llm}
          active={summary.active_llm}
        />
        <ModelComparisonRow
          label="Search context model"
          selected={summary.selected_embedding}
          active={summary.active_embedding}
        />
      </div>

      {guidance.message ? (
        <p className="local-ai-setup-message">{guidance.message}</p>
      ) : null}

      <div className="local-ai-setup-action">
        <button
          className="secondary-action"
          type="button"
          onClick={onOpenModels}
        >
          {guidance.actionTitle}
        </button>
      </div>
    </section>
  );
}

function getLocalAISetupGuidance(summary: WorkspaceModelsDashboardSummary) {
  if (summary.overall_status === "needs_context_index") {
    return {
      title: "Build context for this workspace",
      description:
        "The search model is selected and matches the backend. Build searchable context once so Ask can use local sources.",
      badge: "Needs context build",
      message:
        summary.embedding_index_status === "not_indexed"
          ? "Search context has not been indexed yet."
          : `Search context status is ${summary.embedding_index_status}.`,
      actionTitle:
        summary.primary_next_action_title ??
        "Build context with selected search model",
      navigationHint: "Open Models for model setup or use Overview to build context.",
    };
  }

  if (summary.overall_status === "needs_embedding_runtime") {
    return {
      title: "Search model needs backend runtime review",
      description:
        "The workspace preference differs from the active backend search model. Restart with the selected embedding model before rebuilding context.",
      badge: "Needs runtime review",
      message: "Chosen search model is not active in the backend runtime yet.",
      actionTitle:
        summary.primary_next_action_title ??
        "Restart backend for selected search model",
      navigationHint: "Open Models to review selected and backend search models.",
    };
  }

  const onDemoModel = isDemoModel(summary.active_llm) && !summary.selected_llm;
  return {
    title: onDemoModel ? "Download a model to get real answers" : "Local AI setup needs attention",
    description: onDemoModel
      ? "This workspace is using the built-in demo model, so Ask returns placeholder text. Download a local model and it becomes the answer model automatically."
      : "Review the selected AI and search models before relying on source-backed answers.",
    badge: onDemoModel ? "Demo model" : summary.overall_status,
    message: onDemoModel
      ? "Open Models → Choose & install to download a local model."
      : !summary.can_search_with_selected_embedding
        ? "Search context is not ready yet."
        : null,
    actionTitle: onDemoModel
      ? "Download a local model"
      : summary.primary_next_action_title ?? "Review AI setup",
    navigationHint: "Open Models to review setup steps.",
  };
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
          <dd>{friendlyModelLabel(selected)}</dd>
        </div>
        <div>
          <dt>Backend default</dt>
          <dd
            className={isDemoModel(active) ? "is-demo-model" : undefined}
            title={isDemoModel(active) ? active : undefined}
          >
            {friendlyModelLabel(active)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function isDemoModel(value: string | null | undefined): boolean {
  return Boolean(value && value.toLowerCase().includes("fake"));
}

function friendlyModelLabel(value: string | null | undefined): string {
  if (!value) {
    return "Not selected";
  }
  if (isDemoModel(value)) {
    return "Demo model — placeholder answers";
  }
  return value;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
