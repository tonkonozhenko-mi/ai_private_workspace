import { useCallback, useEffect, useRef, useState } from "react";

import {
  addProjectMemory,
  checkProjectMemoryContradictions,
  deleteProjectMemory,
  getProjectMemoryDuplicates,
  listProjectMemory,
  mergeProjectMemory,
  pinProjectMemory,
  setProjectMemoryStale,
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
  { value: "guardrail", label: "Guardrail (do not…)" },
];

const KIND_LABEL: Record<string, string> = {
  note: "Note",
  decision: "Note",
  correction: "Correction",
  fact: "Note",
  qa: "Q&A",
  architecture_decision: "Architecture decision",
  incident_solution: "Incident fix",
  guardrail: "Guardrail",
};

export function ProjectMemory({ dashboard }: { dashboard: WorkspaceDashboard }) {
  const workspaceId = dashboard.workspace_id;
  const [items, setItems] = useState<ProjectMemoryItem[]>([]);
  const [text, setText] = useState("");
  const [kind, setKind] = useState("note");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // When a new note looks like it contradicts/replaces existing ones, we hold the
  // candidates here and ask the user to supersede one or keep both — before saving.
  const [contradictions, setContradictions] = useState<ProjectMemoryItem[]>([]);
  // Clusters of near-duplicate notes, surfaced for a review-first merge.
  const [duplicates, setDuplicates] = useState<ProjectMemoryItem[][]>([]);
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
    getProjectMemoryDuplicates(workspaceId, { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted) setDuplicates(res.groups ?? []);
      })
      .catch(() => {});
  }, [workspaceId]);

  const mergeGroup = useCallback(
    async (group: ProjectMemoryItem[], keepId: string) => {
      const dropIds = group.filter((i) => i.id !== keepId).map((i) => i.id);
      await mergeProjectMemory(workspaceId, keepId, dropIds).catch(() => {});
      load();
    },
    [workspaceId, load],
  );

  useEffect(() => {
    load();
    return () => {
      abortRef.current?.abort();
      if (confirmTimer.current) window.clearTimeout(confirmTimer.current);
    };
  }, [load]);

  // Actually persist the note. When ``supersedes`` is set, the chosen older note
  // is retired by the backend so the project keeps one current answer.
  const doSave = useCallback(
    async (supersedes?: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      setAdding(true);
      setError(null);
      try {
        await addProjectMemory(workspaceId, trimmed, kind, false, supersedes);
        setText("");
        setContradictions([]);
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
    },
    [text, kind, workspaceId, load],
  );

  // Step 1: before saving, ask the backend if this note likely contradicts/
  // replaces existing ones. If so, surface them and let the user decide; if not
  // (or the check fails), just save.
  const add = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || adding) return;
    setError(null);
    try {
      const res = await checkProjectMemoryContradictions(workspaceId, trimmed, kind);
      if (res.candidates.length > 0) {
        setContradictions(res.candidates);
        return;
      }
    } catch {
      /* best-effort — a failed check must never block saving */
    }
    doSave();
  }, [text, kind, adding, workspaceId, doSave]);

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

  const confirmStillCorrect = useCallback(
    async (item: ProjectMemoryItem) => {
      await setProjectMemoryStale(workspaceId, item.id, false).catch(() => {});
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

      {contradictions.length > 0 ? (
        <div className="pm-contradiction">
          <p className="pm-contradiction-head">
            This may already be covered. Replace the old note, or keep both?
          </p>
          <ul className="pm-contradiction-list">
            {contradictions.map((c) => (
              <li key={c.id}>
                <span className="pm-text">{c.text}</span>
                <button
                  type="button"
                  className="pm-replace"
                  disabled={adding}
                  title="Retire this older note and save the new one in its place"
                  onClick={() => doSave(c.id)}
                >
                  Replace this
                </button>
              </li>
            ))}
          </ul>
          <div className="pm-contradiction-actions">
            <button type="button" className="pm-link" disabled={adding} onClick={() => doSave()}>
              Keep both
            </button>
            <button type="button" className="pm-link" onClick={() => setContradictions([])}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

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

      {duplicates.length > 0 ? (
        <div className="pm-duplicates">
          <p className="pm-duplicates-head">
            Possible duplicates — keep one, retire the rest?
          </p>
          {duplicates.map((group, gi) => (
            <div className="pm-dup-group" key={`dup-${gi}`}>
              {group.map((item) => (
                <div className="pm-dup-row" key={item.id}>
                  <span className="pm-text">{item.text}</span>
                  <button
                    type="button"
                    className="pm-replace"
                    title="Keep this one, retire the others in this group"
                    onClick={() => mergeGroup(group, item.id)}
                  >
                    Keep this
                  </button>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : null}

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
                <li key={item.id} className={`pm-item${item.stale ? " pm-item-stale" : ""}`}>
                  <span className="pm-kind">{KIND_LABEL[item.kind] ?? item.kind}</span>
                  {item.stale ? (
                    <span
                      className="pm-stale-badge"
                      title={
                        item.stale_reason
                          ? `${item.stale_reason} — confirm it's still true.`
                          : "A file this note references changed recently — confirm it's still true."
                      }
                    >
                      check?
                    </span>
                  ) : null}
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
                      {item.confidence_explanation &&
                      item.confidence_source &&
                      item.confidence_source !== "default" ? (
                        <span
                          className="pm-confidence"
                          title={`Confidence ${Math.round((item.confidence ?? 1) * 100)}% — ${item.confidence_explanation}`}
                        >
                          {item.confidence_explanation}
                        </span>
                      ) : null}
                      {item.grounding ? (
                        <span className="pm-grounding" title={`Source: ${item.grounding}`}>
                          {item.grounding}
                        </span>
                      ) : null}
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
                        {item.stale ? (
                          <button
                            type="button"
                            className="pm-still-ok"
                            title="Mark as still correct (clears the changed-file flag)"
                            onClick={() => confirmStillCorrect(item)}
                          >
                            Still correct
                          </button>
                        ) : null}
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
