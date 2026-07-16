// Two true sentences that read as a contradiction are one sentence too few.

import { describe, expect, it } from "vitest";

import { MAP_UNCHANGED_NOTE, reindexNote } from "./refreshNotes";

describe("reindexNote", () => {
  it("says what the search index took in, and says it is the search index", () => {
    const note = reindexNote({ reindexed_files: 1, removed_files: 0 });

    expect(note).toBe("Search index updated: 1 file re-indexed.");
    // The live complaint: this line and the map's line were printed together and
    // one appeared to deny the other. Now they name different things.
    expect(note).toContain("Search index");
    expect(MAP_UNCHANGED_NOTE).toContain("project map");
  });

  it("counts one file as a file", () => {
    expect(reindexNote({ reindexed_files: 3, removed_files: 1 })).toBe(
      "Search index updated: 3 files re-indexed, 1 file removed.",
    );
  });

  it("says nothing had changed rather than nothing happened", () => {
    expect(reindexNote({ reindexed_files: 0, removed_files: 0 })).toBe(
      "Search index already up to date — no file had changed.",
    );
  });

  it("mentions only what happened", () => {
    expect(reindexNote({ reindexed_files: 0, removed_files: 2 })).toBe(
      "Search index updated: 2 files removed.",
    );
  });
});
