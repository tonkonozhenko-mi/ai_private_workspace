import { useEffect, useState } from "react";

import {
  getGgufDownload,
  getRerankerStatus,
  setRerankerEnabled,
  startGgufDownload,
  type RerankerStatus,
} from "../api/client";

/**
 * Opt-in "sharper search" (cross-encoder reranker) toggle.
 *
 * Turning it on downloads a small reranker model the first time, then starts the
 * llama.cpp reranking server. Everything degrades gracefully: if the model/engine
 * isn't available, Ask just keeps using plain hybrid retrieval.
 */
export function RerankerSetting() {
  const [status, setStatus] = useState<RerankerStatus | null>(null);
  const [busy, setBusy] = useState(false);
  // The state the toggle is moving toward while busy, so it doesn't look "off"
  // mid-download.
  const [pending, setPending] = useState<boolean | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void getRerankerStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  async function toggle(next: boolean) {
    setBusy(true);
    setPending(next);
    setMessage(null);
    try {
      if (next && status && !status.model_installed) {
        setMessage("Downloading the reranker model (~370 MB)…");
        const job = await startGgufDownload({ model_id: status.model_id });
        let installed = false;
        for (let attempt = 0; attempt < 1800; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          const current = await getGgufDownload(job.id);
          if (current.status === "succeeded") {
            installed = true;
            break;
          }
          if (current.status === "failed" || current.status === "cancelled") {
            setMessage("Reranker model download did not finish. Try again.");
            break;
          }
          if (typeof current.progress_percent === "number") {
            setMessage(`Downloading the reranker model… ${current.progress_percent}%`);
          }
        }
        if (!installed) {
          setBusy(false);
          return;
        }
      }
      const updated = await setRerankerEnabled(next);
      setStatus(updated);
      if (!next) {
        setMessage("Sharper search is off.");
      } else if (updated.running) {
        setMessage("Sharper search is on.");
      } else {
        setMessage(
          "Saved. The reranker runs with the built-in llama.cpp engine — switch this " +
            "project to llama.cpp for it to take effect.",
        );
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not change the setting.");
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  const enabled = pending !== null ? pending : (status?.enabled ?? false);

  return (
    <section className="panel settings-clean-card">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Search</p>
          <h3>Sharper search</h3>
          <p className="panel-helper">
            A reranker re-scores the top retrieved snippets with a cross-encoder, for
            more precise project sources. Works with the built-in llama.cpp engine and
            downloads a small model (~370 MB) the first time you turn it on.
          </p>
        </div>
      </div>
      <label className="settings-toggle-row">
        <span>
          <strong>Sharper search (reranker)</strong>
          <small>Slower per question, but more relevant retrieved sources.</small>
        </span>
        <input
          type="checkbox"
          role="switch"
          checked={enabled}
          disabled={busy || status === null}
          onChange={(event) => void toggle(event.target.checked)}
        />
      </label>
      {message ? <p className="settings-message">{message}</p> : null}
    </section>
  );
}
