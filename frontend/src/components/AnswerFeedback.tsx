import { useState } from "react";

type MemoryKind = "qa" | "correction";

// Turns a thumbs-up / thumbs-down into a concrete, local action:
//  - 👍 stores the Q&A so the app re-uses it for similar questions,
//  - 👎 opens a correction the app injects into future prompts.
// It never claims to retrain the model — only the app "remembers".
export function AnswerFeedback({
  question,
  answer,
  onSave,
  onRate,
}: {
  question: string;
  answer: string;
  onSave: (text: string, kind: MemoryKind) => Promise<unknown>;
  // Optional best-effort rating log (model + context), used only to derive nudges.
  onRate?: (verdict: "up" | "down") => void;
}) {
  const [mode, setMode] = useState<"idle" | "correcting" | "liked" | "corrected">("idle");
  const [correction, setCorrection] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function like() {
    if (saving) return;
    onRate?.("up");
    setSaving(true);
    setError(null);
    try {
      await onSave(`Q: ${question.trim()}\nA: ${answer.trim()}`, "qa");
      setMode("liked");
    } catch {
      setError("Could not save to memory.");
    } finally {
      setSaving(false);
    }
  }

  async function saveCorrection() {
    const text = correction.trim();
    if (!text || saving) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(text, "correction");
      setMode("corrected");
    } catch {
      setError("Could not save the correction.");
    } finally {
      setSaving(false);
    }
  }

  if (mode === "liked") {
    return (
      <p className="af-done">
        ✓ Saved this answer to memory — it'll be reused for similar questions.
      </p>
    );
  }
  if (mode === "corrected") {
    return <p className="af-done">✓ Correction saved — future answers will take it into account.</p>;
  }

  return (
    <div className="af">
      {mode === "idle" ? (
        <div className="af-row">
          <span className="af-label">Was this helpful?</span>
          <button type="button" className="af-btn" onClick={like} disabled={saving} title="Helpful — remember this answer" aria-label="Helpful">
            <Thumb />
          </button>
          <button
            type="button"
            className="af-btn"
            onClick={() => {
              onRate?.("down");
              setMode("correcting");
            }}
            disabled={saving}
            title="Not right — add a correction"
            aria-label="Not right"
          >
            <Thumb down />
          </button>
          <span className="af-hint">
            Doesn't retrain the model — 👍 remembers a good answer, 👎 adds a correction the app reuses.
          </span>
        </div>
      ) : (
        <div className="af-correct">
          <p className="af-correct-label">What's the correct answer, or what did it get wrong?</p>
          <textarea
            className="af-textarea"
            value={correction}
            rows={2}
            autoFocus
            placeholder="e.g. The lead devops is Serhii Sypalo — the answer named the wrong person."
            onChange={(e) => setCorrection(e.target.value)}
          />
          <div className="af-correct-actions">
            <button type="button" className="af-save" onClick={saveCorrection} disabled={saving || correction.trim().length === 0}>
              {saving ? "Saving…" : "Save correction"}
            </button>
            <button
              type="button"
              className="af-cancel"
              onClick={() => {
                setMode("idle");
                setCorrection("");
                setError(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {error ? <p className="af-error">{error}</p> : null}
    </div>
  );
}

function Thumb({ down = false }: { down?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <g transform={down ? "translate(0,24) scale(1,-1)" : undefined}>
        <path d="M7 10v11" />
        <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h1.76a2 2 0 0 0 1.79-1.11L12 4a2.5 2.5 0 0 1 3 1.88Z" />
      </g>
    </svg>
  );
}
