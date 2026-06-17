import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelGgufDownload,
  getGgufCatalog,
  getGgufDownload,
  getLlamaRuntimeStatus,
  setActiveBackend,
  startGgufDownload,
  startLlamaRuntime,
  updateWorkspaceModelSelection,
} from "../api/client";
import type { GgufCatalogItem, GgufDownloadJob, LlamaRuntimeStatus } from "../api/types";

function formatGb(bytes: number): string {
  if (!bytes) return "";
  const gb = bytes / 1024 ** 3;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${Math.round(bytes / 1024 ** 2)} MB`;
}

// llama.cpp setup: the engine binary ships inside the app; here we only
// download the small GGUF model files (one to answer, one for search).
export function LlamaCppModelsPanel({
  workspaceId,
  onReady,
}: {
  workspaceId?: string;
  onReady?: () => void;
}) {
  const [models, setModels] = useState<GgufCatalogItem[] | null>(null);
  const [jobs, setJobs] = useState<Record<string, GgufDownloadJob>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [runtime, setRuntime] = useState<LlamaRuntimeStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const pollers = useRef<Record<string, number>>({});

  // Tell the parent setup flow once the engine is actually running, so the
  // "models" step can advance to indexing → chat — mirroring the Ollama path.
  // Kept in a ref so the effect below doesn't re-fire on every parent re-render.
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;
  useEffect(() => {
    if (runtime?.running) onReadyRef.current?.();
  }, [runtime?.running]);

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
        if (cancelled) return;
        // One recommended LLM + the recommended embedder.
        const llm = all.find((m) => m.model_type === "llm" && m.recommended) ?? all.find((m) => m.model_type === "llm");
        const embed = all.find((m) => m.model_type === "embedding" && m.recommended) ?? all.find((m) => m.model_type === "embedding");
        setModels([llm, embed].filter((m): m is GgufCatalogItem => Boolean(m)));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the model list."));
    return () => {
      cancelled = true;
      Object.values(pollers.current).forEach((id) => window.clearInterval(id));
    };
  }, []);

  const poll = useCallback((modelId: string, jobId: string) => {
    window.clearInterval(pollers.current[jobId]);
    pollers.current[jobId] = window.setInterval(async () => {
      try {
        const job = await getGgufDownload(jobId);
        setJobs((current) => ({ ...current, [modelId]: job }));
        if (["succeeded", "failed", "cancelled"].includes(job.status)) {
          window.clearInterval(pollers.current[jobId]);
        }
      } catch {
        /* keep polling through transient errors */
      }
    }, 1000);
  }, []);

  async function downloadAll() {
    if (!models) return;
    setBusy(true);
    setError(null);
    try {
      for (const model of models) {
        const existing = jobs[model.id];
        if (existing && existing.status === "succeeded") continue;
        const job = await startGgufDownload({ model_id: model.id });
        setJobs((current) => ({ ...current, [model.id]: job }));
        poll(model.id, job.id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the download.");
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

  async function startEngine() {
    setStarting(true);
    setError(null);
    try {
      const status = await startLlamaRuntime();
      setRuntime(status);
      if (status.running) {
        // Route search embeddings and this workspace's models through llama.cpp.
        await setActiveBackend("llamacpp").catch(() => {});
        if (workspaceId) {
          const llm = models?.find((m) => m.model_type === "llm");
          const embed = models?.find((m) => m.model_type === "embedding");
          if (llm) {
            await updateWorkspaceModelSelection(workspaceId, {
              provider: "llamacpp",
              model: llm.id,
              model_type: "llm",
              selected_reason: "Built-in llama.cpp engine",
            }).catch(() => {});
          }
          if (embed) {
            await updateWorkspaceModelSelection(workspaceId, {
              provider: "llamacpp",
              model: embed.id,
              model_type: "embedding",
              selected_reason: "Built-in llama.cpp engine",
            }).catch(() => {});
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the engine.");
    } finally {
      setStarting(false);
    }
  }

  const anyRunning =
    models?.some((m) => {
      const s = jobs[m.id]?.status;
      return s === "running" || s === "queued";
    }) ?? false;

  const allDone =
    models != null &&
    models.length > 0 &&
    models.every((m) => jobs[m.id]?.status === "succeeded");

  return (
    <div className="gr-llama">
      <p className="gr-llama-note">
        The llama.cpp engine is built into the app — nothing to install. Just
        download the two small models below.
      </p>
      {error ? <p className="getting-ready-error">{error}</p> : null}

      <ul className="getting-ready-checklist">
        {(models ?? []).map((model) => {
          const job = jobs[model.id];
          const pct = job?.progress_percent ?? null;
          const done = job?.status === "succeeded";
          const running = job?.status === "running" || job?.status === "queued";
          const state = done ? "done" : running ? "load" : "wait";
          return (
            <li className={`gr-check gr-check--${state}`} key={model.id}>
              <span className="gr-check-icon" aria-hidden="true">
                {running ? <span className="gr-check-spin" /> : null}
              </span>
              <span className="gr-check-name">
                {model.name}
                <small>· {model.model_type === "embedding" ? "search" : "answers"} · {formatGb(model.size_bytes)}</small>
              </span>
              {running ? (
                <span className="gr-check-progress">
                  <span className="gr-check-pct">{pct === null ? "…" : `${Math.round(pct)}%`}</span>
                  <span className={`install-progress-bar${pct === null ? " is-indeterminate" : ""}`}>
                    <span style={pct === null ? undefined : { width: `${pct}%` }} />
                  </span>
                  <button type="button" className="gr-check-stop" onClick={() => void stop(model.id, job!.id)}>
                    Stop
                  </button>
                </span>
              ) : (
                <span className="gr-check-state">
                  {done ? "Downloaded" : job?.status === "failed" ? "Failed" : "Not yet"}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <div className="getting-ready-actions">
        {!allDone ? (
          <button
            className="getting-ready-cta"
            type="button"
            disabled={busy || anyRunning || models == null}
            onClick={() => void downloadAll()}
          >
            {anyRunning ? "Downloading…" : busy ? "Starting…" : "Download models"}
          </button>
        ) : runtime?.running ? (
          <span className="gr-llama-running">✓ Engine running — ready to use</span>
        ) : runtime && !runtime.binary_available ? (
          <span className="gr-llama-note">
            Models downloaded. The engine ships with the packaged app — it will
            start automatically there.
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
        )}
      </div>
    </div>
  );
}
