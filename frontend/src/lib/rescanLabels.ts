// Two verbs for "make it current", not four.
//
// Live on 0.7.4: four buttons across the app said one idea four ways —
// "Refresh" (Home / what changed), "Re-check" (Models / engine status),
// "Update index (changed files)" (Settings), "Re-read the files"
// (Intelligence). A person should not have to hold a table of which word means
// which. Two of these check the engine; the others re-read the project's files.
// So there are two verbs, and each names its object, so the difference is on
// the button rather than in the reader's memory.
//
// The two families are genuinely different actions — a probe of the local
// engine is not a re-read of your files — which is why they keep two labels
// rather than collapsing to one. Everything within a family shares a label.

/** Ask the local engine whether it is up and which models it has. Cheap, no
 *  files touched. */
export const RECHECK_ENGINE = "Re-check engine";
export const RECHECK_ENGINE_BUSY = "Re-checking…";

/** Read the project's files again to bring the map, the index and the
 *  "what changed" view up to date. */
export const RESCAN_FILES = "Rescan changed files";
export const RESCAN_FILES_BUSY = "Rescanning…";

/** The label for a rescan-family button, idle or busy. Kept as a function so a
 *  component never assembles the pair itself and drifts. */
export function rescanLabel(busy: boolean): string {
  return busy ? RESCAN_FILES_BUSY : RESCAN_FILES;
}

export function recheckEngineLabel(busy: boolean): string {
  return busy ? RECHECK_ENGINE_BUSY : RECHECK_ENGINE;
}
