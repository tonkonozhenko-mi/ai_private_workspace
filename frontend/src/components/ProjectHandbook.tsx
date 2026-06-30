import { useCallback, useEffect, useRef, useState } from "react";

import { buildProjectHandbook, getProjectHandbook } from "../api/client";

// The project handbook is a short, deterministic summary built from the project
// map. It's not a document to read — it's working memory that's fed into every
// Ask and Investigate as background, so answers stay grounded in this project.
// It lives in Intelligence (next to the map it's derived from), not on Home.
export function ProjectHandbook({ workspaceId }: { workspaceId: string }) {
  const [handbook, setHandbook] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    getProjectHandbook(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setHandbook(res.has_handbook ? res.handbook ?? null : null);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [workspaceId]);

  const regen = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await buildProjectHandbook(workspaceId);
      setHandbook(res.handbook);
      setOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Build the project map first.");
    } finally {
      setBusy(false);
    }
  }, [workspaceId]);

  return (
    <div className="pm-handbook pi-handbook">
      <div className="pm-handbook-head">
        <span className="pm-eyebrow">
          Project handbook
          {handbook ? <span className="pm-handbook-badge">In use</span> : null}
        </span>
        <div className="pm-handbook-actions">
          {handbook ? (
            <button type="button" className="pm-link" onClick={() => setOpen((v) => !v)}>
              {open ? "Hide" : "View"}
            </button>
          ) : null}
          <button type="button" className="pm-link" onClick={regen} disabled={busy}>
            {busy ? "Generating…" : handbook ? "Regenerate" : "Generate"}
          </button>
        </div>
      </div>
      <p className="pm-muted">
        {handbook
          ? "Generated from the project map. It's fed into every Ask and Investigate as background, so answers stay grounded in this project — you don't have to do anything with it."
          : "Generate a short, deterministic summary of the project from the map. Once made, it's automatically used as background in every Ask and Investigate to keep answers grounded — it's working memory, not a document to read."}
      </p>
      {error ? <p className="pm-error">{error}</p> : null}
      {handbook && open ? <pre className="pm-handbook-text">{handbook}</pre> : null}
    </div>
  );
}
