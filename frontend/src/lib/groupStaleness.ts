/**
 * What a group card says about a member whose files have moved on.
 *
 * A group does not track its members' changes — it asks them. Each member's
 * workspace already knows what has changed on disk since it was last scanned;
 * the group reads that answer and turns it into a badge. Nothing is copied,
 * nothing is synchronised, and opening the project on its own shows the same
 * facts because they were never anywhere else.
 *
 * Silence is the good news: a member that is current gets no badge at all. A
 * screen that congratulates every repository for being fine is a screen you
 * stop reading.
 */

import type { ScanChanges } from "../api/types";

/**
 * The badge for one member, or null when there is nothing worth saying.
 *
 * Null in three cases, all of them "no news": nothing changed; no scan has ever
 * been taken, so there is no "since" to measure from; the check did not run.
 */
export function memberChangeBadge(changes: ScanChanges | null | undefined): string | null {
  if (!changes || !changes.has_baseline || !changes.changed) return null;
  const total = changes.added_count + changes.modified_count + changes.removed_count;
  if (total <= 0) return null;
  return `${total} ${total === 1 ? "file" : "files"} changed since last index`;
}

/**
 * The same change, spelled out: what a rescan would pick up. Fills the badge's
 * tooltip, so the headline stays one line and the detail is a hover away.
 */
export function memberChangeDetail(changes: ScanChanges | null | undefined): string | null {
  if (!memberChangeBadge(changes) || !changes) return null;
  const parts = [
    changes.added_count ? `${changes.added_count} added` : null,
    changes.modified_count ? `${changes.modified_count} changed` : null,
    changes.removed_count ? `${changes.removed_count} removed` : null,
  ].filter((part): part is string => part !== null);
  return parts.join(" · ");
}

/**
 * Which repositories, by the name the sources are labelled with, have files
 * newer than their index right now.
 *
 * Same arithmetic as the badge, asked from the other end: the badge asks "what
 * should this card say about this member?", this asks "of the repositories that
 * answered a question, which ones answered from an older reading of themselves?"
 * One rule, so a repository cannot be stale on Home and current in Ask.
 */
export function staleRepositoryNames(
  members: { workspace_id: string; name: string }[],
  changes: Record<string, ScanChanges | undefined>,
): Set<string> {
  const stale = new Set<string>();
  for (const member of members) {
    if (memberChangeBadge(changes[member.workspace_id])) stale.add(member.name);
  }
  return stale;
}
