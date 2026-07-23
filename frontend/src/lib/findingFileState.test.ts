// A risk that names a file the project no longer has is the panel disagreeing
// with the map about the same project.

import { describe, expect, it } from "vitest";

import { findingFileState } from "./findingFileState";

describe("findingFileState", () => {
  const live = new Set(["infra/appservice.bicep", "scripts/deploy.ps1"]);

  it("is present when the file is still in the scan", () => {
    expect(findingFileState("infra/appservice.bicep", live)).toBe("present");
  });

  it("is gone when the file moved out from under the finding", () => {
    // The live bug: the finding still said src/, the file is now under infra/.
    expect(findingFileState("src/appservice.bicep", live)).toBe("gone");
  });

  it("is unknown while the scan has not loaded — an absent scan is not evidence", () => {
    expect(findingFileState("src/appservice.bicep", null)).toBe("unknown");
    expect(findingFileState("src/appservice.bicep", undefined)).toBe("unknown");
  });

  it("is present when a finding names no file, since no path can have moved", () => {
    expect(findingFileState(null, live)).toBe("present");
    expect(findingFileState("", live)).toBe("present");
  });
});
