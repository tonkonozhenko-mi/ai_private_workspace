// "0 commits by 0 people" is the shape of a sentence with nothing in it.

import { describe, expect, it } from "vitest";

import { gitSummaryClause, projectSummaryLine } from "./projectSummaryLine";

describe("gitSummaryClause", () => {
  it("says the git story when there is one", () => {
    expect(
      gitSummaryClause({ is_repo: true, total_commits: 12, contributors_count: 3, commits_last_7_days: 2 }),
    ).toBe("12 commits by 3 people, 2 this week.");
  });

  it("drops the whole clause when the folder is not a repository", () => {
    expect(gitSummaryClause({ is_repo: false, total_commits: 0 })).toBe("");
  });

  it("drops the whole clause when a repository has no commits yet", () => {
    // The live bug: a fresh repo showed "0 commits by 0 people".
    expect(gitSummaryClause({ is_repo: true, total_commits: 0, contributors_count: 0 })).toBe("");
  });

  it("says nothing for missing data rather than guessing zeros", () => {
    expect(gitSummaryClause(null)).toBe("");
    expect(gitSummaryClause(undefined)).toBe("");
    expect(gitSummaryClause({})).toBe("");
  });

  it("counts one commit and one person as singular", () => {
    expect(gitSummaryClause({ is_repo: true, total_commits: 1, contributors_count: 1 })).toBe(
      "1 commit by 1 person.",
    );
  });

  it("omits the week when nothing happened this week", () => {
    expect(
      gitSummaryClause({ is_repo: true, total_commits: 40, contributors_count: 2, commits_last_7_days: 0 }),
    ).toBe("40 commits by 2 people.");
  });
});

describe("projectSummaryLine", () => {
  it("joins the makeup and the git clause with a single space", () => {
    expect(
      projectSummaryLine("Built with Bicep.", { is_repo: true, total_commits: 5, contributors_count: 1 }),
    ).toBe("Built with Bicep. 5 commits by 1 person.");
  });

  it("is just the makeup when there is no git story", () => {
    expect(projectSummaryLine("1 page.", { is_repo: true, total_commits: 0 })).toBe("1 page.");
  });

  it("never leaves a stray space or full stop", () => {
    expect(projectSummaryLine("", { is_repo: true, total_commits: 3 })).toBe("3 commits.");
    expect(projectSummaryLine("Built with Bicep.", null)).toBe("Built with Bicep.");
  });
});
