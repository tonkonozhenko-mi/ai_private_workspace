/**
 * Merging edited skill guidance back into the saved preferences.
 *
 * This was three lines inside the Settings panel and it was wrong in a way
 * nothing could catch: it spread the preferences and set a key named
 * `customInstructions` beside them, holding every draft at once. But the
 * preferences are keyed by skill id, and the normaliser walks them by id — so
 * that key was never read. Edit the Tester guidance, press Save, and the panel
 * said "Saved" while the request carried the old text and the panel, reopened,
 * showed the old text back. Every layer behaved correctly on its own.
 *
 * It lives here, as a function over plain data, because that is what makes the
 * mistake expressible as a test.
 */

export interface SkillGuidanceEntry {
  enabled: boolean;
  customInstructions: string;
}

/**
 * The preferences to save: one entry per skill, keeping whether it is switched
 * on and taking its text from the draft being edited.
 *
 * `skillIds` is the full list of skills — passing it in keeps this free of the
 * skill library, and means a skill that gains an id later cannot be forgotten
 * here. A skill with no draft keeps the text it already had.
 */
export function applyGuidanceEdits(
  skillIds: readonly string[],
  current: Record<string, SkillGuidanceEntry | undefined>,
  drafts: Record<string, string | undefined>,
): Record<string, SkillGuidanceEntry> {
  const next: Record<string, SkillGuidanceEntry> = {};
  for (const id of skillIds) {
    const saved = current[id];
    const draft = drafts[id];
    next[id] = {
      // Editing the wording is not a way to switch a skill on or off.
      enabled: Boolean(saved?.enabled),
      customInstructions: draft ?? saved?.customInstructions ?? "",
    };
  }
  return next;
}
