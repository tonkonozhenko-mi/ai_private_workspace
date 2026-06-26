import { useCallback, useEffect, useRef, useState } from "react";

import {
  getProjectWatchHistory,
  recordProjectWatchHistory,
  runProjectWatch,
} from "../api/client";
import type { ProjectWatchHighlight, ProjectWatchHistoryEntry } from "../api/types";
import { AreaChip } from "./AreaChip";

function dayKey(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function isToday(iso: string | null | undefined): boolean {
  return !!iso && dayKey(iso) === dayKey(new Date().toISOString());
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Earlier";
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (isToday(iso)) return "Today";
  if (dayKey(iso) === dayKey(yesterday.toISOString())) return "Yesterday";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

// Group entries (already newest-first) into consecutive same-day buckets.
function groupByDay(entries: ProjectWatchHistoryEntry[]): { key: string; label: string; items: ProjectWatchHistoryEntry[] }[] {
  const groups: { key: string; label: string; items: ProjectWatchHistoryEntry[] }[] = [];
  for (const entry of entries) {
    const when = entry.checked_at || entry.created_at;
    const key = dayKey(when);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(entry);
    else groups.push({ key, label: dayLabel(when), items: [entry] });
  }
  return groups;
}

const HIGHLIGHT_DOT: Record<string, string> = {
  risk_added: "pw-dot-risk",
  risk_resolved: "pw-dot-resolved",
  analyzer_added: "pw-dot-new",
  entity_added: "pw-dot-new",
  count_added: "pw-dot-new",
  entity_removed: "pw-dot-removed",
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
  if (days < 30) return `${days} d ago`;
  return new Date(iso).toLocaleDateString();
}

function absoluteDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function countChips(counts: ProjectWatchHistoryEntry["counts"]): { label: string; tone: string }[] {
  const chips: { label: string; tone: string }[] = [];
  if (counts.findings_added) chips.push({ label: `${counts.findings_added} new risk(s)`, tone: "risk" });
  if (counts.findings_resolved) chips.push({ label: `${counts.findings_resolved} resolved`, tone: "resolved" });
  if (counts.entities_added) chips.push({ label: `${counts.entities_added} added`, tone: "add" });
  if (counts.entities_removed) chips.push({ label: `${counts.entities_removed} removed`, tone: "removed" });
  return chips;
}

function HighlightList({ items, muted }: { items: ProjectWatchHighlight[]; muted?: boolean }) {
  if (items.length === 0) return null;
  return (
    <ul className={`pw-highlights pwh-highlights${muted ? " pw-highlights-muted" : ""}`}>
      {items.map((h, i) => (
        <li key={i} className="pw-highlight">
          <span className={`pw-dot ${HIGHLIGHT_DOT[h.kind] ?? "pw-dot-new"}`} />
          <span className="pw-highlight-text">
            {!muted && h.severity && h.kind === "risk_added" ? (
              <span className={`pw-sev pw-sev-${h.severity}`}>{h.severity}</span>
            ) : null}
            {h.text}
          </span>
        </li>
      ))}
    </ul>
  );
}

function authorLine(entry: ProjectWatchHistoryEntry): string {
  const parts: string[] = [];
  if (entry.commit_count > 0) {
    parts.push(`${entry.commit_count} commit${entry.commit_count === 1 ? "" : "s"}`);
  }
  if (entry.authors.length > 0) parts.push(entry.authors.slice(0, 3).join(", "));
  return parts.join(" · ");
}

function HistoryEntryItem({ entry }: { entry: ProjectWatchHistoryEntry }) {
  const [open, setOpen] = useState(false);
  const chips = countChips(entry.counts);
  const when = entry.checked_at || entry.created_at;
  const subjects = entry.commit_subjects ?? [];
  const highlights = entry.highlights ?? [];
  const areas = entry.areas ?? [];
  const gitLines = entry.git_lines ?? [];
  const meta = authorLine(entry);
  return (
    <li className="pwh-item">
      <span className="pwh-dot" aria-hidden="true" />
      <div className="pwh-body">
        <div className="pwh-when">
          <span className="pwh-when-rel">{relativeTime(when)}</span>
          <span className="pwh-when-abs">{absoluteDate(when)}</span>
        </div>

        <p className="pwh-summary">{entry.summary}</p>

        {/* Secondary git line, e.g. "Most changes in applications (3 files)…". */}
        {gitLines.length > 1 ? <p className="pwh-git-line">{gitLines[1]}</p> : null}

        {/* Changed areas/services — hover a chip to see which files. */}
        {areas.length > 0 ? (
          <div className="pwh-chips">
            {areas.slice(0, 5).map((a) => (
              <AreaChip key={a.area} area={a} className="pwh-chip pwh-chip-add" />
            ))}
          </div>
        ) : null}

        {entry.llm_summary ? <p className="pw-summary-llm pwh-llm">{entry.llm_summary}</p> : null}

        {chips.length > 0 ? (
          <div className="pwh-chips">
            {chips.map((chip, i) => (
              <span key={i} className={`pwh-chip pwh-chip-${chip.tone}`}>
                {chip.label}
              </span>
            ))}
          </div>
        ) : null}

        {/* What actually changed, by service/entity — risks first. */}
        <HighlightList items={highlights.filter((h) => h.category === "risk")} />
        <HighlightList items={highlights.filter((h) => h.category !== "risk")} muted />

        {meta ? <p className="pwh-meta">{meta}</p> : null}

        {subjects.length > 0 ? (
          <>
            <button type="button" className="pw-link" onClick={() => setOpen((v) => !v)}>
              {open ? "Hide commits" : `Show commits (${subjects.length})`}
            </button>
            {open ? (
              <ul className="pwh-commits">
                {subjects.map((s, i) => (
                  <li key={i} className="pwh-commit">
                    {s}
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}
      </div>
    </li>
  );
}

export function ProjectWatchHistory({ workspaceId }: { workspaceId: string }) {
  const [entries, setEntries] = useState<ProjectWatchHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  // Auto-check at most once per mount; throttled to once per calendar day below.
  const autoRan = useRef(false);

  const reload = useCallback(
    async (signal?: AbortSignal) => {
      const res = await getProjectWatchHistory(workspaceId, { signal });
      if (!signal?.aborted) setEntries(res.entries);
    },
    [workspaceId],
  );

  const recordNow = useCallback(async () => {
    setChecking(true);
    setCheckError(null);
    try {
      await runProjectWatch(workspaceId);
      await reload();
    } catch {
      setCheckError("Could not check for changes right now.");
    } finally {
      setChecking(false);
    }
  }, [workspaceId, reload]);

  useEffect(() => {
    const controller = new AbortController();
    setEntries(null);
    setError(null);
    setCheckError(null);
    (async () => {
      try {
        await reload(controller.signal);
        // Auto-record a dated snapshot once per calendar day, so the journal fills
        // by the dates you open the app — without anyone clicking. This uses the
        // CHEAP git-only path: it just reads git (commits since last record), with
        // no file rescan, no graph rebuild and no re-indexing. The throttle key is
        // kept locally so it survives across tab switches within the same day.
        const key = `pwh-auto-${workspaceId}`;
        const today = dayKey(new Date().toISOString());
        let last: string | null = null;
        try {
          last = window.localStorage.getItem(key);
        } catch {
          last = null;
        }
        if (!autoRan.current && last !== today) {
          autoRan.current = true;
          try {
            window.localStorage.setItem(key, today);
          } catch {
            /* private mode / storage disabled — proceed without throttling */
          }
          setChecking(true);
          try {
            await recordProjectWatchHistory(workspaceId);
            await reload(controller.signal);
          } catch {
            /* best-effort: a failed auto-record must not break the view */
          } finally {
            if (!controller.signal.aborted) setChecking(false);
          }
        }
      } catch {
        if (!controller.signal.aborted) setError("The history could not be loaded.");
      }
    })();
    return () => controller.abort();
  }, [workspaceId, reload]);

  const header = (
    <div className="pwh-head">
      <div>
        <p className="pw-subtitle pwh-intro">
          A dated journal of what changed in the project — newest first. It fills automatically
          from git when you open the app on a new day (no rescan). “Check now” also re-scans the
          project to capture structural changes.
        </p>
      </div>
      <button type="button" className="pw-button" onClick={recordNow} disabled={checking}>
        {checking ? "Checking…" : "Check now"}
      </button>
    </div>
  );

  if (error) return <p className="pw-error">{error}</p>;
  if (entries === null) return <p className="pw-muted">Loading history…</p>;

  if (entries.length === 0) {
    return (
      <div className="pwh">
        {header}
        {checkError ? <p className="pw-error">{checkError}</p> : null}
        <div className="pwh-empty">
          <p className="pw-muted">
            {checking ? "Recording the first snapshot…" : "No changes recorded yet."}
          </p>
          <p className="pw-subtitle">
            The first check sets a baseline. From the next change onward, every check that finds
            something is saved here with its date — so you can see what changed and when.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="pwh">
      {header}
      {checkError ? <p className="pw-error">{checkError}</p> : null}
      {groupByDay(entries).map((group) => (
        <div key={group.key} className="pwh-group">
          <p className="pwh-date">{group.label}</p>
          <ol className="pwh-list">
            {group.items.map((entry) => (
              <HistoryEntryItem key={entry.id} entry={entry} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
