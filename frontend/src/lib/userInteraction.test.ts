// The gate that keeps folder walks off a cold launch.
//
// Getting this wrong is not a cosmetic matter in either direction: stuck false
// and no project ever reports its changes; stuck true and an app that opens on
// login asks macOS for folder access before the person has touched anything.
//
// The module reads `window` when it is imported, so each test installs its own
// fake window and then imports a fresh copy — which is why these are async, and
// why the harness had to learn to await before they could mean anything.

import { describe, expect, it } from "vitest";

function fakeWindow() {
  const listeners = new Map<string, Set<(e?: unknown) => void>>();
  return {
    listeners,
    addEventListener(type: string, fn: (e?: unknown) => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    },
    removeEventListener(type: string, fn: (e?: unknown) => void) {
      listeners.get(type)?.delete(fn);
    },
    fire(type: string) {
      // Snapshot before dispatch, deliberately: the listener under test removes
      // itself (and its twin) the moment it runs, so the set mutates mid-loop.
      // A real DOM dispatch copies the listener list for the same reason, and a
      // fake that iterates the live set would be a fake with different rules
      // from the thing it stands in for.
      const dispatching = [...(listeners.get(type) ?? [])];
      for (const fn of dispatching) fn();
    },
  };
}

let instance = 0;

async function loadFresh(win: unknown) {
  (globalThis as Record<string, unknown>).window = win;
  // A fresh module instance per test: the flag is module state by design (one
  // app, one answer), so the only honest reset is a new instance of the module.
  instance += 1;
  return import(`./userInteraction?${instance}`) as Promise<{
    hasUserInteracted: () => boolean;
  }>;
}

describe("hasUserInteracted", () => {
  it("is false before the person has done anything", async () => {
    const win = fakeWindow();
    const { hasUserInteracted } = await loadFresh(win);

    expect(hasUserInteracted()).toBe(false);
  });

  it("is true after a pointer goes down", async () => {
    const win = fakeWindow();
    const { hasUserInteracted } = await loadFresh(win);

    win.fire("pointerdown");

    expect(hasUserInteracted()).toBe(true);
  });

  it("is true after a key goes down", async () => {
    const win = fakeWindow();
    const { hasUserInteracted } = await loadFresh(win);

    win.fire("keydown");

    expect(hasUserInteracted()).toBe(true);
  });

  it("stops listening once it knows — it is a latch, not a counter", async () => {
    const win = fakeWindow();
    await loadFresh(win);

    expect(win.listeners.get("pointerdown")?.size).toBe(1);
    win.fire("pointerdown");

    expect(win.listeners.get("pointerdown")?.size).toBe(0);
    expect(win.listeners.get("keydown")?.size).toBe(0);
  });

  it("stays false where there is no window at all", async () => {
    // Server-side rendering, or a test importing it with no DOM: nothing to
    // listen to, and nothing is claimed.
    const { hasUserInteracted } = await loadFresh(undefined);

    expect(hasUserInteracted()).toBe(false);
  });
});
