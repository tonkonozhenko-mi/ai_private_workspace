import { useMemo, useState } from "react";

import type { WorkspaceDashboard } from "../api/types";
import type { WorkspaceTab } from "./appTabs";

// First-run orientation state is per-device UI state (not a synced setting), so it
// lives in localStorage: whether the "Start here" card was dismissed, which steps
// the user has actioned, and which tabs they've already seen a caption for.
const DISMISS_KEY = "aiw.onboard.dismissed";
const DONE_KEY = "aiw.onboard.doneSteps";
const SEEN_TABS_KEY = "aiw.onboard.seenTabs";
const TOUR_KEY = "aiw.onboard.tourDone";

export function isTourDone(): boolean {
  try {
    return localStorage.getItem(TOUR_KEY) === "1";
  } catch {
    return false;
  }
}

export function markTourDone(): void {
  try {
    localStorage.setItem(TOUR_KEY, "1");
  } catch {
    /* ignore */
  }
}

function readSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    return new Set();
  }
}

function writeSet(key: string, value: Set<string>): void {
  try {
    localStorage.setItem(key, JSON.stringify([...value]));
  } catch {
    /* storage unavailable — orientation just won't persist, which is fine */
  }
}

function isDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

// One-line caption shown the first time a tab is opened, so a new user learns what
// each section is for without a modal tour. Auto-dismisses once seen.
const TAB_CAPTIONS: Partial<Record<WorkspaceTab, string>> = {
  overview: "Your project at a glance — status, what changed, and the next thing to do.",
  intelligence: "The architecture, risks and environments the app found in your project.",
  ask: "Ask anything about your project in plain words — answers come from your own files.",
  models: "Choose and manage the local AI model that runs on your computer.",
  settings: "Appearance, behaviour and per-project preferences.",
};

export function TabCaption({ tab }: { tab: WorkspaceTab }) {
  const caption = TAB_CAPTIONS[tab];
  const [seen, setSeen] = useState(() => readSet(SEEN_TABS_KEY).has(tab));
  if (!caption || seen) return null;
  const dismiss = () => {
    const next = readSet(SEEN_TABS_KEY);
    next.add(tab);
    writeSet(SEEN_TABS_KEY, next);
    setSeen(true);
  };
  return (
    <div className="tab-caption" role="note">
      <span className="tab-caption-text">{caption}</span>
      <button type="button" className="tab-caption-x" aria-label="Got it" onClick={dismiss}>
        Got it
      </button>
    </div>
  );
}

interface StartHereProps {
  dashboard: WorkspaceDashboard;
  modelsReady: boolean;
  onOpenModels: () => void;
  onOpenAsk: () => void;
  onOpenIntelligence: () => void;
  onTakeTour?: () => void;
}

interface Step {
  id: string;
  label: string;
  hint: string;
  actionLabel: string;
  onAction: () => void;
  done: boolean;
}

export function StartHereChecklist({
  dashboard,
  modelsReady,
  onOpenModels,
  onOpenAsk,
  onOpenIntelligence,
  onTakeTour,
}: StartHereProps) {
  const [dismissed, setDismissed] = useState(isDismissed);
  const [doneManual, setDoneManual] = useState<Set<string>>(() => readSet(DONE_KEY));

  const markDone = (id: string) => {
    const next = new Set(doneManual);
    next.add(id);
    writeSet(DONE_KEY, next);
    setDoneManual(next);
  };

  const steps = useMemo<Step[]>(() => {
    const events = dashboard.recent_events ?? [];
    const happened = (fragment: string) =>
      events.some((event) => (event.event_type ?? "").includes(fragment));
    const go = (id: string, navigate: () => void) => () => {
      markDone(id);
      navigate();
    };
    return [
      {
        id: "ai",
        label: "Get the local AI ready",
        hint: "Choose a model that runs on your computer — everything stays on your machine.",
        actionLabel: "Open Models",
        onAction: go("ai", onOpenModels),
        done: modelsReady || doneManual.has("ai"),
      },
      {
        id: "ask",
        label: "Ask your first question",
        hint: "Ask anything about your project in plain words. It answers from your files.",
        actionLabel: "Open Ask",
        onAction: go("ask", onOpenAsk),
        done: happened("question_asked") || doneManual.has("ask"),
      },
      {
        id: "intelligence",
        label: "Explore your project's map",
        hint: "See the architecture, risks and environments the app found for you.",
        actionLabel: "Open Intelligence",
        onAction: go("intelligence", onOpenIntelligence),
        done: doneManual.has("intelligence"),
      },
    ];
    // markDone is stable enough for this memo; deps are the real signals.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboard.recent_events, modelsReady, doneManual, onOpenModels, onOpenAsk, onOpenIntelligence]);

  const doneCount = steps.filter((step) => step.done).length;
  if (dismissed || doneCount === steps.length) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
    setDismissed(true);
  };

  const firstOpen = steps.findIndex((step) => !step.done);

  return (
    <section className="start-here" aria-label="Getting started">
      <div className="start-here-head">
        <div>
          <p className="start-here-title">Start here</p>
          <p className="start-here-sub">
            Three steps to get going. This goes away once you're set.
          </p>
        </div>
        <div className="start-here-head-right">
          {onTakeTour ? (
            <button type="button" className="start-here-tour" onClick={onTakeTour}>
              Take a quick tour
            </button>
          ) : null}
          <span className="start-here-count">
            {doneCount} of {steps.length}
          </span>
          <button type="button" className="start-here-x" aria-label="Dismiss" onClick={dismiss}>
            Dismiss
          </button>
        </div>
      </div>
      <ol className="start-here-steps">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`start-here-step${step.done ? " is-done" : ""}${
              index === firstOpen ? " is-current" : ""
            }`}
          >
            <span className="start-here-marker" aria-hidden="true">
              {step.done ? "✓" : index + 1}
            </span>
            <div className="start-here-body">
              <span className="start-here-step-label">{step.label}</span>
              <span className="start-here-step-hint">{step.hint}</span>
            </div>
            {step.done ? (
              <span className="start-here-done-tag">Done</span>
            ) : (
              <button
                type="button"
                className={`start-here-action${index === firstOpen ? " is-primary" : ""}`}
                onClick={step.onAction}
              >
                {step.actionLabel}
              </button>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
