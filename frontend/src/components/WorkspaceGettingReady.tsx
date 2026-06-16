import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelLocalModelDownloadJob,
  createLocalModelInstallDraft,
  getLocalModelDownloadExecutionCapability,
  getLocalModelInstallStatus,
  listLocalModelDownloadJobs,
  startLocalModelDownloadJob,
  updateWorkspaceModelSelection,
} from "../api/client";
import type {
  LocalModelDownloadJob,
  LocalModelInstallStatus,
  LocalModelStatusItem,
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function roleLabel(item: LocalModelStatusItem): string {
  return item.model_type === "embedding" ? "search" : "answers";
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
  const embeddingReady = modelsSummary.can_search_with_selected_embedding;
  const llmReady = modelsSummary.can_ask_with_selected_llm;
  const modelsReady = embeddingReady && llmReady;

  const [installStatus, setInstallStatus] = useState<LocalModelInstallStatus | null>(null);
  const [downloadJobs, setDownloadJobs] = useState<LocalModelDownloadJob[]>([]);
  const [busy, setBusy] = useState<"scan" | "models" | "index" | "check" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);
  const prevActiveJobsRef = useRef(0);
  const prevInstalledCountRef = useRef<number | null>(null);

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

  const ollamaReachable = installStatus ? installStatus.runtime_reachable : true;
  const recommendedItems = asArray(installStatus?.items).filter((item) => item.recommended);

  function jobForModel(model: string): LocalModelDownloadJob | undefined {
    return downloadJobs.find((job) => job.model === model);
  }

  async function installRecommendedModels() {
    setBusy("models");
    setError(null);
    setMessage(null);
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
      setMessage(
        started > 0
          ? "Downloading your local AI — progress shows below. Keep this open."
          : "Models ready — moving on.",
      );
      await tick();
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
    await tick();
    await onRefreshWorkspaceState();
    setCheckedAt(Date.now());
    setBusy(null);
  }

  // ---- Which step are we on? --------------------------------------------
  let step: "ollama" | "scan" | "models" | "index" | "ready";
  if (!ollamaReachable) step = "ollama";
  else if (!hasScan) step = "scan";
  else if (!modelsReady) step = "models";
  else if (!indexReady) step = "index";
  else step = "ready";

  const stepNumber = { ollama: 0, scan: 1, models: 2, index: 3, ready: 4 }[step];
  const downloading = downloadJobs.length > 0;

  return (
    <section className="getting-ready">
      <div className="getting-ready-stepper" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={stepNumber >= n ? "is-on" : ""} />
        ))}
      </div>

      {step === "ollama" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">First — the local engine</span>
          <h2>Install Ollama to run AI on your Mac</h2>
          <p>
            {dashboard.workspace_name} runs models locally through Ollama — a free,
            private engine. Install it once, start it, then come back.
          </p>
          <div className="getting-ready-actions">
            <a className="getting-ready-cta" href="https://ollama.com/download" target="_blank" rel="noreferrer">
              Get Ollama
            </a>
            <button className="secondary-action" type="button" disabled={busy !== null} onClick={() => void recheck()}>
              {busy === "check" ? "Checking…" : "I’ve installed it — re-check"}
            </button>
          </div>
        </div>
      ) : step === "scan" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Step 1 of 3</span>
          <h2>Look at your project</h2>
          <p>A quick, local scan lists your files so the AI knows what it can search. Nothing leaves this Mac.</p>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" disabled={busy !== null} onClick={() => { setBusy("scan"); void onStartScanJob(); window.setTimeout(() => setBusy(null), 4000); }}>
              {busy === "scan" ? "Scanning…" : "Scan project"}
            </button>
          </div>
        </div>
      ) : step === "models" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Step 2 of 3 · one click</span>
          <h2>Give your project a local brain</h2>
          <p>
            Downloads two small local models — one to answer, one to search your files
            (about 5 GB, runs offline). Want to choose your own instead? Open Models.
          </p>

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
                      <span className="install-progress-bar">
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
              {downloading ? "Downloading…" : busy === "models" ? "Starting…" : "Install & continue"}
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
              Checked — {modelsReady ? "all set, moving on." : "still missing a model above."}
            </p>
          ) : null}
        </div>
      ) : step === "index" ? (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Step 3 of 3</span>
          <h2>Build understanding</h2>
          <p>Turn your scanned files into searchable local context, so answers come from your real project.</p>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" disabled={busy !== null} onClick={() => { setBusy("index"); void onStartIndexJob(); window.setTimeout(() => setBusy(null), 4000); }}>
              {busy === "index" ? "Building…" : "Build search context"}
            </button>
          </div>
        </div>
      ) : (
        <div className="getting-ready-step">
          <span className="getting-ready-kicker">Ready</span>
          <h2>Everything’s set — ask anything</h2>
          <p>Your project is scanned, your local AI is installed, and context is built. Answers stay on this Mac.</p>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" onClick={onOpenAsk}>
              Ask a question
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
