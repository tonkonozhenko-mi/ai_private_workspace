import { useCallback, useEffect, useLayoutEffect, useState } from "react";

export interface TourStep {
  // CSS selector for the element to spotlight (must be on screen for the step).
  selector: string;
  title: string;
  body: string;
}

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const PAD = 8; // breathing room around the spotlighted element
const GAP = 12; // distance between the spotlight and the callout

/**
 * A one-time guided tour: it dims the screen, cuts a bright "spotlight" around a
 * real element, and shows a captioned callout pointing at it. Skippable, keyboard
 * friendly, and self-positioning. Purely presentational — the caller decides when
 * to open it and what to persist on close.
 */
export function SpotlightTour({
  steps,
  onClose,
}: {
  steps: TourStep[];
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);

  const step = steps[index];
  const isLast = index === steps.length - 1;

  const measure = useCallback(() => {
    if (!step) return;
    const el = document.querySelector(step.selector);
    if (!el) {
      setRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
  }, [step]);

  useLayoutEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [measure]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" || e.key === "Enter") {
        if (isLast) onClose();
        else setIndex((i) => Math.min(i + 1, steps.length - 1));
      } else if (e.key === "ArrowLeft") setIndex((i) => Math.max(i - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isLast, onClose, steps.length]);

  if (!step) return null;

  // Callout goes below the spotlight when there's room, otherwise above; clamped
  // to the viewport so it never runs off-screen. Falls back to top-centre when the
  // target element can't be found.
  const viewportW = window.innerWidth;
  const viewportH = window.innerHeight;
  const calloutW = Math.min(360, viewportW - 32);
  let calloutTop: number;
  let calloutLeft: number;
  if (rect) {
    const below = rect.top + rect.height + PAD + GAP;
    const wantAbove = below + 180 > viewportH;
    calloutTop = wantAbove ? Math.max(16, rect.top - PAD - GAP - 170) : below;
    calloutLeft = Math.min(Math.max(16, rect.left - PAD), viewportW - calloutW - 16);
  } else {
    calloutTop = 96;
    calloutLeft = Math.max(16, (viewportW - calloutW) / 2);
  }

  return (
    <div className="tour-overlay" role="dialog" aria-modal="true" aria-label={`Tour: ${step.title}`}>
      {rect ? (
        <div
          className="tour-spot"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
          }}
        />
      ) : (
        <div className="tour-dim" />
      )}
      <div className="tour-callout" style={{ top: calloutTop, left: calloutLeft, width: calloutW }}>
        <div className="tour-callout-head">
          <span className="tour-callout-title">{step.title}</span>
          <button type="button" className="tour-skip" onClick={onClose}>
            Skip
          </button>
        </div>
        <p className="tour-callout-body">{step.body}</p>
        <div className="tour-callout-foot">
          <span className="tour-count">
            {index + 1} of {steps.length}
          </span>
          <div className="tour-nav">
            {index > 0 ? (
              <button
                type="button"
                className="tour-btn"
                onClick={() => setIndex((i) => Math.max(i - 1, 0))}
              >
                Back
              </button>
            ) : null}
            <button
              type="button"
              className="tour-btn is-primary"
              onClick={() => (isLast ? onClose() : setIndex((i) => i + 1))}
            >
              {isLast ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
