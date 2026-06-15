import { useEffect, useState } from "react";

import {
  createLocalModelInstallDraft,
  getLocalModelDownloadExecutionCapability,
  getLocalModelInstallStatus,
  startLocalModelDownloadJob,
  updateWorkspaceModelSelection,
} from "../api/client";
import type {
  LocalModelInstallStatus,
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
} from "../api/types";

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

/**
 * One calm setup step at a time, done inline — no detour into Models/Settings.
 * Order: (Ollama) -> scan -> local models -> build context -> ready to ask.
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
  const [busy, setBusy] = useState<"scan" | "models" | "index" | "check" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshInstallStatus() {
    try {
      setInstallStatus(await getLocalModelInstallStatus());
    } catch {
      // Ignore; treated as "unknown" below.
    }
  }

  useEffect(() => {
    void refreshInstallStatus();
  }, []);

  const ollamaReachable = installStatus ? installStatus.runtime_reachable : true;

  async function installRecommendedModels() {
    setBusy("models");
    setError(null);
    setMessage(null);
    try {
      const status = await getLocalModelInstallStatus();
      setInstallStatus(status);
      if (!status.runtime_reachable) {
        setError("Ollama isn’t running yet. Start it, then try again.");
        return;
      }
      const capability = await getLocalModelDownloadExecutionCapability();
      const missing = asArray(status.items).filter(
        (item) => item.recommended && item.status !== "installed",
      );
      if (missing.length === 0) {
        await onRefreshWorkspaceState();
        return;
      }
      for (const item of missing) {
        const modelType = (item.model_type === "embedding" ? "embedding" : "llm") as
          | "llm"
          | "embedding";
        const draft = await createLocalModelInstallDraft({
          workspace_id: dashboard.workspace_id,
          provider: item.provider,
          model: item.model,
          model_type: modelType,
        });
        if (capability.execution_enabled) {
          await startLocalModelDownloadJob(draft.command_proposal.id);
        }
        await updateWorkspaceModelSelection(dashboard.workspace_id, {
          provider: item.provider,
          model: item.model,
          model_type: modelType,
          selected_reason: "First-run recommended setup.",
        });
      }
      setMessage(
        "Downloading your local AI — watch progress in the sidebar. This step finishes once both models are installed; then tap Re-check.",
      );
      await onRefreshWorkspaceState();
    } catch (installError) {
      setError(installError instanceof Error ? installError.message : "Could not start the install.");
    } finally {
      setBusy(null);
    }
  }

  async function recheck() {
    setBusy("check");
    await refreshInstallStatus();
    await onRefreshWorkspaceState();
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
          <div className="getting-ready-models">
            <span>qwen2.5-coder · answers</span>
            <span>nomic-embed-text · search</span>
          </div>
          <div className="getting-ready-actions">
            <button className="getting-ready-cta" type="button" disabled={busy !== null} onClick={() => void installRecommendedModels()}>
              {busy === "models" ? "Starting…" : "Install & continue"}
            </button>
            <button className="secondary-action" type="button" disabled={busy !== null} onClick={() => void recheck()}>
              {busy === "check" ? "Checking…" : "Re-check"}
            </button>
            <button className="text-button" type="button" onClick={onOpenModels}>
              Choose models yourself
            </button>
          </div>
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
