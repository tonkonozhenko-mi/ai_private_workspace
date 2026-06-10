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
import { ModelsSummaryCard } from "./ModelsSummaryCard";
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
          <span>
            {summary.has_scan ? "Latest scan available" : "Project scan needed"}
          </span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Context</span>
          <strong className="metric-word">
            {formatLabel(indexStatus.status)}
          </strong>
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
        onPreviewSavedFileSelection={onPreviewSavedFileSelection}
        onPreviewDraftFileSelection={onPreviewDraftFileSelection}
        onStartScanJob={onStartScanJob}
        onStartIndexJob={onStartIndexJob}
        onGetWorkspaceJob={onGetWorkspaceJob}
        onListWorkspaceJobs={onListWorkspaceJobs}
        onCancelWorkspaceJob={onCancelWorkspaceJob}
        onRefreshWorkspaceState={onRefreshWorkspaceState}
        fileIndexingPreferences={fileIndexingPreferences}
      />

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
          <button
            className="overview-cta-button"
            type="button"
            onClick={onOpenAsk}
          >
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
  onPreviewSavedFileSelection,
  onPreviewDraftFileSelection,
  onStartScanJob,
  onStartIndexJob,
  onGetWorkspaceJob,
  onListWorkspaceJobs,
  onCancelWorkspaceJob,
  onRefreshWorkspaceState,
  fileIndexingPreferences,
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
}) {
  const summary = dashboard.summary;
  const hasScan = summary.has_scan;
  const indexReady = summary.index_status.status === "indexed";
  const localAIReady = modelsSummary.overall_status === "ready";
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
  const pollingJobIdRef = useRef<string | null>(null);

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
      description:
        "Optional: compare local models only when you want to improve answer quality.",
      status: "optional",
    },
  ];

  const primaryAction = !hasScan
    ? {
        label: setupAction === "scan" ? "Scanning..." : "Scan project",
        onClick: () => void requestSetupAction("scan"),
        disabled: setupAction !== null,
      }
    : !indexReady
      ? {
          label:
            setupAction === "index" ? "Building..." : "Build search context",
          onClick: () => void requestSetupAction("index"),
          disabled: setupAction !== null,
        }
      : !localAIReady
        ? { label: "Review Models", onClick: onOpenModels, disabled: false }
        : { label: "Go to Ask", onClick: onOpenAsk, disabled: false };

  return (
    <section className="panel onboarding-guide-panel">
      <div className="onboarding-guide-heading">
        <div>
          <p className="eyebrow">Guided path</p>
          <h2>
            {readyToAsk ? "Ready to ask questions" : "Set up this workspace"}
          </h2>
          <p>
            A short, safe path from local folder to source-backed answers.
          </p>
          <span className="onboarding-safety-note">
            Each step is explicit and reversible. No hidden shell commands.
          </span>
        </div>
        <button
          className="overview-cta-button"
          type="button"
          disabled={primaryAction.disabled}
          onClick={primaryAction.onClick}
        >
          {primaryAction.label}
        </button>
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

      {!readyToAsk ? (
        <div
          className="workspace-setup-actions"
          aria-label="Current workspace setup step"
        >
          <div>
            <strong>
              {!hasScan
                ? "Next: scan the project"
                : !indexReady
                  ? "Next: build search context"
                  : "Next: review local AI"}
            </strong>
            <p>
              {!hasScan
                ? "The scan reads project metadata through the backend and records detected technologies."
                : !indexReady
                  ? "Search context makes answers grounded in local project sources."
                  : "Confirm the selected models before asking source-backed questions."}
            </p>
          </div>
          <div className="workspace-setup-action-buttons">
            <button
              className="secondary-action"
              type="button"
              onClick={onOpenCapabilities}
            >
              View capabilities
            </button>
          </div>
        </div>
      ) : null}

      <details className="file-rules-plan file-rules-disclosure" aria-label="File selection plan">
        <summary>
          <div>
            <strong>File rules for scan and context build</strong>
            <p>
              Saved rules are applied when scan/index starts. Open this only when you want to verify included files.
            </p>
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
      </details>

      {filePreviewError ? (
        <p className="settings-message error">{filePreviewError}</p>
      ) : null}

      {filePreview && filePreviewOpen ? (
        <FileSelectionPreviewPanel
          preview={filePreview}
          title={filePreviewMode === "draft" ? "Draft rules preview" : "Saved rules preview"}
        />
      ) : null}

      {confirmationAction ? (
        <JobConfirmationPanel
          action={confirmationAction}
          preview={filePreview}
          loading={filePreviewLoading}
          onCancel={clearSetupConfirmation}
          onConfirm={() => void runSetupAction(confirmationAction)}
        />
      ) : null}

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

      <div className="onboarding-steps-grid">
        {steps.map((step, index) => (
          <article
            className={`onboarding-step-card is-${step.status}`}
            key={step.title}
          >
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
  const skills = getWorkspaceSkillCards(
    dashboard.assistant_mode,
    summary.detected_skills_count,
    summary.has_scan,
    skillPreferences,
  );
  const suggestedFocus = getAssistantFocus(dashboard.assistant_mode);

  return (
    <section className="panel workspace-skills-panel">
      <div className="workspace-skills-heading">
        <div>
          <p className="eyebrow">Workspace skills</p>
          <h2>Use the right project lens</h2>
          <p>
            Skills help AI Private Workspace frame answers around the
            technologies and work style detected in this project.
          </p>
        </div>
        <div className="workspace-skills-badges">
          <StatusBadge
            label={
              summary.has_scan
                ? `${summary.detected_skills_count} found`
                : "scan first"
            }
            tone={summary.has_scan ? "success" : "warning"}
            size="md"
          />
          <StatusBadge
            label={`${activeSkillPresets.length} active skills`}
            tone="info"
            size="md"
          />
        </div>
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
          <strong>Customize skill presets</strong>
          <p>
            Open Settings to enable presets or tune custom instructions, for
            example extending DevOps with Jenkins pipelines, deployment rules,
            or company-specific review checks.
          </p>
        </div>
        <button
          className="secondary-action"
          type="button"
          onClick={onOpenSettings}
        >
          Manage skills
        </button>
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
    <section className="panel workspace-files-panel">
      <div className="workspace-skills-heading">
        <div>
          <p className="eyebrow">Files and context</p>
          <h2>Control what becomes searchable</h2>
          <p>
            File preferences define which local project files should be
            considered for scan and future indexing. Defaults keep source, docs,
            and infrastructure files while skipping generated or heavy folders.
          </p>
        </div>
        <div className="workspace-skills-badges">
          <StatusBadge label={`${includeCount} include rules`} tone="info" />
          <StatusBadge label={`${excludeCount} exclude rules`} tone="neutral" />
        </div>
      </div>

      <div className="workspace-files-grid">
        <article className="workspace-skill-card">
          <div className="workspace-skill-icon" aria-hidden="true">
            ↳
          </div>
          <div>
            <h3>Include useful project files</h3>
            <p>
              Source code, documentation, Terraform, Kubernetes, Docker, Helm,
              and CI/CD definitions are included by default.
            </p>
            <span className="workspace-skill-footnote">
              Source, docs, configs, IaC
            </span>
          </div>
        </article>
        <article className="workspace-skill-card">
          <div className="workspace-skill-icon" aria-hidden="true">
            ⊘
          </div>
          <div>
            <h3>Skip noisy or generated files</h3>
            <p>
              Dependencies, caches, build outputs, binaries, archives, and logs
              stay out of the context by default.
            </p>
            <span className="workspace-skill-footnote">
              node_modules, .venv, dist, build
            </span>
          </div>
        </article>
        <article className="workspace-skill-card">
          <div className="workspace-skill-icon" aria-hidden="true">
            ⌘
          </div>
          <div>
            <h3>Review before rebuilding</h3>
            <p>
              This task only prepares browser-local preferences. Rebuilding
              search context remains an explicit action.
            </p>
            <span className="workspace-skill-footnote">Manual and safe</span>
          </div>
        </article>
      </div>

      <div className="workspace-skills-next-step">
        <div>
          <p className="eyebrow">Indexing control</p>
          <h3>
            {contextReady
              ? "Search context is ready"
              : scanReady
                ? "Review file rules before building context"
                : "Scan first, then review file rules"}
          </h3>
          <p>
            File preferences are saved in this browser and will be connected to
            scan/index requests in the next phase step.
          </p>
        </div>
        <button
          className="secondary-action"
          type="button"
          onClick={onOpenSettings}
        >
          Edit file rules
        </button>
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
