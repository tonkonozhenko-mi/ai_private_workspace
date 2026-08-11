import { describe, expect, it } from "vitest";

import type { CustomSkill, SkillPreferences, SkillPresetDefinition } from "../components/skillLibrary";
import {
  MAX_CUSTOM_SKILLS,
  liveDefaultId,
  migrateEditedRoleGuidance,
  resolveInstruction,
} from "./instructions";

function preset(id: string, name: string, defaultInstructions: string): SkillPresetDefinition {
  return {
    id: id as SkillPresetDefinition["id"],
    name,
    shortName: name,
    roleDescription: "",
    purpose: "",
    bestFor: "",
    exampleQuestions: [],
    defaultInstructions,
    recommendedFiles: [],
  };
}

const PRESETS = [
  preset("devops", "DevOps", "Answer as a DevOps/platform assistant."),
  preset("tester", "Tester / QA", "Answer as a QA / test engineer."),
];

function preferences(overrides: Record<string, string>): SkillPreferences {
  return Object.fromEntries(
    PRESETS.map((item) => [
      item.id,
      {
        enabled: false,
        customInstructions: overrides[item.id] ?? item.defaultInstructions,
      },
    ]),
  ) as SkillPreferences;
}

function ids() {
  let n = 0;
  return () => `custom-${(n += 1)}`;
}

describe("carrying edited role wording over to instructions", () => {
  it("keeps a sentence somebody wrote when the box it lived in goes away", () => {
    const { instructions } = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ devops: "Always mention rollback steps." }),
      [],
      [],
      ids(),
    );

    expect(instructions).toHaveLength(1);
    expect(instructions[0].instructions).toBe("Always mention rollback steps.");
    // Named so it is findable, and marked so it is not mistaken for a role.
    expect(instructions[0].name).toBe("DevOps (yours)");
  });

  it("does not hand everyone six instructions they never wrote", () => {
    // Untouched boxes hold the app's own default text. Copying that out would
    // turn a migration into clutter, and clutter is what this change removes.
    const { instructions } = migrateEditedRoleGuidance(PRESETS, preferences({}), [], [], ids());

    expect(instructions).toEqual([]);
  });

  it("ignores whitespace-only differences from the default", () => {
    const { instructions } = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ devops: "  Answer as a DevOps/platform assistant.  " }),
      [],
      [],
      ids(),
    );

    expect(instructions).toEqual([]);
  });

  it("does not bring back an instruction that was deleted", () => {
    // The role wording stays where it is — it is per-workspace data this cannot
    // edit — so without a record of what was already carried, every launch
    // would re-create what the person just threw away, for good.
    const first = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ tester: "Check the risky flows first." }),
      [],
      [],
      ids(),
    );
    expect(first.instructions).toHaveLength(1);

    const afterDeleting = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ tester: "Check the risky flows first." }),
      [],
      first.carriedSources,
      ids(),
    );

    expect(afterDeleting.instructions).toEqual([]);
  });

  it("does not duplicate one whose wording was then edited", () => {
    const first = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ tester: "Check the risky flows first." }),
      [],
      [],
      ids(),
    );
    const edited = [{ ...first.instructions[0], instructions: "Check the risky flows, briefly." }];

    const again = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ tester: "Check the risky flows first." }),
      edited,
      first.carriedSources,
      ids(),
    );

    expect(again.instructions).toHaveLength(1);
    expect(again.instructions[0].instructions).toBe("Check the risky flows, briefly.");
  });

  it("runs twice without duplicating the paragraph", () => {
    // It runs on load, and load happens on every start.
    const once = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ tester: "Check the risky flows first." }),
      [],
      [],
      ids(),
    );
    const twice = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ tester: "Check the risky flows first." }),
      once.instructions,
      once.carriedSources,
      ids(),
    );

    expect(twice.instructions).toHaveLength(1);
  });

  it("leaves instructions that already exist untouched", () => {
    const mine: CustomSkill[] = [
      { id: "custom-a", name: "Security reviewer", instructions: "Lead with secrets." },
    ];

    const { instructions } = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ devops: "Mention rollback." }),
      mine,
      [],
      ids(),
    );

    expect(instructions[0]).toEqual(mine[0]);
    expect(instructions).toHaveLength(2);
  });

  it("does not collide with an instruction that already has the name", () => {
    const mine: CustomSkill[] = [
      { id: "custom-a", name: "DevOps (yours)", instructions: "Something older." },
    ];

    const { instructions } = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ devops: "Mention rollback." }),
      mine,
      [],
      ids(),
    );

    expect(instructions.map((item) => item.name)).toEqual(["DevOps (yours)", "DevOps (yours 2)"]);
  });

  it("stops at the cap, and does not retry the ones it could not fit", () => {
    // Appending past the cap meant the tail was truncated on the next load and
    // re-created with fresh ids — churning the default's id out from under it.
    const full: CustomSkill[] = Array.from({ length: MAX_CUSTOM_SKILLS }, (_, index) => ({
      id: `custom-${index}`,
      name: `Mine ${index}`,
      instructions: `Text ${index}`,
    }));

    const { instructions, carriedSources } = migrateEditedRoleGuidance(
      PRESETS,
      preferences({ devops: "Mention rollback." }),
      full,
      [],
      ids(),
    );

    expect(instructions).toHaveLength(MAX_CUSTOM_SKILLS);
    expect(carriedSources).toEqual(["Mention rollback."]);
  });
});

describe("which instruction an answer uses", () => {
  const mine: CustomSkill[] = [
    { id: "a", name: "Security reviewer", instructions: "Lead with secrets." },
    { id: "b", name: "Plain steps", instructions: "Short numbered steps." },
  ];

  it("uses the standing default when the question says nothing", () => {
    expect(resolveInstruction(null, "b", mine)?.name).toBe("Plain steps");
  });

  it("lets one question override the default", () => {
    expect(resolveInstruction("a", "b", mine)?.name).toBe("Security reviewer");
  });

  it("treats an explicit None as none, not as the default", () => {
    // Without this there is no way to ask a single question without your
    // standing instruction, and a default you cannot step out of is a trap.
    expect(resolveInstruction("", "b", mine)).toBeNull();
  });

  it("sends nothing when there is no default and no choice", () => {
    expect(resolveInstruction(null, null, mine)).toBeNull();
  });

  it("sends nothing when the chosen instruction no longer exists", () => {
    expect(resolveInstruction("deleted", null, mine)).toBeNull();
  });
});

describe("a default that still names something", () => {
  const mine: CustomSkill[] = [{ id: "a", name: "Security reviewer", instructions: "Lead." }];

  it("forgets a default that was deleted", () => {
    // Otherwise Settings keeps saying an instruction is in force while the
    // answers stopped using one — the kind of lie that takes an hour to find.
    expect(liveDefaultId("gone", mine)).toBeNull();
  });

  it("keeps one that is still there", () => {
    expect(liveDefaultId("a", mine)).toBe("a");
  });

  it("has nothing to say about no default", () => {
    expect(liveDefaultId(null, mine)).toBeNull();
  });
});
