import { useCallback, useEffect, useRef, useState } from "react";

import {
  addProjectMemory,
  buildProjectHandbook,
  deleteProjectMemory,
  getProjectHandbook,
  listProjectMemory,
  pinProjectMemory,
} from "../api/client";
import type { ProjectMemoryItem, WorkspaceDashboard } from "../api/types";

const KINDS: { value: string; label: string }[] = [
  { value: "note", label: "Note" },
  { value: "decision", label: "Decision" },
  { value: "correction", label: "Correction" },
  { value: "fact", label: "Fact" },
];

const KIND_LABEL: Record<string, string> = {
  note: "Note",
  decision: "Decision",
  correction: "Correction",
  fact: "Fact",
  qa: "Q&A",
};

export function ProjectMemory({ dashboard }: { dashboard: WorkspaceDashboard }) {
  const workspaceId = dashboard.workspace_id;
  const [items, setItems] = useState<ProjectMemoryItem[]>([]);
  const [text, setText] = useState("");
  const [kind, setKind] = useState("note");
  const [adding, setAdding] = useState(false);
  const [handbook, setHandbook] = useState<string | null>(null);
  const [handbookOpen, setHandbookOpen] = useState(false);
  const [handbookBusy, setHandbookBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    listProjectMemory(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setItems(res.items);
      })
      .catch(() => {});
    getProjectHandbook(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setHandbook(res.has_handbook ? res.handbook ?? null : null);
      })
      .catch(() => {});
  }, [workspaceId]);

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  const add = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || adding) return;
    setAdding(true);
    setError(null);
    try {
      await addProjectMemory(workspaceId, trimmed, kind);
      setText("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setAdding(false);
    }
  }, [text, kind, adding, workspaceId, load]);

  const remove = useCallback(
    async (id: string) => {
      await deleteProjectMemory(workspaceId, id).catch(() => {});
      load();
    },
    [workspaceId, load],
  );

  const togglePin = useCallback(
    async (item: ProjectMemoryItem) => {
      await pinProjectMemory(workspaceId, item.id, !item.pinned).catch(() => {});
      load();
    },
    [workspaceId, load],
  );

  const regenHandbook = useCallback(async () => {
    setHandbookBusy(true);
    setError(null);
    try {
      const res = await buildProjectHandbook(workspaceId);
      setHandbook(res.handbook);
      setHandbookOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Build the project map first.");
    } finally {
      setHandbookBusy(false);
    }
  }, [workspaceId]);

  // The handbook is stored as a memory item too; don't show it in the list.
  const visible = items.filter((i) => i.kind !== "handbook");

  return (
    <section className="pm-card">
      <header className="pm-head">
        <div>
          <p className="pm-eyebrow">Project memory</p>
          <h2 className="pm-title">What the app remembers</h2>
          <p className="pm-subtitle">
            Notes, decisions and corrections recorded here are fed into Ask and the
            Investigator — so answers improve over time. Stored locally, always editable.
          </p>
        </div>
      </header>

      {error ? <p className="pm-error">{error}</p> : null}

      <div className="pm-add">
        <select value={kind} onChange={(e) => setKind(e.target.value)} disabled={adding}>
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={text}
          placeholder="e.g. Production is called 'prd' in this repo"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
          disabled={adding}
        />
        <button type="button" onClick={add} disabled={adding || text.trim().length === 0}>
          {adding ? "Saving…" : "Remember"}
        </button>
      </div>

      {visible.length > 0 ? (
        <ul className="pm-list">
          {visible.map((item) => (
            <li key={item.id} className="pm-item">
              <span className="pm-kind">{KIND_LABEL[item.kind] ?? item.kind}</span>
              <span className="pm-text">{item.text}</span>
              <div className="pm-actions">
                <button
                  type="button"
                  className={`pm-pin${item.pinned ? " pm-pin-on" : ""}`}
                  title={item.pinned ? "Unpin" : "Pin"}
                  onClick={() => togglePin(item)}
                >
                  {item.pinned ? "★" : "☆"}
                </button>
                <button type="button" className="pm-del" title="Delete" onClick={() => remove(item.id)}>
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="pm-muted">Nothing recorded yet. Add a note, correction, or decision above.</p>
      )}

      <div className="pm-handbook">
        <div className="pm-handbook-head">
          <span className="pm-eyebrow">Project handbook</span>
          <div className="pm-handbook-actions">
            {handbook ? (
              <button type="button" className="pm-link" onClick={() => setHandbookOpen((v) => !v)}>
                {handbookOpen ? "Hide" : "View"}
              </button>
            ) : null}
            <button type="button" className="pm-link" onClick={regenHandbook} disabled={handbookBusy}>
              {handbookBusy ? "Generating…" : handbook ? "Regenerate" : "Generate"}
            </button>
          </div>
        </div>
        <p className="pm-muted">
          A distilled, deterministic summary of the project (from the map) that the models
          read as background.
        </p>
        {handbook && handbookOpen ? <pre className="pm-handbook-text">{handbook}</pre> : null}
      </div>
    </section>
  );
}
