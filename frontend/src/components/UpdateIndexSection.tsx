import { useCallback, useEffect, useRef, useState } from "react";

import { previewChangedWorkspace, reindexChangedWorkspace } from "../api/client";
import type { WorkspaceIndexChangePreviewResponse } from "../api/types";

function dayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function readBool(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

/**
 * "Keep the AI up to date" — re-embeds only the files whose content changed
 * since the last index (incremental), so the model sees the latest code without
 * re-indexing the whole project. Shows a hint when the index is stale, and an
 * optional auto-update (off by default) that runs once per day on open.
 */
export function UpdateIndexSection({ workspaceId }: { workspaceId: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<WorkspaceIndexChangePreviewResponse | null>(null);
  const autoKey = `ai-index-auto-${workspaceId}`;
  const ranKey = `ai-index-auto-ran-${workspaceId}`;
  const [auto, setAuto] = useState(() => readBool(autoKey));
  const autoTried = useRef(false);

  const loadPreview = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const result = await previewChangedWorkspace(workspaceId, { signal });
        if (!signal?.aborted) setPreview(result);
        return result;
      } catch {
        return null;
      }
    },
    [workspaceId],
  );

  const update = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await reindexChangedWorkspace(workspaceId);
      if (result.reindexed_files === 0 && result.removed_files === 0) {
        setMessage("The AI is already up to date — nothing changed since the last index.");
      } else {
        const parts: string[] = [];
        if (result.reindexed_files) parts.push(`${result.reindexed_files} file(s) re-indexed`);
        if (result.removed_files) parts.push(`${result.removed_files} removed`);
        setMessage(`Updated the AI's knowledge: ${parts.join(", ")}.`);
      }
      await loadPreview();
    } catch {
      setMessage("Could not update the index right now.");
    } finally {
      setBusy(false);
    }
  }, [workspaceId, loadPreview]);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      const result = await loadPreview(controller.signal);
      // Optional auto-update: once per calendar day, only when something is
      // actually pending. Off by default; the user opts in below.
      if (
        result &&
        result.pending > 0 &&
        readBool(autoKey) &&
        !autoTried.current &&
        (() => {
          try {
            return window.localStorage.getItem(ranKey) !== dayKey();
          } catch {
            return true;
          }
        })()
      ) {
        autoTried.current = true;
        try {
          window.localStorage.setItem(ranKey, dayKey());
        } catch {
          /* storage disabled — proceed without throttling */
        }
        if (!controller.signal.aborted) void update();
      }
    })();
    return () => controller.abort();
  }, [workspaceId, loadPreview, update, autoKey, ranKey]);

  const toggleAuto = (next: boolean) => {
    setAuto(next);
    try {
      window.localStorage.setItem(autoKey, next ? "1" : "0");
    } catch {
      /* storage disabled — toggle is session-only */
    }
  };

  const pending = preview?.pending ?? 0;
  const hint =
    preview && preview.has_index && pending > 0
      ? `${pending} file(s) changed since the AI last indexed them.`
      : preview && preview.has_index && pending === 0
        ? "The AI's knowledge is up to date."
        : null;

  return (
    <section className="panel settings-clean-card">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Search index</p>
          <h3>Keep the AI up to date</h3>
          <p className="panel-helper">
            Re-embeds only the files that changed since the last index, so the model sees the
            latest code without re-indexing the whole project. Then just ask in Ask — e.g. “what
            changed today?”
          </p>
        </div>
      </div>
      {hint ? (
        <p className={pending > 0 ? "settings-message settings-hint-active" : "settings-message"}>
          {hint}
        </p>
      ) : null}
      <div className="settings-clean-actions">
        <button className="primary-button" type="button" disabled={busy} onClick={() => void update()}>
          {busy ? "Updating…" : "Update index (changed files)"}
        </button>
      </div>
      <label className="settings-inline-check">
        <input type="checkbox" checked={auto} onChange={(e) => toggleAuto(e.target.checked)} />
        <span>Auto-update changed files when I open this workspace (once a day)</span>
      </label>
      {message ? <p className="settings-message">{message}</p> : null}
    </section>
  );
}
