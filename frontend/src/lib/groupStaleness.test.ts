// A member changed, a member did not, a member was never indexed — three cases,
// and only one of them has anything to say.
//
// Written in the vitest `describe/it/expect` style, and run today by the
// standalone harness (scripts/run-lib-tests.mjs) until a vitest runner exists.

import { describe, expect, it } from "vitest";

import {
  memberChangeBadge,
  memberChangeDetail,
  staleRepositoryNames,
} from "./groupStaleness";

const baseline = {
  has_baseline: true,
  changed: false,
  added_count: 0,
  removed_count: 0,
  modified_count: 0,
  current_file_count: 12,
  previous_file_count: 12,
};

describe("memberChangeBadge", () => {
  it("counts every kind of change into one number", () => {
    const badge = memberChangeBadge({
      ...baseline,
      changed: true,
      added_count: 2,
      modified_count: 3,
      removed_count: 1,
    });
    expect(badge).toBe("6 files changed since last index");
  });

  it("says file, not files, when there is one", () => {
    const badge = memberChangeBadge({ ...baseline, changed: true, modified_count: 1 });
    expect(badge).toBe("1 file changed since last index");
  });

  it("says nothing about a member that has not changed", () => {
    expect(memberChangeBadge(baseline)).toBeNull();
  });

  it("says nothing about a member that was never scanned", () => {
    // No baseline: there is no "since last index" to measure from. A badge here
    // would be inventing a comparison.
    expect(memberChangeBadge({ ...baseline, has_baseline: false, changed: true })).toBeNull();
  });

  it("says nothing when the check did not run", () => {
    expect(memberChangeBadge(null)).toBeNull();
    expect(memberChangeBadge(undefined)).toBeNull();
  });

  it("says nothing when the flag disagrees with the counts", () => {
    // changed=true with nothing to show is a badge with no content behind it.
    expect(memberChangeBadge({ ...baseline, changed: true })).toBeNull();
  });
});

describe("memberChangeDetail", () => {
  it("spells out only the kinds that happened", () => {
    const detail = memberChangeDetail({
      ...baseline,
      changed: true,
      added_count: 2,
      removed_count: 1,
    });
    expect(detail).toBe("2 added · 1 removed");
  });

  it("has nothing to spell out when there is no badge", () => {
    expect(memberChangeDetail(baseline)).toBeNull();
  });
});

describe("staleRepositoryNames", () => {
  const members = [
    { workspace_id: "ws-wiki", name: "Wiki" },
    { workspace_id: "ws-code", name: "Backend" },
  ];

  it("names only the repositories whose files moved past their index", () => {
    const stale = staleRepositoryNames(members, {
      "ws-wiki": { ...baseline, changed: true, modified_count: 2 },
      "ws-code": baseline,
    });
    expect(Array.from(stale)).toEqual(["Wiki"]);
  });

  it("names none when nothing has been checked", () => {
    expect(staleRepositoryNames(members, {}).size).toBe(0);
  });

  it("uses the same rule as the badge, so the two can never disagree", () => {
    // No baseline → no badge → not stale. Home and Ask say the same thing.
    const changes = { "ws-wiki": { ...baseline, has_baseline: false, changed: true } };
    expect(memberChangeBadge(changes["ws-wiki"])).toBeNull();
    expect(staleRepositoryNames(members, changes).size).toBe(0);
  });
});
