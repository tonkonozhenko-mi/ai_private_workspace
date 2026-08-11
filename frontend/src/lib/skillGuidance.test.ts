// Reported live: "зробив зміни в Tester і зберіг, але коли повернувся —
// нічого не збереглося." Reproduced by reading, not by luck.
//
// The panel built what to save as `{...preferences, customInstructions: drafts}`
// — the whole batch of drafts filed under one key. But preferences are keyed by
// skill id, and everything downstream walks them by id, so that key was read by
// nobody. The panel said "Saved", the request carried the old text, and the old
// text came back. Three honest components, one shape nobody owned.
//
// The merge is a function over plain data now, which is what makes the mistake
// something a test can hold.

import { describe, expect, it } from "vitest";

import { applyGuidanceEdits, type SkillGuidanceEntry } from "./skillGuidance";

const SKILLS = ["developer", "devops", "tester"] as const;

function saved(): Record<string, SkillGuidanceEntry> {
  return {
    developer: { enabled: false, customInstructions: "Original developer text." },
    devops: { enabled: true, customInstructions: "Original devops text." },
    tester: { enabled: false, customInstructions: "Original tester text." },
  };
}

describe("editing skill guidance", () => {
  it("keeps the words that were typed", () => {
    // The whole complaint, in one assertion.
    const next = applyGuidanceEdits(SKILLS, saved(), {
      ...Object.fromEntries(SKILLS.map((id) => [id, saved()[id].customInstructions])),
      tester: "Check the risky flows first.",
    });

    expect(next.tester.customInstructions).toBe("Check the risky flows first.");
  });

  it("leaves the other skills exactly as they were", () => {
    const next = applyGuidanceEdits(SKILLS, saved(), { tester: "Edited." });

    expect(next.developer.customInstructions).toBe("Original developer text.");
    expect(next.devops.customInstructions).toBe("Original devops text.");
  });

  it("does not switch anything on or off", () => {
    // Editing wording is not activation — that follows the project's role. A
    // save that silently flipped a skill would be the same class of surprise.
    const next = applyGuidanceEdits(SKILLS, saved(), { tester: "Edited." });

    expect(next.devops.enabled).toBe(true);
    expect(next.tester.enabled).toBe(false);
    expect(next.developer.enabled).toBe(false);
  });

  it("covers every skill, including ones never edited", () => {
    // A skill missing from the result is a skill whose guidance disappears on
    // the next save.
    const next = applyGuidanceEdits(SKILLS, saved(), {});

    expect(Object.keys(next).sort()).toEqual([...SKILLS].sort());
  });

  it("ignores a key that is not a skill id", () => {
    // This is precisely the shape of the bug: a batch of drafts filed under
    // `customInstructions`. It must not be mistaken for a skill, and — more to
    // the point — it must not be the only place the drafts live.
    const next = applyGuidanceEdits(SKILLS, saved(), {
      customInstructions: "A batch, filed in the wrong place.",
      tester: "Edited.",
    } as Record<string, string>);

    expect(next.customInstructions).toBe(undefined);
    expect(next.tester.customInstructions).toBe("Edited.");
  });

  it("falls back to empty rather than undefined for a skill it has never seen", () => {
    const next = applyGuidanceEdits(["brand-new"], {}, {});

    expect(next["brand-new"]).toEqual({ enabled: false, customInstructions: "" });
  });
});
