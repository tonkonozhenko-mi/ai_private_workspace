// A failed model switch must always end as visible words, never an empty string.

import { describe, expect, it } from "vitest";

import { modelSwitchErrorMessage } from "./modelSwitchError";

describe("modelSwitchErrorMessage", () => {
  it("surfaces the backend's worded reason when there is one", () => {
    // The backend phrases the real cause; the UI must show exactly that.
    const err = new Error("Could not start Qwen3-0.6B: llama-server exited during startup");
    expect(modelSwitchErrorMessage(err, "answer")).toBe(
      "Could not start Qwen3-0.6B: llama-server exited during startup",
    );
  });

  it("never returns an empty string — the whole bug was a silent failure", () => {
    expect(modelSwitchErrorMessage(new Error("   "), "answer")).toBe(
      "Could not switch the answer model.",
    );
    expect(modelSwitchErrorMessage(undefined, "answer")).toBe(
      "Could not switch the answer model.",
    );
    expect(modelSwitchErrorMessage(null, "search")).toBe("Could not switch the search model.");
  });

  it("names the right object in the fallback", () => {
    expect(modelSwitchErrorMessage({}, "answer")).toBe("Could not switch the answer model.");
    expect(modelSwitchErrorMessage({}, "search")).toBe("Could not switch the search model.");
  });

  it("accepts a bare string error", () => {
    expect(modelSwitchErrorMessage("boom", "answer")).toBe("boom");
  });
});
