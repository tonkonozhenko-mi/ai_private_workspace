import { useCallback, useEffect, useRef, useState } from "react";

import { getProjectWatch, runProjectWatch } from "../api/client";
import type { ProjectWatchDigest, WorkspaceDashboard } from "../api/types";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return `${days} d ago`;
}

const HIGHLIGHT_DOT: Record<string, string> = {
  risk_added: "pw-dot-risk",
  risk_resolved: "pw-dot-resolved",
  analyzer_added: "pw-dot-new",
  entity_added: "pw-dot-new",
  count_added: "pw-dot-new",
  entity_removed: "pw-dot-removed",
};

export function ProjectWatch({ dashboard }: { dashboard: WorkspaceDashboard }) {
  const workspaceId = dashboard.workspace_id;
  const [digest, setDigest] = useState<ProjectWatchDigest | null>(null);
  const [hasDigest, setHasDigest] = useState<boolean | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    getProjectWatch(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (controller.signal.aborted) return;
        setHasDigest(res.has_digest);
        setDigest(res.digest ?? null);
      })
      .catch(() => {
        if (!controller.signal.aborted) setHasDigest(false);
      });
    return () => controller.abort();
  }, [workspaceId]);

  const check = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      const result = await runProjectWatch(workspaceId);
      setDigest(result);
      setHasDigest(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The check could not be completed.");
    } finally {
      setRunning(false);
    }
  }, [workspaceId]);

  return (
    <section className="pw-card">
      <header className="pw-head">
        <div className="pw-head-text">
          <p className="pw-eyebrow">Project watch</p>
          <h2 className="pw-title">What changed since last time</h2>
          {digest ? (
            <p className="pw-subtitle">
              Last checked {relativeTime(digest.checked_at)}
              {digest.previous_checked_at
                ? ` · compared to ${relativeTime(digest.previous_checked_at)}`
                : ""}
            </p>
          ) : (
            <p className="pw-subtitle">
              Re-scans the project and reports new environments, risks, cloud services and more.
            </p>
          )}
        </div>
        <button type="button" className="pw-button" onClick={check} disabled={running}>
          {running ? "Checking…" : "Check now"}
        </button>
      </header>

      {error ? <p className="pw-error">{error}</p> : null}

      {hasDigest === false && !digest && !running ? (
        <p className="pw-muted">No check has run yet. Run one to record a baseline.</p>
      ) : null}

      {digest ? (
        <>
          <p className="pw-summary">{digest.summary}</p>
          {digest.highlights.length > 0 ? (
            <ul className="pw-highlights">
              {digest.highlights.map((h, i) => (
                <li key={i} className="pw-highlight">
                  <span className={`pw-dot ${HIGHLIGHT_DOT[h.kind] ?? "pw-dot-new"}`} />
                  <span className="pw-highlight-text">
                    {h.severity && h.kind === "risk_added" ? (
                      <span className={`pw-sev pw-sev-${h.severity}`}>{h.severity}</span>
                    ) : null}
                    {h.text}
                  </span>
                </li>
              ))}
            </ul>
          ) : digest.baseline ? null : (
            <p className="pw-muted">Nothing new to report.</p>
          )}
        </>
      ) : null}
    </section>
  );
}
