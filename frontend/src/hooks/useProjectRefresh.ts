import { useCallback, useEffect, useState } from "react";

import { reindexChangedWorkspace, runProjectWatch } from "../api/client";
import type { ProjectWatchDigest } from "../api/types";

/**
 * Drives the Home "Refresh" action, with state kept in a **module-level store**
 * keyed by workspace id — not in the component. The Home tab unmounts when you
 * switch tabs, so component-local state would reset the button back to "Refresh"
 * and orphan the in-flight request. Holding it here means a refresh started on
 * one visit is still shown as running (and its result still lands) after you
 * leave the tab and come back.
 */

export type RefreshPhase = "idle" | "structure" | "knowledge";

export interface RefreshState {
  running: boolean;
  phase: RefreshPhase;
  knowledgeNote: string | null;
  error: string | null;
  // Set when a refresh finishes its structural step, so a remounted card can
  // adopt the fresh digest without waiting for its own reload.
  digest: ProjectWatchDigest | null;
  digestNonce: number;
}

const DEFAULT_STATE: RefreshState = {
  running: false,
  phase: "idle",
  knowledgeNote: null,
  error: null,
  digest: null,
  digestNonce: 0,
};

const store = new Map<string, RefreshState>();
const listeners = new Map<string, Set<() => void>>();

function getState(workspaceId: string): RefreshState {
  return store.get(workspaceId) ?? DEFAULT_STATE;
}

function setState(workspaceId: string, patch: Partial<RefreshState>): void {
  store.set(workspaceId, { ...getState(workspaceId), ...patch });
  listeners.get(workspaceId)?.forEach((notify) => notify());
}

function subscribe(workspaceId: string, notify: () => void): () => void {
  let set = listeners.get(workspaceId);
  if (!set) {
    set = new Set();
    listeners.set(workspaceId, set);
  }
  set.add(notify);
  return () => {
    set?.delete(notify);
  };
}

async function startRefresh(workspaceId: string): Promise<void> {
  // Guard against double-firing (e.g. a second click, or two mounted cards).
  if (getState(workspaceId).running) return;
  setState(workspaceId, {
    running: true,
    phase: "structure",
    error: null,
    knowledgeNote: null,
  });
  try {
    // 1) Structure + git: re-scan, refresh the map (skipped if unchanged) and
    //    record the dated change journal.
    const digest = await runProjectWatch(workspaceId);
    setState(workspaceId, {
      phase: "knowledge",
      digest,
      digestNonce: getState(workspaceId).digestNonce + 1,
    });
    // 2) AI knowledge: re-embed only changed files. Best-effort.
    try {
      const idx = await reindexChangedWorkspace(workspaceId);
      const parts: string[] = [];
      if (idx.reindexed_files) parts.push(`${idx.reindexed_files} re-indexed`);
      if (idx.removed_files) parts.push(`${idx.removed_files} removed`);
      setState(workspaceId, {
        knowledgeNote: parts.length
          ? `AI knowledge updated: ${parts.join(", ")}.`
          : "AI knowledge already up to date.",
      });
    } catch {
      /* reindex is best-effort within a refresh */
    }
  } catch (err) {
    setState(workspaceId, {
      error: err instanceof Error ? err.message : "The refresh could not be completed.",
    });
  } finally {
    setState(workspaceId, { running: false, phase: "idle" });
  }
}

export function useProjectRefresh(workspaceId: string): RefreshState & { refresh: () => void } {
  const [, forceRender] = useState(0);
  useEffect(
    () => subscribe(workspaceId, () => forceRender((n) => n + 1)),
    [workspaceId],
  );
  const refresh = useCallback(() => {
    void startRefresh(workspaceId);
  }, [workspaceId]);
  return { ...getState(workspaceId), refresh };
}
