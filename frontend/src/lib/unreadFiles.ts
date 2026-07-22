// The one line that admits what the scan walked past.
//
// A project can be scanned, indexed and answering questions while every .bicep
// and .ps1 in it is invisible — found, counted, classified as "unknown", and
// dropped at the index step without a word. The person sees a project that has
// been read.
//
// So the count gets a line of its own, in the same register as the rest of the
// honest negatives here: a fact, not a warning. No icon, no amber, no banner.
// And when there is nothing to admit the line does not exist — no "0 files
// skipped", no green tick. A screen that is quiet when all is well is what
// teaches the eye to stop when the line does appear.
//
// The wording is deliberately not the backend's wording. That sentence is
// addressed to a model and tells it what to do about the gap; this one is
// addressed to a person and only tells them the gap is there.

// Past four extensions the line stops being a line.
const NAMED_EXTENSIONS = 4;

export function unreadFilesNote(byExtension: Record<string, number> | undefined | null): string {
  const entries = Object.entries(byExtension ?? {}).filter(([, count]) => count > 0);
  if (entries.length === 0) return "";

  // Most-common first, ties alphabetical: the same project always reads the same.
  entries.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  const named = entries
    .slice(0, NAMED_EXTENSIONS)
    .map(([extension, count]) => `${extension} ×${count}`);
  const remaining = entries.length - NAMED_EXTENSIONS;
  if (remaining > 0) named.push(`and ${remaining} more`);

  return `${total} ${total === 1 ? "file" : "files"} I can't read yet: ${named.join(", ")}`;
}
