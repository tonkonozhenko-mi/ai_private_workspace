// Four words for one idea, brought down to two.

import { describe, expect, it } from "vitest";

import {
  RECHECK_ENGINE,
  RESCAN_FILES,
  recheckEngineLabel,
  rescanLabel,
} from "./rescanLabels";

describe("rescan labels", () => {
  it("has exactly two idle forms, one per family", () => {
    // If a third label appears here, a button somewhere is inventing a new word
    // for something these two already mean.
    const idle = new Set([rescanLabel(false), recheckEngineLabel(false)]);
    expect(idle).toEqual(new Set([RESCAN_FILES, RECHECK_ENGINE]));
  });

  it("each family names its object", () => {
    // The point of the object-name is that the two are different actions — a
    // probe of the engine is not a re-read of files — so a person does not have
    // to remember which is which.
    expect(RECHECK_ENGINE).toContain("engine");
    expect(RESCAN_FILES).toContain("files");
  });

  it("switches to a busy form and back", () => {
    expect(rescanLabel(true)).not.toBe(rescanLabel(false));
    expect(recheckEngineLabel(true)).not.toBe(recheckEngineLabel(false));
  });
});
