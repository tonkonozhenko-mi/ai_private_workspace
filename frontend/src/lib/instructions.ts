// Two things were wearing the same word.
//
// "Skill" meant both the six built-in roles and the instructions a person writes
// themselves, and Settings edited them in one list. So the app taught one model
// on the Settings screen and a different one in Ask, where the roles had already
// been removed from the picker. Reported plainly: "why does Ask only show my own
// one — will only new ones appear there?"
//
// The split that holds:
//
//   Role        — which facts you care about. Six of them, fixed, chosen in the
//                 header. Reaches Home, Intelligence and Ask alike.
//   Instruction — how the answer should be written. Yours, any number, created
//                 in Settings. Reaches only the answer.
//
// This module owns the instruction side: which one is the default, and how the
// wording someone typed into a built-in role's box gets carried over rather than
// deleted when that box goes away.

import type { CustomSkill, SkillPreferences, SkillPresetDefinition } from "../components/skillLibrary";

// As many instructions of your own as the app will keep. One constant, because
// two places enforce it — the loader in skillLibrary and the migration below —
// and a cap that disagrees with itself drops what the other just accepted. It
// lives here rather than beside the loader so that src/lib stays importable on
// its own, which is what lets these functions be tested without a bundler.
export const MAX_CUSTOM_SKILLS = 20;

/**
 * The instruction to use, given a per-question choice and the standing default.
 *
 * The composer's picker offers "None", and "None" has to mean *no instruction* —
 * not "fall back to the default". Otherwise there is no way to ask one question
 * without your standing instruction, which is exactly the escape hatch a default
 * needs to be safe.
 */
export function resolveInstruction(
  perQuestionId: string | null,
  defaultId: string | null,
  instructions: CustomSkill[],
): CustomSkill | null {
  const chosen = perQuestionId === null ? defaultId : perQuestionId;
  if (!chosen) {
    return null;
  }
  return instructions.find((item) => item.id === chosen) ?? null;
}

/**
 * A default that still names something. An instruction can be deleted while it
 * is the default, and a dangling id would send nothing while Settings kept
 * claiming an instruction was in force.
 */
export function liveDefaultId(
  defaultId: string | null,
  instructions: CustomSkill[],
): string | null {
  if (!defaultId) {
    return null;
  }
  return instructions.some((item) => item.id === defaultId) ? defaultId : null;
}

function migratedName(presetName: string, taken: Set<string>): string {
  const base = `${presetName} (yours)`;
  if (!taken.has(base)) {
    return base;
  }
  for (let suffix = 2; suffix < 100; suffix += 1) {
    const candidate = `${presetName} (yours ${suffix})`;
    if (!taken.has(candidate)) {
      return candidate;
    }
  }
  return base;
}

export interface CarriedGuidance {
  instructions: CustomSkill[];
  /**
   * Every role wording this has ever carried, whatever became of the
   * instruction afterwards. Without it the migration cannot tell "never seen"
   * from "seen, and then deleted" — and would keep resurrecting something the
   * person threw away, on every launch, for good.
   */
  carriedSources: string[];
}

/**
 * Wording typed into a built-in role's box, carried out to an instruction of
 * one's own.
 *
 * Settings used to let you rewrite how each of the six roles phrases an answer.
 * That editor is gone — a role decides which facts you see, and rephrasing is
 * what an instruction is for. But somebody wrote those sentences, and removing
 * the box they live in is not a reason to delete them. Anything that still
 * matches the built-in default is left behind: it is the app's own text, not
 * theirs, and copying it back would hand every user six instructions they never
 * wrote.
 *
 * This runs on every load, because the role wording is per-workspace and a
 * workspace opened for the first time may bring some. That makes what it
 * remembers more important than what it copies: it records the source text, not
 * the instruction it produced, so deleting or rewriting the instruction after
 * the fact does not bring the original back.
 *
 * Pure, and takes its id generator, so the result can be asserted rather than
 * hoped for.
 */
export function migrateEditedRoleGuidance(
  presets: SkillPresetDefinition[],
  preferences: SkillPreferences,
  existing: CustomSkill[],
  alreadyCarried: string[],
  makeId: () => string,
): CarriedGuidance {
  const taken = new Set(existing.map((item) => item.name));
  const seen = new Set([...alreadyCarried, ...existing.map((item) => item.instructions.trim())]);
  const instructions = [...existing];
  const carriedSources = [...alreadyCarried];

  for (const preset of presets) {
    const written = preferences[preset.id]?.customInstructions?.trim() ?? "";
    if (!written || written === preset.defaultInstructions.trim() || seen.has(written)) {
      continue;
    }
    seen.add(written);
    // Recorded even when there is no room for it, so a full list does not turn
    // this into something that retries — and renames — forever.
    carriedSources.push(written);
    if (instructions.length >= MAX_CUSTOM_SKILLS) {
      continue;
    }
    const name = migratedName(preset.name, taken);
    taken.add(name);
    instructions.push({ id: makeId(), name, instructions: written });
  }

  return { instructions, carriedSources };
}
