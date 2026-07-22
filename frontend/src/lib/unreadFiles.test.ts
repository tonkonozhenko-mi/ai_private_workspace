// The empty case is the one that matters most: silence, not reassurance.

import { describe, expect, it } from "vitest";

import { unreadFilesNote } from "./unreadFiles";

describe("unreadFilesNote", () => {
  it("names the extensions and adds up to the total", () => {
    expect(unreadFilesNote({ ".bicep": 12, ".ps1": 2 })).toBe(
      "14 files I can't read yet: .bicep ×12, .ps1 ×2",
    );
  });

  it("says nothing at all when nothing was skipped", () => {
    // Not "0 files skipped", not a tick — nothing. The line's absence is the
    // good news, and a line that appears on every project is a line nobody reads.
    expect(unreadFilesNote({})).toBe("");
    expect(unreadFilesNote(undefined)).toBe("");
    expect(unreadFilesNote(null)).toBe("");
  });

  it("counts one file as a file", () => {
    expect(unreadFilesNote({ ".bicep": 1 })).toBe("1 file I can't read yet: .bicep ×1");
  });

  it("orders by count, then alphabetically, so the same project always reads the same", () => {
    expect(unreadFilesNote({ ".zz": 3, ".aa": 3, ".mm": 9 })).toBe(
      "15 files I can't read yet: .mm ×9, .aa ×3, .zz ×3",
    );
  });

  it("stops naming after four and counts the rest", () => {
    const note = unreadFilesNote({ ".a": 5, ".b": 4, ".c": 3, ".d": 2, ".e": 1, ".f": 1 });

    expect(note).toBe("16 files I can't read yet: .a ×5, .b ×4, .c ×3, .d ×2, and 2 more");
    // The total still covers every file, including the ones it stopped naming.
    expect(note.startsWith("16 ")).toBe(true);
  });
});
