import { useState } from "react";

import type { WorkspaceTab } from "./appTabs";

// First-run orientation state is per-device UI state (not a synced setting), so it
// lives in localStorage: which tabs the user has already seen a caption for, and
// whether the guided tour has been completed.
const SEEN_TABS_KEY = "aiw.onboard.seenTabs";
const TOUR_KEY = "aiw.onboard.tourDone";

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

// One-line caption shown the first time a tab is opened, so a new user learns what
// each section is for. Auto-dismisses once seen. Complements the guided tour.
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
