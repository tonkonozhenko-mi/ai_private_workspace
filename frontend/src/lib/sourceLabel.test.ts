// The label under every answer, in three components. It gets a path and returns
// what a person reads — so what it must never do is answer a question it was not
// asked.

import { describe, expect, it } from "vitest";

import { formatSourceLabel, HANDBOOK_PSEUDO_PATH } from "./sourceLabel";

describe("formatSourceLabel", () => {
  it("passes a real path through untouched", () => {
    expect(formatSourceLabel("docs/adr/0008-report-storage.md")).toBe(
      "docs/adr/0008-report-storage.md",
    );
  });

  it("gives the handbook pseudo-document its human name", () => {
    expect(formatSourceLabel(HANDBOOK_PSEUDO_PATH)).toBe("Project handbook");
  });

  // The lookup used to be a plain object, which answers for every name
  // Object.prototype carries. `?? sourcePath` cannot rescue that: the object had
  // already replied, with a function.
  for (const inherited of ["constructor", "toString", "valueOf", "hasOwnProperty", "__proto__"]) {
    it(`treats a file called ${inherited} as a file, not as Object.prototype`, () => {
      expect(formatSourceLabel(inherited)).toBe(inherited);
      expect(typeof formatSourceLabel(inherited)).toBe("string");
    });
  }

  it("keeps a path that merely contains a pseudo path", () => {
    expect(formatSourceLabel(`docs/${HANDBOOK_PSEUDO_PATH}.md`)).toBe(
      `docs/${HANDBOOK_PSEUDO_PATH}.md`,
    );
  });
});
