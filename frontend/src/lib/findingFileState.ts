// Whether a risk still points at a file that exists.
//
// Live on 0.7.4: a Bicep file moved from `src/` to `infra/`, a rescan ran, and
// the Operational-risks panel kept naming `src/appservice.bicep` — a path the
// project no longer contains. The risk panel and the file map were telling two
// different stories about the same project. The map is a snapshot built at
// analysis time; a rescan updates the file list without rebuilding the map, so
// a finding can outlive the file it is about.
//
// This does not fix the snapshot — that is the "Rescan changed files" button's
// job — but it lets the panel be honest in the meantime: a finding whose file
// is no longer in the current scan is marked, rather than quietly asserting a
// path that has moved. Not knowing where a file went is not the same as it
// being where the finding remembers it.

export type FindingFileState = "present" | "gone" | "unknown";

/** Is the file a finding points at still in the project?
 *
 *  ``livePaths`` is the set of paths in the current scan. When it is absent
 *  (the scan has not loaded yet) the answer is "unknown", and the caller shows
 *  the finding plainly rather than marking it — an unloaded scan is not
 *  evidence a file is gone. A finding with no source file is "present": there
 *  is no path to have moved. */
export function findingFileState(
  sourceFile: string | null | undefined,
  livePaths: ReadonlySet<string> | null | undefined,
): FindingFileState {
  if (!sourceFile) return "present";
  if (!livePaths) return "unknown";
  return livePaths.has(sourceFile) ? "present" : "gone";
}
