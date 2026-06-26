import { useState } from "react";

import { reindexChangedWorkspace } from "../api/client";

/**
 * "Keep the AI up to date" — re-embeds only the files whose content changed
 * since the last index (incremental), so the model sees the latest code without
 * re-indexing the whole project. Self-contained so it doesn't add complexity to
 * the larger Settings panel.
 */
export function UpdateIndexSection({ workspaceId }: { workspaceId: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const update = async () => {
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
    } catch {
      setMessage("Could not update the index right now.");
    } finally {
      setBusy(false);
    }
  };

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
      <div className="settings-clean-actions">
        <button className="primary-button" type="button" disabled={busy} onClick={() => void update()}>
          {busy ? "Updating…" : "Update index (changed files)"}
        </button>
      </div>
      {message ? <p className="settings-message">{message}</p> : null}
    </section>
  );
}
