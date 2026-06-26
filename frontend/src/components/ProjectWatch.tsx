import { useCallback, useEffect, useRef, useState } from "react";

import { getProjectWatch, runProjectWatch, summarizeProjectWatch } from "../api/client";
import type { ProjectWatchDigest, WorkspaceDashboard } from "../api/types";
import { AreaChip } from "./AreaChip";
import { ProjectWatchHistory } from "./ProjectWatchHistory";

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
  const [showAll, setShowAll] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  // Bumped after each check so the inline history re-fetches the new entry.
  const [historyKey, setHistoryKey] = useState(0);
  const [showHistory, setShowHistory] = useState(false);
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
    // A new check supersedes any earlier summary.
    setSummary(null);
    setSummaryError(null);
    try {
      const result = await runProjectWatch(workspaceId);
      setDigest(result);
      setHasDigest(true);
      // A check that found changes appends a history entry — refresh the timeline.
      setHistoryKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The check could not be completed.");
    } finally {
      setRunning(false);
    }
  }, [workspaceId]);

  const summarize = useCallback(async () => {
    setSummarizing(true);
    setSummaryError(null);
    try {
      const result = await summarizeProjectWatch(workspaceId);
      setSummary(result.summary);
      // The summary is saved onto the latest history entry — refresh the timeline.
      setHistoryKey((k) => k + 1);
    } catch (err) {
      setSummaryError(
        err instanceof Error ? err.message : "The summary could not be generated.",
      );
    } finally {
      setSummarizing(false);
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
        (() => {
          const git = digest.git_brief;
          const riskHighlights = digest.highlights.filter((h) => h.category === "risk");
          const structural = digest.highlights.filter((h) => h.category !== "risk");
          const hasGitWork = !!git && git.commit_count > 0;
          return (
            <>
              <p className="pw-summary">{digest.summary}</p>

              {/* Git brief: what the team actually did since last time. */}
              {git && git.lines.length > 1 ? (
                <p className="pw-git-line">{git.lines[1]}</p>
              ) : null}
              {git && git.authors.length > 0 && hasGitWork ? (
                <div className="pw-counts">
                  {git.areas.slice(0, 4).map((a) => (
                    <AreaChip key={a.area} area={a} className="pw-count pw-count-add" />
                  ))}
                </div>
              ) : null}

              {/* Optional one-tap LLM recap of the commits. */}
              {hasGitWork ? (
                <div className="pw-summarize">
                  {summary ? (
                    <p className="pw-summary-llm">{summary}</p>
                  ) : (
                    <button
                      type="button"
                      className="pw-link"
                      onClick={summarize}
                      disabled={summarizing}
                    >
                      {summarizing ? "Summarising…" : "Summarise the changes"}
                    </button>
                  )}
                  {summaryError ? <p className="pw-error">{summaryError}</p> : null}
                </div>
              ) : null}

              {/* Risks first — the part a person cares about. */}
              {riskHighlights.length > 0 ? (
                <ul className="pw-highlights">
                  {riskHighlights.map((h, i) => (
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
              ) : null}

              {/* Analyzer bookkeeping, tucked away. */}
              {structural.length > 0 ? (
                <>
                  <button type="button" className="pw-link" onClick={() => setShowAll((v) => !v)}>
                    {showAll
                      ? "Hide structural details"
                      : `Structural details (${structural.length})`}
                  </button>
                  {showAll ? (
                    <ul className="pw-highlights pw-highlights-muted">
                      {structural.map((h, i) => (
                        <li key={i} className="pw-highlight">
                          <span className={`pw-dot ${HIGHLIGHT_DOT[h.kind] ?? "pw-dot-new"}`} />
                          <span className="pw-highlight-text">{h.text}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </>
              ) : null}

              {!hasGitWork && riskHighlights.length === 0 && !digest.baseline ? (
                <p className="pw-muted">Nothing new to report.</p>
              ) : null}
            </>
          );
        })()
      ) : null}

      {/* Durable timeline of past checks — the digest above is just the latest. */}
      <div className="pw-history">
        <button
          type="button"
          className="pw-link"
          onClick={() => setShowHistory((v) => !v)}
          aria-expanded={showHistory}
        >
          {showHistory ? "Hide change history" : "View change history"}
        </button>
        {showHistory ? (
          <div className="pw-history-body">
            <ProjectWatchHistory key={historyKey} workspaceId={workspaceId} />
          </div>
        ) : null}
      </div>
    </section>
  );
}
