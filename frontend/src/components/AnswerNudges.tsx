import { useEffect, useState } from "react";

import { getAnswerRatingNudges } from "../api/client";
import type { AnswerRatingNudge } from "../api/types";

// Quiet, dismissible suggestions derived from the user's recent 👍/👎. Fetched
// once per workspace; nudges are about accumulated history, so they don't need
// to react to every single rating.
export function AnswerNudges({
  workspaceId,
  onOpenModels,
  onOpenOverview,
}: {
  workspaceId: string;
  onOpenModels?: () => void;
  onOpenOverview?: () => void;
}) {
  const [nudges, setNudges] = useState<AnswerRatingNudge[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setDismissed(new Set());
    getAnswerRatingNudges(workspaceId)
      .then((res) => {
        if (!cancelled) setNudges(res.nudges);
      })
      .catch(() => {
        if (!cancelled) setNudges([]);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const visible = nudges.filter((n) => !dismissed.has(n.kind));
  if (visible.length === 0) return null;

  return (
    <div className="nudges">
      {visible.map((n) => {
        const action =
          n.action === "open_models"
            ? { label: "Open Models", run: onOpenModels }
            : n.action === "rebuild_context"
              ? { label: "Go to Home to rebuild", run: onOpenOverview }
              : null;
        return (
          <div key={n.kind} className="nudge">
            <div className="nudge-body">
              <strong className="nudge-title">{n.title}</strong>
              <span className="nudge-detail">{n.detail}</span>
            </div>
            <div className="nudge-actions">
              {action && action.run ? (
                <button type="button" className="nudge-action" onClick={action.run}>
                  {action.label}
                </button>
              ) : null}
              <button
                type="button"
                className="nudge-dismiss"
                aria-label="Dismiss"
                onClick={() => setDismissed((prev) => new Set(prev).add(n.kind))}
              >
                ✕
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
