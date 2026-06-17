import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelGgufDownload,
  getGgufCatalog,
  getGgufDownload,
  getLlamaRuntimeStatus,
  setActiveBackend,
  startGgufDownload,
  startLlamaRuntime,
  switchLlamaRuntimeLlm,
  updateWorkspaceModelSelection,
} from "../api/client";
import type { GgufCatalogItem, GgufDownloadJob, LlamaRuntimeStatus } from "../api/types";

function formatGb(bytes: number): string {
  if (!bytes) return "";
  const gb = bytes / 1024 ** 3;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${Math.round(bytes / 1024 ** 2)} MB`;
}

// llama.cpp setup: the engine binary ships inside the app; here we download the
// GGUF model files. The catalog reports real on-disk install state, so models
// downloaded for one workspace already show as installed in the next one.
export function LlamaCppModelsPanel({
  workspaceId,
  onReady,
  mode = "manage",
}: {
  workspaceId?: string;
  onReady?: () => void;
  // "setup" = first-run: just the recommended answer model + embedder, download
  // and go (like Ollama). "manage" = Models tab: full list with per-model
  // download and live answer-model switching.
  mode?: "setup" | "manage";
}) {
  const interactive = mode === "manage";
  const [models, setModels] = useState<GgufCatalogItem[] | null>(null);
  const [jobs, setJobs] = useState<Record<string, GgufDownloadJob>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [runtime, setRuntime] = useState<LlamaRuntimeStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const pollers = useRef<Record<string, number>>({});

  // Tell the parent setup flow once the engine is actually running, so the
  // "models" step can advance to indexing → chat — mirroring the Ollama path.
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;
  useEffect(() => {
    if (runtime?.running) onReadyRef.current?.();
  }, [runtime?.running]);

  const refreshCatalog = useCallback(async () => {
    const all = await getGgufCatalog();
    setModels(all);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getLlamaRuntimeStatus()
      .then((status) => {
        if (!cancelled) setRuntime(status);
      })
      .catch(() => {
        /* status optional — panel still works for downloads */
      });
    getGgufCatalog()
      .then((all) => {
        if (!cancelled) setModels(all);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the model list."));
    const active = pollers.current;
    return () => {
      cancelled = true;
      Object.values(active).forEach((id) => window.clearInterval(id));
    };
  }, []);

  const poll = useCallback(
    (modelId: string, jobId: string) => {
      window.clearInterval(pollers.current[jobId]);
      pollers.current[jobId] = window.setInterval(async () => {
        try {
          const job = await getGgufDownload(jobId);
          setJobs((current) => ({ ...current, [modelId]: job }));
          if (["succeeded", "failed", "cancelled"].includes(job.status)) {
            window.clearInterval(pollers.current[jobId]);
            if (job.status === "succeeded") void refreshCatalog();
          }
        } catch {
          /* keep polling through transient errors */
        }
      }, 1000);
    },
    [refreshCatalog],
  );

  const isInstalled = useCallback(
    (model: GgufCatalogItem) =>
      model.installed || jobs[model.id]?.status === "succeeded",
    [jobs],
  );

  const llmModels = (models ?? []).filter((m) => m.model_type === "llm");
  const embedModel =
    (models ?? []).find((m) => m.model_type === "embedding" && m.recommended) ??
    (models ?? []).find((m) => m.model_type === "embedding");
  const recommendedLlm =
    llmModels.find((m) => m.recommended) ?? llmModels[0];

  // First-run setup stays simple: only the recommended answer model is shown.
  // The Models tab ("manage") shows every answer model with download/switch.
  const visibleLlmModels = interactive
    ? llmModels
    : recommendedLlm
      ? [recommendedLlm]
      : [];

  // The minimum to run: a recommended answer model + the embedder.
  const requiredModels = [recommendedLlm, embedModel].filter(
    (m): m is GgufCatalogItem => Boolean(m),
  );
  const requiredInstalled =
    requiredModels.length > 0 && requiredModels.every((m) => isInstalled(m));

  async function download(modelId: string) {
    setError(null);
    try {
      const job = await startGgufDownload({ model_id: modelId });
      setJobs((current) => ({ ...current, [modelId]: job }));
      poll(modelId, job.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the download.");
    }
  }

  async function downloadRequired() {
    setBusy(true);
    setError(null);
    try {
      for (const model of requiredModels) {
        if (isInstalled(model)) continue;
        await download(model.id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function stop(modelId: string, jobId: string) {
    try {
      await cancelGgufDownload(jobId);
    } catch {
      /* the poller will reflect the final state */
    }
    window.clearInterval(pollers.current[jobId]);
    setJobs((current) => {
      const next = { ...current };
      delete next[modelId];
      return next;
    });
  }

  async function applyWorkspaceSelection(llmId: string) {
    await setActiveBackend("llamacpp").catch(() => {});
    if (!workspaceId) return;
    await updateWorkspaceModelSelection(workspaceId, {
      provider: "llamacpp",
      model: llmId,
      model_type: "llm",
      selected_reason: "Built-in llama.cpp engine",
    }).catch(() => {});
    if (embedModel) {
      await updateWorkspaceModelSelection(workspaceId, {
        provider: "llamacpp",
        model: embedModel.id,
        model_type: "embedding",
        selected_reason: "Built-in llama.cpp engine",
      }).catch(() => {});
    }
  }

  async function startEngine() {
    setStarting(true);
    setError(null);
    try {
      const status = await startLlamaRuntime();
      setRuntime(status);
      if (status.running) {
        await applyWorkspaceSelection(status.active_llm_model ?? recommendedLlm?.id ?? "");
        await refreshCatalog();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the engine.");
    } finally {
      setStarting(false);
    }
  }

  // Switch the running engine to a different, already-downloaded answer model.
  async function useModel(modelId: string) {
    setSwitchingId(modelId);
    setError(null);
    try {
      const status = await switchLlamaRuntimeLlm(modelId);
      setRuntime(status);
      await applyWorkspaceSelection(modelId);
      await refreshCatalog();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not switch the answer model.");
    } finally {
      setSwitchingId(null);
    }
  }

  const anyDownloading = Object.values(jobs).some(
    (j) => j.status === "running" || j.status === "queued",
  );

  function renderRow(model: GgufCatalogItem, kind: "llm" | "embedding") {
    const job = jobs[model.id];
    const pct = job?.progress_percent ?? null;
    const downloading = job?.status === "running" || job?.status === "queued";
    const installed = isInstalled(model);
    const active = model.active && kind === "llm";
    const state = active ? "done" : installed ? "done" : downloading ? "load" : "wait";
    return (
      <li className={`gr-check gr-check--${state}`} key={model.id}>
        <span className="gr-check-icon" aria-hidden="true">
          {downloading ? <span className="gr-check-spin" /> : null}
        </span>
        <span className="gr-check-name">
          {model.name}
          <small>
            · {kind === "embedding" ? "search" : "answers"} · {formatGb(model.size_bytes)}
            {model.recommended ? " · recommended" : ""}
          </small>
        </span>
        {downloading ? (
          <span className="gr-check-progress">
            <span className="gr-check-pct">{pct === null ? "…" : `${Math.round(pct)}%`}</span>
            <span className={`install-progress-bar${pct === null ? " is-indeterminate" : ""}`}>
              <span style={pct === null ? undefined : { width: `${pct}%` }} />
            </span>
            <button type="button" className="gr-check-stop" onClick={() => void stop(model.id, job!.id)}>
              Stop
            </button>
          </span>
        ) : active ? (
          <span className="gr-check-state gr-check-state--on">In use</span>
        ) : installed ? (
          interactive && kind === "llm" && runtime?.running ? (
            <button
              type="button"
              className="gr-check-use"
              disabled={switchingId !== null}
              onClick={() => void useModel(model.id)}
            >
              {switchingId === model.id ? "Switching…" : "Use this model"}
            </button>
          ) : (
            <span className="gr-check-state">Downloaded</span>
          )
        ) : interactive ? (
          <button
            type="button"
            className="gr-check-use"
            disabled={anyDownloading}
            onClick={() => void download(model.id)}
          >
            Download
          </button>
        ) : (
          <span className="gr-check-state">Not yet</span>
        )}
      </li>
    );
  }

  const installedLlm = llmModels.filter((m) => isInstalled(m));
  const addableLlm = llmModels.filter((m) => !isInstalled(m));

  const engineCta = !requiredInstalled ? (
    <button
      className="getting-ready-cta"
      type="button"
      disabled={busy || anyDownloading || models == null}
      onClick={() => void downloadRequired()}
    >
      {anyDownloading ? "Downloading…" : busy ? "Starting…" : "Download models"}
    </button>
  ) : runtime?.running ? (
    <span className="gr-llama-running">✓ Engine running — ready to use</span>
  ) : runtime && !runtime.binary_available ? (
    <span className="gr-llama-note">
      Models downloaded. The engine ships with the packaged app — it will start
      automatically there.
    </span>
  ) : (
    <button
      className="getting-ready-cta"
      type="button"
      disabled={starting}
      onClick={() => void startEngine()}
    >
      {starting ? "Starting engine…" : "Start engine"}
    </button>
  );

  if (!interactive) {
    // First-run setup: recommended answer model + embedder, download and go.
    return (
      <div className="gr-llama">
        <p className="gr-llama-note">
          The llama.cpp engine is built into the app — nothing to install. Just
          download the two small models below.
        </p>
        {error ? <p className="getting-ready-error">{error}</p> : null}
        <ul className="getting-ready-checklist">
          {visibleLlmModels.map((model) => renderRow(model, "llm"))}
          {embedModel ? renderRow(embedModel, "embedding") : null}
        </ul>
        <div className="getting-ready-actions">{engineCta}</div>
      </div>
    );
  }

  // Models tab: installed models + info first, then an "Add a model" section.
  return (
    <div className="gr-llama">
      {error ? <p className="getting-ready-error">{error}</p> : null}

      <p className="gr-llama-section-label">Your engine models</p>
      <ul className="getting-ready-checklist">
        {installedLlm.map((model) => renderRow(model, "llm"))}
        {embedModel ? renderRow(embedModel, "embedding") : null}
      </ul>
      <div className="getting-ready-actions">{engineCta}</div>

      <p className="gr-llama-section-label">Add a model</p>
      <p className="gr-llama-note">
        Download another answer model to switch to. Models are shared across all
        your projects.
      </p>
      {addableLlm.length > 0 ? (
        <ul className="getting-ready-checklist">
          {addableLlm.map((model) => renderRow(model, "llm"))}
        </ul>
      ) : (
        <p className="gr-llama-note">Every catalog model is already downloaded.</p>
      )}
    </div>
  );
}
