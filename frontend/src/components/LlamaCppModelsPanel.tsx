import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import {
  cancelGgufDownload,
  deleteGgufModel,
  getGgufCatalog,
  getGgufDownload,
  listGgufDownloads,
  getLlamaRuntimeStatus,
  resolveGgufModel,
  setActiveBackend,
  startGgufDownload,
  startLlamaRuntime,
  switchLlamaRuntimeLlm,
  switchLlamaRuntimeEmbedding,
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
  onSelectionUpdated,
  mode = "manage",
}: {
  workspaceId?: string;
  onReady?: () => void;
  // Called after the active answer/search model changes, so a parent "current
  // setup" view can reload and stop showing the previous model.
  onSelectionUpdated?: () => Promise<void> | void;
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
  const [notice, setNotice] = useState<string | null>(null);
  const [customRepo, setCustomRepo] = useState("");
  const [customFile, setCustomFile] = useState("");
  const [customBusy, setCustomBusy] = useState(false);
  const [customJobKey, setCustomJobKey] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const pollers = useRef<Record<string, number>>({});

  // The setup flow advances only when the user clicks "Continue" below — never
  // automatically on mount — so picking "llama" shows this panel instead of
  // instantly skipping to indexing.
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  const refreshCatalog = useCallback(async () => {
    const all = await getGgufCatalog();
    // Rerankers are managed only via Settings ("Sharper search"), never as an
    // answer/search model here.
    setModels(all.filter((model) => model.model_type !== "reranker"));
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
        if (!cancelled) setModels(all.filter((model) => model.model_type !== "reranker"));
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

  // A download runs in the background on the server, so when this panel is
  // remounted (e.g. after toggling the engine and coming back) we re-attach to
  // any job still in flight instead of losing the progress bar.
  useEffect(() => {
    let cancelled = false;
    listGgufDownloads()
      .then((all) => {
        if (cancelled) return;
        const live = all.filter(
          (job) => job.status === "running" || job.status === "queued",
        );
        if (live.length === 0) return;
        setJobs((current) => {
          const next = { ...current };
          for (const job of live) next[job.model_id] = job;
          return next;
        });
        for (const job of live) poll(job.model_id, job.id);
      })
      .catch(() => {
        /* no active downloads to resume, or endpoint unavailable */
      });
    return () => {
      cancelled = true;
    };
  }, [poll]);

  const isInstalled = useCallback(
    (model: GgufCatalogItem) =>
      model.installed || jobs[model.id]?.status === "succeeded",
    [jobs],
  );

  const llmModels = (models ?? []).filter((m) => m.model_type === "llm");
  const embeddingModels = (models ?? []).filter((m) => m.model_type === "embedding");
  const embedModel =
    embeddingModels.find((m) => m.recommended) ?? embeddingModels[0];
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

  // If the models are downloaded and the bundled binary is present, bring the
  // engine up on its own — the user already chose llama.cpp and downloaded the
  // models, so they shouldn't have to press "Start engine" every visit. Runs at
  // most once per mount; the button stays as a manual fallback if it fails.
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (
      !autoStartedRef.current &&
      requiredInstalled &&
      runtime?.binary_available &&
      !runtime.running &&
      !starting
    ) {
      autoStartedRef.current = true;
      void startEngine();
    }
  }, [requiredInstalled, runtime?.binary_available, runtime?.running, starting]);

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

  async function applyWorkspaceSelection(llmId: string): Promise<boolean> {
    // This switch decides which engine embeds the search index. Swallowing a
    // failure here let onboarding build an index with the WRONG vectorizer
    // (observed live: built via Ollama, workspace selected llama.cpp → Ask
    // could never search it). Surface the failure and stop the flow instead.
    try {
      await setActiveBackend("llamacpp");
    } catch {
      setError(
        "Could not point search at the built-in engine. Press Start engine, then try again.",
      );
      return false;
    }
    if (!workspaceId) return true;
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
    return true;
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

  // Setup "Continue": make sure this workspace is recorded as llama.cpp (the
  // engine may already be running from another project, so auto-start didn't
  // apply the selection), then advance the setup flow.
  async function continueSetup() {
    const applied = await applyWorkspaceSelection(
      runtime?.active_llm_model ?? recommendedLlm?.id ?? "",
    );
    // Only advance when the engine switch actually took — otherwise the next
    // step would build the search index with the wrong vectorizer.
    if (applied) onReadyRef.current?.();
  }

  // Switch the running engine to a different, already-downloaded answer model.
  // Custom models (not in the catalog) are switched by their HF repo + filename.
  async function useModel(model: GgufCatalogItem) {
    setSwitchingId(model.id);
    setError(null);
    try {
      const ref = model.custom
        ? { repo_id: model.repo_id, filename: model.filename }
        : { model_id: model.id };
      const status = await switchLlamaRuntimeLlm(ref);
      setRuntime(status);
      await applyWorkspaceSelection(model.id);
      await refreshCatalog();
      await onSelectionUpdated?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not switch the answer model.");
    } finally {
      setSwitchingId(null);
    }
  }

  // Switch the running engine to a different, already-downloaded search model.
  // A different embedder is a different vector space, so the index must be
  // rebuilt afterwards — we say so rather than silently breaking search.
  async function useEmbeddingModel(model: GgufCatalogItem) {
    setSwitchingId(model.id);
    setError(null);
    setNotice(null);
    try {
      const status = await switchLlamaRuntimeEmbedding({ model_id: model.id });
      setRuntime(status);
      if (workspaceId) {
        await updateWorkspaceModelSelection(workspaceId, {
          provider: "llamacpp",
          model: model.id,
          model_type: "embedding",
          selected_reason: "Built-in llama.cpp engine",
        }).catch(() => {});
      }
      await refreshCatalog();
      await onSelectionUpdated?.();
      setNotice(`${model.name} is now your search model. Rebuild the project's search context to use it.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not switch the search model.");
    } finally {
      setSwitchingId(null);
    }
  }

  // Download a custom Hugging Face GGUF by repo + filename, then run the engine
  // on it. Works end-to-end: the engine starts the downloaded file directly.
  async function addCustomModel() {
    const repo = customRepo.trim();
    if (!repo) {
      setError("Enter a Hugging Face repo (e.g. bartowski/Qwen2.5-0.5B-Instruct-GGUF).");
      return;
    }
    setCustomBusy(true);
    setError(null);
    try {
      // The user only needs the repo — pick a good GGUF file automatically
      // (a specific filename can still be given to override).
      let file = customFile.trim();
      if (!file) {
        const resolved = await resolveGgufModel(repo);
        file = resolved.filename;
      }
      const key = `${repo}/${file}`;
      setCustomJobKey(key);
      let job = await startGgufDownload({ repo_id: repo, filename: file });
      setJobs((current) => ({ ...current, [key]: job }));
      for (
        let i = 0;
        i < 7200 && !["succeeded", "failed", "cancelled"].includes(job.status);
        i += 1
      ) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        try {
          job = await getGgufDownload(job.id);
        } catch {
          break;
        }
        setJobs((current) => ({ ...current, [key]: job }));
      }
      if (job.status !== "succeeded") {
        setError("Download did not finish. Check the repo and filename, then retry.");
        return;
      }
      const status = await switchLlamaRuntimeLlm({ repo_id: repo, filename: file });
      setRuntime(status);
      await applyWorkspaceSelection(key);
      setCustomRepo("");
      setCustomFile("");
      await refreshCatalog();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add that model.");
    } finally {
      setCustomBusy(false);
    }
  }

  async function removeModel(model: GgufCatalogItem) {
    if (!window.confirm(`Delete ${model.name}? The model file is removed from disk.`)) {
      return;
    }
    setDeletingId(model.id);
    setError(null);
    try {
      await deleteGgufModel(
        model.custom
          ? { repo_id: model.repo_id, filename: model.filename }
          : { model_id: model.id },
      );
      setExpandedId(null);
      await refreshCatalog();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the model.");
    } finally {
      setDeletingId(null);
    }
  }

  const anyDownloading = Object.values(jobs).some(
    (j) => j.status === "running" || j.status === "queued",
  );
  const customJob = customJobKey ? jobs[customJobKey] : undefined;

  function renderRow(model: GgufCatalogItem, kind: "llm" | "embedding") {
    const job = jobs[model.id];
    const pct = job?.progress_percent ?? null;
    const downloading = job?.status === "running" || job?.status === "queued";
    const installed = isInstalled(model);
    const active =
      kind === "llm"
        ? Boolean(model.active)
        : Boolean(runtime?.running) && runtime?.active_embedding_model === model.id;
    const state = active ? "done" : installed ? "done" : downloading ? "load" : "wait";
    // In the Models tab, an installed model can be expanded to show details and a
    // delete action.
    const canExpand = interactive && installed;
    const expanded = expandedId === model.id;
    const nameContent = (
      <>
        {model.name}
        <small>
          · {kind === "embedding" ? "search" : "answers"} · {formatGb(model.size_bytes)}
          {model.recommended ? " · recommended" : ""}
        </small>
      </>
    );
    return (
      <Fragment key={model.id}>
      <li className={`gr-check gr-check--${state}`}>
        <span className="gr-check-icon" aria-hidden="true">
          {downloading ? <span className="gr-check-spin" /> : null}
        </span>
        {canExpand ? (
          <button
            type="button"
            className="gr-check-name gr-check-name--button"
            aria-expanded={expanded}
            onClick={() => setExpandedId(expanded ? null : model.id)}
          >
            {nameContent}
            <span className="gr-check-caret" aria-hidden="true">{expanded ? "▴" : "▾"}</span>
          </button>
        ) : (
          <span className="gr-check-name">{nameContent}</span>
        )}
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
          interactive && runtime?.running ? (
            <button
              type="button"
              className="gr-check-use"
              disabled={switchingId !== null}
              onClick={() =>
                void (kind === "llm" ? useModel(model) : useEmbeddingModel(model))
              }
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
      {canExpand && expanded ? (
        <li className="gr-model-detail-row">
          <dl>
            <div><dt>Repository</dt><dd>{model.repo_id}</dd></div>
            <div><dt>File</dt><dd>{model.filename}</dd></div>
            <div><dt>Quantization</dt><dd>{model.quantization}</dd></div>
            <div><dt>Size</dt><dd>{formatGb(model.size_bytes)}</dd></div>
            <div><dt>Type</dt><dd>{model.model_type === "embedding" ? "search / embeddings" : "answers"}</dd></div>
            {model.min_ram_gb ? (
              <div><dt>Needs RAM</dt><dd>≥ {model.min_ram_gb} GB</dd></div>
            ) : null}
          </dl>
          <div className="gr-model-detail-actions">
            {active ? (
              <span className="gr-llama-note gr-llama-note--left">
                In use — switch to another model before deleting.
              </span>
            ) : (
              <>
                {runtime?.running ? (
                  <button
                    type="button"
                    className="gr-check-use"
                    disabled={switchingId !== null}
                    onClick={() =>
                      void (kind === "llm" ? useModel(model) : useEmbeddingModel(model))
                    }
                  >
                    {switchingId === model.id ? "Switching…" : "Use this model"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="gr-model-delete"
                  disabled={deletingId !== null}
                  onClick={() => void removeModel(model)}
                >
                  {deletingId === model.id ? "Deleting…" : "Delete model"}
                </button>
              </>
            )}
          </div>
        </li>
      ) : null}
      </Fragment>
    );
  }

  const installedLlm = llmModels.filter((m) => isInstalled(m));
  const addableLlm = llmModels.filter((m) => !isInstalled(m));
  const installedEmbedding = embeddingModels.filter((m) => isInstalled(m));
  const addableEmbedding = embeddingModels.filter((m) => !isInstalled(m));

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
    interactive ? (
      <span className="gr-llama-running">✓ Engine running — ready to use</span>
    ) : (
      <div className="gr-llama-running-row">
        <span className="gr-llama-running">✓ Engine running</span>
        <button
          className="getting-ready-cta"
          type="button"
          onClick={() => void continueSetup()}
        >
          Continue
        </button>
      </div>
    )
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
      {notice ? <p className="gr-llama-notice">{notice}</p> : null}

      <p className="gr-llama-section-label">Your engine models</p>
      <p className="gr-llama-subhead">Answer models</p>
      <ul className="getting-ready-checklist">
        {installedLlm.map((model) => renderRow(model, "llm"))}
      </ul>
      {installedEmbedding.length > 0 ? (
        <>
          <p className="gr-llama-subhead gr-llama-subhead--divided">Search models</p>
          <ul className="getting-ready-checklist">
            {installedEmbedding.map((model) => renderRow(model, "embedding"))}
          </ul>
        </>
      ) : null}
      <div className="getting-ready-actions">{engineCta}</div>

      <p className="gr-llama-section-label">Add a model</p>
      <p className="gr-llama-note">
        Download another answer or search model to switch to. Models are shared
        across all your projects.
      </p>
      {addableLlm.length > 0 ? (
        <>
          <p className="gr-llama-subhead">Answer models</p>
          <ul className="getting-ready-checklist">
            {addableLlm.map((model) => renderRow(model, "llm"))}
          </ul>
        </>
      ) : null}
      {addableEmbedding.length > 0 ? (
        <>
          <p className="gr-llama-subhead gr-llama-subhead--divided">Search models</p>
          <ul className="getting-ready-checklist">
            {addableEmbedding.map((model) => renderRow(model, "embedding"))}
          </ul>
        </>
      ) : null}

      <div className="gr-llama-custom">
        <p className="gr-llama-custom-title">Add your own model</p>
        <p className="gr-llama-note gr-llama-note--left">
          Paste a Hugging Face GGUF repo — the app picks a good quant and switches
          the engine to it. (Avoid repos tagged npu/mobilint or vocab-only files.)
        </p>
        <div className="gr-llama-custom-fields">
          <input
            type="text"
            value={customRepo}
            placeholder="Hugging Face repo, e.g. bartowski/Qwen2.5-0.5B-Instruct-GGUF"
            disabled={customBusy}
            onChange={(e) => setCustomRepo(e.target.value)}
          />
          <button
            type="button"
            className="gr-check-use"
            disabled={customBusy || !customRepo.trim()}
            onClick={() => void addCustomModel()}
          >
            {customBusy ? "Working…" : "Download & use"}
          </button>
        </div>
        {customBusy && customJob ? (
          <div className="install-progress">
            <div
              className={`install-progress-bar${
                customJob.progress_percent === null ? " is-indeterminate" : ""
              }`}
            >
              <span
                style={
                  customJob.progress_percent === null
                    ? undefined
                    : { width: `${customJob.progress_percent}%` }
                }
              />
            </div>
            <span className="install-progress-label">
              {customJob.progress_percent === null
                ? "Preparing…"
                : `${customJob.progress_percent}%`}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
