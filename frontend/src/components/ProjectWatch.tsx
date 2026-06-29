import { useCallback, useEffect, useRef, useState } from "react";

import { getProjectWatch, summarizeProjectWatch } from "../api/client";
import type { ProjectWatchDigest, WorkspaceDashboard } from "../api/types";
import { useProjectRefresh } from "../hooks/useProjectRefresh";
import { AreaChip } from "./AreaChip";

const REFRESH_PHASE_LABEL: Record<string, string> = {
  structure: "Updating project structure…",
  knowledge: "Updating the AI's knowledge…",
};

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
  const [showAll, setShowAll] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Refresh state lives in a module-level store keyed by workspace, so it
  // survives this card unmounting when the user switches tabs mid-refresh.
  const {
    running,
    phase,
    knowledgeNote,
    error,
    digest: refreshedDigest,
    digestNonce,
    refresh,
  } = useProjectRefresh(workspaceId);

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

  // When a (possibly off-tab) refresh produces a fresh digest, adopt it.
  useEffect(() => {
    if (refreshedDigest) {
      setDigest(refreshedDigest);
      setHasDigest(true);
    }
  }, [refreshedDigest, digestNonce]);

  // A new refresh supersedes any earlier LLM summary.
  useEffect(() => {
    if (running) {
      setSummary(null);
      setSummaryError(null);
    }
  }, [running]);

  const summarize = useCallback(async () => {
    setSummarizing(true);
    setSummaryError(null);
    try {
      const result = await summarizeProjectWatch(workspaceId);
      setSummary(result.summary);
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
              Re-scans the project, refreshes the map and the AI's knowledge of changed files, and
              reports what changed.
            </p>
          )}
        </div>
        <button type="button" className="pw-button" onClick={refresh} disabled={running}>
          {running ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {running ? (
        <div className="pw-progress" role="status" aria-live="polite">
          <div className="pw-progress-bar">
            <span
              className="pw-progress-fill"
              data-phase={phase}
              style={{ width: phase === "knowledge" ? "66%" : "33%" }}
            />
          </div>
          <p className="pw-progress-label">
            {REFRESH_PHASE_LABEL[phase] ?? "Refreshing…"}
          </p>
        </div>
      ) : null}

      {error ? <p className="pw-error">{error}</p> : null}
      {knowledgeNote ? <p className="pw-muted pw-knowledge-note">{knowledgeNote}</p> : null}

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

      {/* The full dated journal lives in one place — Intelligence › History. */}
      {digest ? (
        <p className="pw-muted pw-history-hint">
          The full dated history is in Intelligence › History.
        </p>
      ) : null}
    </section>
  );
}
