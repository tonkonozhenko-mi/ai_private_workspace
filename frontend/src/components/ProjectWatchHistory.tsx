import { useEffect, useRef, useState } from "react";

import { getProjectWatchHistory } from "../api/client";
import type { ProjectWatchHighlight, ProjectWatchHistoryEntry } from "../api/types";
import { AreaChip } from "./AreaChip";

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
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    setEntries(null);
    setError(null);
    getProjectWatchHistory(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setEntries(res.entries);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("The history could not be loaded.");
      });
    return () => controller.abort();
  }, [workspaceId]);

  if (error) return <p className="pw-error">{error}</p>;
  if (entries === null) return <p className="pw-muted">Loading history…</p>;

  if (entries.length === 0) {
    return (
      <div className="pwh-empty">
        <p className="pw-muted">No changes recorded yet.</p>
        <p className="pw-subtitle">
          Each time a watch check finds changes, it is saved here as a timeline — so you can see
          what changed and when, even after the moment passes. Run a check in “Project watch” to
          start the record.
        </p>
      </div>
    );
  }

  return (
    <div className="pwh">
      <p className="pw-subtitle pwh-intro">
        A durable timeline of every check that found changes — newest first.
      </p>
      <ol className="pwh-list">
        {entries.map((entry) => (
          <HistoryEntryItem key={entry.id} entry={entry} />
        ))}
      </ol>
    </div>
  );
}
