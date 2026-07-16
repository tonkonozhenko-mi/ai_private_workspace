/**
 * What a refresh did, said so that two true sentences do not read as a
 * contradiction.
 *
 * A refresh does two separate things at two separate levels: it re-embeds the
 * files that changed (so search finds them), and it rebuilds the project map (so
 * the facts are current). One panel managed to print both at once —
 *
 *   "AI knowledge updated: 1 re-indexed."
 *   "Nothing new to report."
 *
 * — which is a flat contradiction to read, and neither line was wrong. A file
 * changed; the map it produces did not. Both sentences now say which level they
 * are talking about, so they stack instead of arguing.
 */

export interface ReindexCounts {
  reindexed_files: number;
  removed_files: number;
}

/** The file level: what the search index took in. */
export function reindexNote(counts: ReindexCounts): string {
  const parts = [
    counts.reindexed_files
      ? `${counts.reindexed_files} ${counts.reindexed_files === 1 ? "file" : "files"} re-indexed`
      : null,
    counts.removed_files
      ? `${counts.removed_files} ${counts.removed_files === 1 ? "file" : "files"} removed`
      : null,
  ].filter((part): part is string => part !== null);
  if (parts.length === 0) return "Search index already up to date — no file had changed.";
  return `Search index updated: ${parts.join(", ")}.`;
}

/** The map level: what the rebuilt map turned out to say. Named as the map, so
 *  "nothing new" cannot be read as a denial of the line above it. */
export const MAP_UNCHANGED_NOTE = "The project map is unchanged — nothing new to report.";
