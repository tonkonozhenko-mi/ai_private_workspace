import { useCallback, useEffect, useRef, useState } from "react";

import {
  addProjectMemory,
  deleteProjectMemory,
  listProjectMemory,
  pinProjectMemory,
} from "../api/client";
import type { ProjectMemoryItem, WorkspaceDashboard } from "../api/types";

// A note or a correction for everyday knowledge, plus the two high-value "why"
// types: the rationale behind a design choice, and how a past incident was fixed —
// the context a new model (or teammate) otherwise can't recover.
const KINDS: { value: string; label: string }[] = [
  { value: "note", label: "Note" },
  { value: "correction", label: "Correction" },
  { value: "architecture_decision", label: "Architecture decision (why)" },
  { value: "incident_solution", label: "Past incident fix" },
];

const KIND_LABEL: Record<string, string> = {
  note: "Note",
  decision: "Note",
  correction: "Correction",
  fact: "Note",
  qa: "Q&A",
  architecture_decision: "Architecture decision",
  incident_solution: "Incident fix",
};

export function ProjectMemory({ dashboard }: { dashboard: WorkspaceDashboard }) {
  const workspaceId = dashboard.workspace_id;
  const [items, setItems] = useState<ProjectMemoryItem[]>([]);
  const [text, setText] = useState("");
  const [kind, setKind] = useState("note");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The list is management, not the main job — keep it collapsed by default and
  // just confirm each add transiently, so the card stays clean.
  const [showList, setShowList] = useState(false);
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const confirmTimer = useRef<number | null>(null);

  const load = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    listProjectMemory(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setItems(res.items);
      })
      .catch(() => {});
  }, [workspaceId]);

  useEffect(() => {
    load();
    return () => {
      abortRef.current?.abort();
      if (confirmTimer.current) window.clearTimeout(confirmTimer.current);
    };
  }, [load]);

  const add = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || adding) return;
    setAdding(true);
    setError(null);
    try {
      await addProjectMemory(workspaceId, trimmed, kind);
      setText("");
      // Transient confirmation that fades — no need to expand the whole list.
      setJustAdded(trimmed);
      if (confirmTimer.current) window.clearTimeout(confirmTimer.current);
      confirmTimer.current = window.setTimeout(() => setJustAdded(null), 6000);
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

  // Edit = save a fresh item then drop the old one (keeps kind + pinned). No
  // dedicated update endpoint needed, and it stays atomic enough for a note.
  const saveEdit = useCallback(
    async (item: ProjectMemoryItem, nextText: string) => {
      const trimmed = nextText.trim();
      if (!trimmed || trimmed === item.text) {
        setEditingId(null);
        return;
      }
      try {
        await addProjectMemory(workspaceId, trimmed, item.kind, item.pinned);
        await deleteProjectMemory(workspaceId, item.id);
      } catch {
        /* best-effort */
      }
      setEditingId(null);
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

  // The handbook is stored as a memory item too; don't show it in the list.
  const visible = items.filter((i) => i.kind !== "handbook");

  return (
    <section className="pm-card">
      <header className="pm-head">
        <div>
          <p className="pm-eyebrow">Project memory</p>
          <h2 className="pm-title">What the app remembers</h2>
          <p className="pm-subtitle">
            Notes and corrections recorded here are fed into Ask and the
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

      {justAdded ? (
        <p className="pm-just-added" key={justAdded}>
          <span className="pm-just-added-tick">✓</span> Remembered: <span>{justAdded}</span>
        </p>
      ) : (
        <p className="pm-kinds-hint">
          Use <strong>Correction</strong> when the model gets something wrong (e.g. "prod is called
          prd here"); <strong>Note</strong> for anything else worth remembering.
        </p>
      )}

      {visible.length > 0 ? (
        <div className="pm-entries">
          <button
            type="button"
            className="pm-entries-toggle"
            onClick={() => setShowList((v) => !v)}
            aria-expanded={showList}
          >
            {showList ? "Hide entries" : `Show my entries (${visible.length})`}
          </button>
          {showList ? (
            <ul className="pm-list">
              {visible.map((item) => (
                <li key={item.id} className="pm-item">
                  <span className="pm-kind">{KIND_LABEL[item.kind] ?? item.kind}</span>
                  {editingId === item.id ? (
                    <>
                      <input
                        className="pm-edit-input"
                        value={editText}
                        autoFocus
                        onChange={(e) => setEditText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveEdit(item, editText);
                          if (e.key === "Escape") setEditingId(null);
                        }}
                      />
                      <div className="pm-actions">
                        <button type="button" className="pm-save" title="Save" onClick={() => saveEdit(item, editText)}>
                          Save
                        </button>
                        <button type="button" className="pm-del" title="Cancel" onClick={() => setEditingId(null)}>
                          ✕
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <span className="pm-text">{item.text}</span>
                      <div className="pm-actions">
                        <button
                          type="button"
                          className="pm-edit"
                          title="Edit"
                          onClick={() => {
                            setEditingId(item.id);
                            setEditText(item.text);
                          }}
                        >
                          ✎
                        </button>
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
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
