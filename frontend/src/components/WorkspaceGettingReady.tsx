import { useCallback, useEffect, useRef, useState } from "react";

import { LlamaCppModelsPanel } from "./LlamaCppModelsPanel";

import {
  cancelLocalModelDownloadJob,
  cancelWorkspaceJob,
  createLocalModelInstallDraft,
  getLocalModelDownloadExecutionCapability,
  getLocalModelInstallStatus,
  getWorkspaceJob,
  listLocalModelDownloadJobs,
  setActiveBackend,
  startLocalModelDownloadJob,
  updateWorkspaceModelSelection,
} from "../api/client";
import type {
  LocalModelDownloadJob,
  LocalModelInstallStatus,
  LocalModelStatusItem,
  WorkspaceJob,
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function roleLabel(item: LocalModelStatusItem): string {
  return item.model_type === "embedding" ? "search" : "answers";
}

// Tauri does not follow target="_blank" links, so route external URLs through
// the Rust `open_external_url` command (exposed via withGlobalTauri). Falls back
// to window.open when running in a plain browser (dev).
function openExternalUrl(url: string): void {
  const invoke = (
    window as unknown as {
      __TAURI__?: { core?: { invoke?: (cmd: string, args?: unknown) => Promise<unknown> } };
    }
  ).__TAURI__?.core?.invoke;
  if (invoke) {
    void invoke("open_external_url", { url });
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

/**
 * One calm setup step at a time, done inline — no detour into Models/Settings.
 * Order: (Ollama) -> scan -> local models -> build context -> ready to ask.
 *
 * The models step polls download jobs + install status so progress and
 * green/▢ status are visible right here (this screen can run full-window with
 * no sidebar, so progress must live inline rather than in the sidebar).
 */
export function WorkspaceGettingReady({
  dashboard,
  modelsSummary,
  onOpenAsk,
  onOpenModels,
  onStartScanJob,
  onStartIndexJob,
  onRefreshWorkspaceState,
}: {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  onOpenAsk: () => void;
  onOpenModels: () => void;
  onStartScanJob: () => Promise<unknown> | void;
  onStartIndexJob: () => Promise<unknown> | void;
  onRefreshWorkspaceState: () => Promise<void> | void;
}) {
  const summary = dashboard.summary;
  const hasScan = summary.has_scan;
  const indexReady = summary.index_status.status === "indexed";
  // The "models" step checks that models are CHOSEN + INSTALLED (computed below),
  // not that search works — search needs an index, which is the NEXT step.

  // The workspace already records its engine in its selected providers, so a
  // returning project opens on the right engine. A FRESH workspace (no
  // selection yet) defaults to the built-in llama.cpp engine: zero install,
  // and the only path with Flash Attention, prompt cache, and exact token
  // counts. Ollama is offered as a detected integration (one quiet line when
  // it's actually running) rather than an upfront decision — progressive
  // disclosure: the capability stays, the decision disappears.
  const hasEngineSelection =
    Boolean(modelsSummary.selected_llm) || Boolean(modelsSummary.selected_embedding);
  const workspaceBackend: "ollama" | "llamacpp" =
    !hasEngineSelection ||
    modelsSummary.selected_llm?.startsWith("llamacpp") ||
    modelsSummary.selected_embedding?.startsWith("llamacpp")
      ? "llamacpp"
      : "ollama";

  const [installStatus, setInstallStatus] = useState<LocalModelInstallStatus | null>(null);
  const [downloadJobs, setDownloadJobs] = useState<LocalModelDownloadJob[]>([]);
  const [busy, setBusy] = useState<"scan" | "models" | "index" | "check" | null>(null);
  const [backendChoice, setBackendChoice] = useState<"ollama" | "llamacpp">(workspaceBackend);
  // True once the built-in llama.cpp engine reports running (models downloaded,
  // engine up, selections applied). Used to pass the "models" step in llama.cpp
  // mode, the same way recommendedInstalled does for Ollama.
  const [llamaReady, setLlamaReady] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  const [jobProgress, setJobProgress] = useState<{
    kind: "scan" | "index";
    current: number | null;
    total: number | null;
    percent: number | null;
    step: string | null;
    startedAt: number;
  } | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const prevActiveJobsRef = useRef(0);
  const prevInstalledCountRef = useRef<number | null>(null);

  // Start a scan/index job, then poll it for real progress (X of Y files, %),
  // and advance when it completes — so the user always sees what's happening.
  async function runJob(kind: "scan" | "index", starter: () => Promise<unknown> | void) {
    setBusy(kind);
    setError(null);
    setMessage(null);
    setJobProgress({
      kind,
      current: null,
      total: null,
      percent: null,
      step: "Starting…",
      startedAt: Date.now(),
    });
    try {
      const result = (await starter()) as WorkspaceJob | undefined;
      const jobId = result?.job_id;
      if (!jobId) {
        await onRefreshWorkspaceState();
        return;
      }
      setRunningJobId(jobId);
      for (let attempt = 0; attempt < 900; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        let job: WorkspaceJob;
        try {
          job = await getWorkspaceJob(dashboard.workspace_id, jobId);
        } catch {
          continue;
        }
        setJobProgress((prev) => ({
          kind,
          current: job.progress_current,
          total: job.progress_total,
          percent: job.progress_percent,
          step: job.current_step ?? job.message,
          startedAt: prev?.startedAt ?? Date.now(),
        }));
        if (["completed", "failed", "cancelled"].includes(job.status)) {
          if (job.status === "failed") {
            setError(job.error ?? "That step failed. Please try again.");
          }
          await onRefreshWorkspaceState();
          break;
        }
      }
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Could not run this step.");
    } finally {
      setBusy(null);
      setJobProgress(null);
      setRunningJobId(null);
      setCancelling(false);
    }
  }

  // Let the user stop a long-running scan/index. The backend marks the job
  // cancelled; the poll loop above then observes "cancelled" and unwinds. The
  // project files on disk are never touched.
  async function stopJob() {
    if (!runningJobId || cancelling) return;
    setCancelling(true);
    setJobProgress((current) => (current ? { ...current, step: "Stopping…" } : current));
    try {
      await cancelWorkspaceJob(dashboard.workspace_id, runningJobId);
    } catch {
      // If cancel fails (e.g. job already finished), the poller resolves it.
      setCancelling(false);
    }
  }

  // Estimate remaining time from the average rate so far. Only shown once there's
  // enough signal (>=3% done and a few seconds elapsed) so it isn't wildly wrong.
  function formatEta(progress: NonNullable<typeof jobProgress>): string | null {
    const { current, total, startedAt } = progress;
    if (!total || current == null || current <= 0 || current >= total) return null;
    const elapsedMs = Date.now() - startedAt;
    if (elapsedMs < 3000 || current / total < 0.03) return null;
    const remainingMs = (elapsedMs / current) * (total - current);
    const secs = Math.round(remainingMs / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return rem ? `${mins}m ${rem}s` : `${mins}m`;
  }

  function renderJobProgress(progress: NonNullable<typeof jobProgress>) {
    // Before the file list is known the backend reports a "0 of 1" placeholder,
    // which reads like a stuck 0% — show a plain "Enumerating files…" instead.
    const enumerating =
      progress.current != null &&
      progress.current <= 0 &&
      (progress.total == null || progress.total <= 1);
    const percent = enumerating
      ? null
      : progress.percent ??
        (progress.total && progress.current != null
          ? Math.round((progress.current / progress.total) * 100)
          : null);
    const label = enumerating
      ? "Enumerating files…"
      : progress.total != null && progress.current != null
        ? `${progress.current.toLocaleString()} of ${progress.total.toLocaleString()} files`
        : progress.step ?? "Working…";
    // Rough ETA from the average rate so far — reassuring on large repos.
    const eta = formatEta(progress);
    return (
      <div className="gr-job-progress">
        <div className={`install-progress-bar${percent === null ? " is-indeterminate" : ""}`}>
          <span style={percent === null ? undefined : { width: `${percent}%` }} />
        </div>
        <div className="gr-job-progress-foot">
          <span className="gr-job-progress-label">
            {label}
            {percent !== null ? ` · ${percent}%` : ""}
            {eta ? ` · ~${eta} left` : ""}
          </span>
          {runningJobId ? (
            <button
              className="gr-job-stop"
              type="button"
              disabled={cancelling}
              onClick={() => void stopJob()}
            >
              {cancelling ? "Stopping…" : "Stop"}
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  // Lightweight poll: only install status + in-flight downloads (2 cheap calls).
  // The heavy workspace refresh (8 calls) runs ONLY on a real transition — a
  // download finishing or a model becoming installed — so we never storm the
  // local backend or race with scan/forget/delete actions. Scan and index steps
  // advance via their own job pollers in App (pollSetupJobThenRefresh).
  const tick = useCallback(async () => {
    try {
      const [status, jobList] = await Promise.all([
        getLocalModelInstallStatus(),
        listLocalModelDownloadJobs(),
      ]);
      setInstallStatus(status);
      const active = asArray(jobList.jobs).filter(
        (job) => job.status === "running" || job.status === "queued",
      );
      setDownloadJobs(active);

      const installedCount = asArray(status.items).filter(
        (item) => item.status === "installed",
      ).length;
      const downloadsJustFinished = prevActiveJobsRef.current > 0 && active.length === 0;
      const installedChanged =
        prevInstalledCountRef.current !== null && installedCount !== prevInstalledCountRef.current;
      prevActiveJobsRef.current = active.length;
      prevInstalledCountRef.current = installedCount;

      if (downloadsJustFinished || installedChanged) {
        await onRefreshWorkspaceState();
      }
    } catch {
      // Ignore transient polling errors.
    }
  }, [onRefreshWorkspaceState]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (cancelled) return;
      await tick();
    };
    void run();
    const id = window.setInterval(() => void run(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [tick]);

  // Opening a different workspace re-syncs the toggle to that project's engine.
  useEffect(() => {
    setBackendChoice(workspaceBackend);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboard.workspace_id]);

  const ollamaReachable = installStatus ? installStatus.runtime_reachable : true;
  const recommendedItems = asArray(installStatus?.items).filter((item) => item.recommended);
  // Models step is done only when the recommended models are SELECTED (llm/embedding
  // ready) AND actually installed in Ollama — so we never skip to indexing while a
  // download is still running. Requires install status to have loaded.
  const recommendedInstalled =
    recommendedItems.length > 0 && recommendedItems.every((item) => item.status === "installed");
  // llama.cpp: pass only on explicit Continue from the panel (llamaReady).
  // Ollama: pass once the models are SELECTED and INSTALLED — NOT tied to whether
  // they match the currently-active runtime, which is app-global and flips when
  // you switch projects (reactivation re-points it on open). Tying the step to it
  // made a set-up project wrongly reappear in setup after switching projects.
  const ollamaModelsReady =
    modelsSummary.selected_llm != null &&
    modelsSummary.selected_embedding != null &&
    recommendedInstalled;
  const modelsReady =
    backendChoice === "llamacpp" ? llamaReady : ollamaModelsReady;

  function jobForModel(model: string): LocalModelDownloadJob | undefined {
    return downloadJobs.find((job) => job.model === model);
  }

  async function installRecommendedModels() {
    setBusy("models");
    setError(null);
    setMessage(null);
    setCheckedAt(null);
    try {
      const status = await getLocalModelInstallStatus();
      setInstallStatus(status);
      if (!status.runtime_reachable) {
        setError("Ollama isn’t running yet. Start it, then tap Re-check.");
        return;
      }
      const recommended = asArray(status.items).filter((item) => item.recommended);
      if (recommended.length === 0) {
        await onRefreshWorkspaceState();
        return;
      }
      const capability = await getLocalModelDownloadExecutionCapability();
      const missing = recommended.filter((item) => item.status !== "installed");
      if (missing.length > 0 && !capability.execution_enabled) {
        setError(
          "Automatic download is turned off in this build. Open Models to install them manually.",
        );
        return;
      }
      let started = 0;
      // For every recommended model: start its download if missing, and ALWAYS
      // select it for this workspace — selecting an already-installed model is
      // what flips can_ask / can_search to ready and advances the step.
      for (const item of recommended) {
        const modelType = (item.model_type === "embedding" ? "embedding" : "llm") as
          | "llm"
          | "embedding";
        if (item.status !== "installed") {
          const draft = await createLocalModelInstallDraft({
            workspace_id: dashboard.workspace_id,
            provider: item.provider,
            model: item.model,
            model_type: modelType,
          });
          await startLocalModelDownloadJob(draft.command_proposal.id);
          started += 1;
        }
        await updateWorkspaceModelSelection(dashboard.workspace_id, {
          provider: item.provider,
          model: item.model,
          model_type: modelType,
          selected_reason: "First-run recommended setup.",
        });
      }
      // The active embedding engine is global. If a previous project switched it
      // to llama.cpp, this Ollama project's embedding would "not match the active
      // runtime" and the step would never advance — so point it back at Ollama.
      await setActiveBackend("ollama").catch(() => {});
      setMessage(
        started > 0
          ? "Downloading your local AI — progress shows below. Keep this open."
          : "Models ready — moving on.",
      );
      // Trigger refreshes but DON'T await them — on some local backends a single
      // refresh call can stall, and the button must never freeze on it. The
      // models-step poll (below) advances the step once the selection registers.
      void tick();
      void onRefreshWorkspaceState();
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    } catch (installError) {
      setError(installError instanceof Error ? installError.message : "Could not start the install.");
    } finally {
      setBusy(null);
    }
  }

  async function stopDownload(jobId: string) {
    try {
      await cancelLocalModelDownloadJob(jobId);
      setDownloadJobs((current) => current.filter((job) => job.id !== jobId));
    } catch {
      // Next poll reflects the real state.
    }
  }

  async function recheck() {
    setBusy("check");
    setError(null);
    setMessage(null);
    try {
      await tick();
      // Fire-and-forget: on some local backends a single heavy refresh can stall,
      // and awaiting it here would leave `busy` stuck — which disables the next
      // step's button (e.g. "Scan project" never reacts). The step pollers and
      // tick() already advance state on their own.
      void onRefreshWorkspaceState();
      setCheckedAt(Date.now());
    } finally {
      setBusy(null);
    }
  }

  // ---- Which step are we on? --------------------------------------------
  // The "install Ollama" gate only applies when the user actually chose Ollama.
  // If they picked the built-in llama.cpp engine, Ollama is irrelevant and must
  // not block them — skip straight to scan/models.
  let step: "ollama" | "scan" | "models" | "index" | "ready";
  // A scanned AND indexed workspace is ready, full stop — the index could not
  // have been built without working models. Checking modelsReady first here
  // relied on ephemeral component state (llamaReady resets on remount), which
  // made the completion screen show "step 2" instead of "ready" right after
  // indexing finished (observed live).
  if (hasScan && indexReady) step = "ready";
  else if (backendChoice === "ollama" && !ollamaReachable) step = "ollama";
  else if (!hasScan) step = "scan";
  else if (!modelsReady) step = "models";
  else if (!indexReady) step = "index";
  else step = "ready";

  // Backend toggle, shared between the Ollama-install gate and the models step so
  // the user can switch engines at either point (picking llama.cpp clears the
  // Ollama requirement immediately).
  const backendToggle = (
    <div className="gr-backend-toggle" role="tablist" aria-label="Local engine">
      <button
        type="button"
        role="tab"
        aria-selected={backendChoice === "ollama"}
        className={backendChoice === "ollama" ? "is-selected" : ""}
        onClick={() => setBackendChoice("ollama")}
      >
        Ollama
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={backendChoice === "llamacpp"}
        className={backendChoice === "llamacpp" ? "is-selected" : ""}
        onClick={() => setBackendChoice("llamacpp")}
      >
        Built-in (llama.cpp)
      </button>
    </div>
  );

  const stepNumber = { ollama: 0, scan: 1, models: 2, index: 3, ready: 4 }[step];
  const downloading = downloadJobs.length > 0;

  // While on the models or index step, gently re-pull parent state so the step
  // advances on its own once selection/indexing registers — even if the one-off
  // refresh right after the job stalled or landed a beat too early (which made
  // "Build context" / Install look like they needed a second click). Stops once
  // the step moves on.
  useEffect(() => {
    if (step !== "models" && step !== "index") return;
    const id = window.setInterval(() => void onRefreshWorkspaceState(), 3000);
    return () => window.clearInterval(id);
  }, [step, onRefreshWorkspaceState]);

  return (
    <section className="getting-ready">
      <div className="getting-ready-stepper" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={stepNumber >= n ? "is-on" : ""} />
        ))}
      </div>

      {step === "ollama" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">First — pick a local engine</span>
          <h2>Choose how to run AI on your Mac</h2>
          <p>
            {dashboard.workspace_name} runs models locally. Use the built-in
            llama.cpp engine (nothing to install), or Ollama if you prefer it.
          </p>
          {backendToggle}
          <div className="getting-ready-actions">
            <button
              className="getting-ready-cta"
              type="button"
              onClick={() => openExternalUrl("https://ollama.com/download")}
            >
              Get Ollama
            </button>
            <button className="secondary-action" type="button" disabled={busy !== null} onClick={() => void recheck()}>
              {busy === "check" ? "Checking…" : "I’ve installed it — re-check"}
            </button>
          </div>
          <p className="gr-llama-note">
            Or pick “Built-in (llama.cpp)” above to skip Ollama entirely.
          </p>
        </div>
      ) : step === "scan" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Step 1 of 3</span>
          <h2>Look at your project</h2>
          <p>A quick, local scan lists your files so the AI knows what it can search. Nothing leaves this Mac.</p>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" disabled={busy !== null} onClick={() => void runJob("scan", onStartScanJob)}>
              {busy === "scan" ? "Scanning…" : "Scan project"}
            </button>
          </div>
          {jobProgress && jobProgress.kind === "scan" ? renderJobProgress(jobProgress) : null}
        </div>
      ) : step === "models" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Step 2 of 3 · one click</span>
          <h2>Give your project a local brain</h2>
          <p>
            Downloads two small local models — one to answer, one to search your files
            (about 2.5 GB, runs offline). Want a bigger, sharper model? Open Models.
          </p>

          {backendChoice === "llamacpp" ? (
            installStatus?.runtime_reachable === true ? (
              <p className="gr-engine-note">
                Found Ollama running on this Mac.{" "}
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setBackendChoice("ollama")}
                >
                  Use your Ollama models instead
                </button>{" "}
                — keeps your existing models, skips the download.
              </p>
            ) : null
          ) : (
            <p className="gr-engine-note">
              Using your Ollama install.{" "}
              <button
                type="button"
                className="text-button"
                onClick={() => setBackendChoice("llamacpp")}
              >
                Switch to the built-in engine
              </button>{" "}
              — nothing to install, works even without Ollama.
            </p>
          )}

          {backendChoice === "llamacpp" ? (
            <LlamaCppModelsPanel
              workspaceId={dashboard.workspace_id}
              mode="setup"
              onReady={() => {
                setLlamaReady(true);
                void onRefreshWorkspaceState();
              }}
            />
          ) : (
          <>
          <ul className="getting-ready-checklist">
            <li className={`gr-check gr-check--${ollamaReachable ? "done" : "bad"}`}>
              <span className="gr-check-icon" aria-hidden="true" />
              <span className="gr-check-name">Ollama engine</span>
              <span className="gr-check-state">{ollamaReachable ? "Running" : "Not running"}</span>
            </li>
            {(recommendedItems.length > 0
              ? recommendedItems
              : []
            ).map((item) => {
              const job = jobForModel(item.model);
              const installed = item.status === "installed";
              const pct = job?.progress_percent ?? null;
              const state = installed ? "done" : job ? "load" : "wait";
              return (
                <li className={`gr-check gr-check--${state}`} key={item.model}>
                  <span className="gr-check-icon" aria-hidden="true">
                    {job ? <span className="gr-check-spin" /> : null}
                  </span>
                  <span className="gr-check-name">
                    {item.display_name}
                    <small>· {roleLabel(item)}</small>
                  </span>
                  {job ? (
                    <span className="gr-check-progress">
                      <span className="gr-check-pct">
                        {pct === null ? "…" : `${Math.round(pct)}%`}
                      </span>
                      <span className={`install-progress-bar${pct === null ? " is-indeterminate" : ""}`}>
                        <span style={pct === null ? undefined : { width: `${pct}%` }} />
                      </span>
                      <button
                        type="button"
                        className="gr-check-stop"
                        onClick={() => void stopDownload(job.id)}
                      >
                        Stop
                      </button>
                    </span>
                  ) : (
                    <span className="gr-check-state">{installed ? "Installed" : "Not yet"}</span>
                  )}
                </li>
              );
            })}
          </ul>

          <div className="getting-ready-actions">
            <button
              className="getting-ready-cta"
              type="button"
              disabled={busy !== null || downloading}
              onClick={() => void installRecommendedModels()}
            >
              {downloading
                ? "Downloading…"
                : busy === "models"
                  ? "Starting…"
                  : recommendedInstalled
                    ? "Continue"
                    : "Install & continue"}
            </button>
            <button className="secondary-action" type="button" disabled={busy !== null} onClick={() => void recheck()}>
              {busy === "check" ? "Checking…" : "Re-check"}
            </button>
            <button className="text-button" type="button" onClick={onOpenModels}>
              Choose models yourself
            </button>
          </div>
          {checkedAt && !downloading ? (
            <p className="getting-ready-message">
              Checked — {modelsReady
                ? "all set, moving on."
                : recommendedInstalled
                  ? "tap Continue to use these models here."
                  : "tap Install & continue to use these models here."}
            </p>
          ) : null}
          </>
          )}
        </div>
      ) : step === "index" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Step 3 of 3</span>
          <h2>Build understanding</h2>
          <p>Turn your scanned files into searchable local context, so answers come from your real project.</p>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" disabled={busy !== null} onClick={() => void runJob("index", onStartIndexJob)}>
              {busy === "index" ? "Building…" : "Build search context"}
            </button>
          </div>
          {jobProgress && jobProgress.kind === "index" ? renderJobProgress(jobProgress) : null}
        </div>
      ) : (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Ready</span>
          <h2>Everything’s set — ask anything</h2>
          <p>
            {dashboard.summary.index_status.indexed_files_count > 0
              ? `${dashboard.summary.index_status.indexed_files_count.toLocaleString()} files turned into ${dashboard.summary.index_status.chunks_count.toLocaleString()} searchable pieces — all on this Mac. `
              : "Your project is scanned, your local AI is installed, and context is built. Answers stay on this Mac. "}
            The AI now answers from your real project, with sources.
          </p>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" onClick={onOpenAsk}>
              Ask your first question
            </button>
          </div>
        </div>
      )}

      {message ? <p className="getting-ready-message">{message}</p> : null}
      {error ? <p className="getting-ready-error">{error}</p> : null}
      <p className="getting-ready-foot">Everything runs on this Mac · no cloud · no accounts</p>
    </section>
  );
}
