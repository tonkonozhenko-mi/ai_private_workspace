// The one-line "what this project is", with the git clause dropped when there
// is no git to speak of.
//
// Live on a four-file Bicep project (0.7.4): "1 page. 0 commits by 0 people."
// The three zeros are not information — they are the shape of a sentence with
// nothing to put in it. A folder that was never a git repository, or a fresh
// one with no commits yet, has no commit story, and printing zeros invents the
// absence of one. The rule the rest of the app already follows: not knowing is
// not the same as knowing there is nothing, and neither is worth a sentence.

export interface GitSummary {
  is_repo?: boolean;
  total_commits?: number;
  contributors_count?: number;
  commits_last_7_days?: number;
}

/** The git half of the summary — "12 commits by 3 people, 2 this week" — or ""
 *  when there is nothing true to say. Empty means the caller prints no git
 *  clause at all, rather than a row of zeros. */
export function gitSummaryClause(git: GitSummary | null | undefined): string {
  if (!git || git.is_repo === false) return "";
  const commits = git.total_commits ?? 0;
  const people = git.contributors_count ?? 0;
  // No commits is the same nothing as no repository: a project can be a git
  // repo with an empty history, and "0 commits by 0 people" is still zeros.
  if (commits <= 0) return "";

  const commitWord = commits === 1 ? "commit" : "commits";
  let clause = `${commits.toLocaleString()} ${commitWord}`;
  if (people > 0) {
    clause += ` by ${people} ${people === 1 ? "person" : "people"}`;
  }
  const week = git.commits_last_7_days ?? 0;
  if (week > 0) clause += `, ${week} this week`;
  return `${clause}.`;
}

/** Join the "what it's made of" line with the git clause, dropping either side
 *  when it is empty so there is never a stray full stop or a leading space. */
export function projectSummaryLine(makeup: string, git: GitSummary | null | undefined): string {
  const gitClause = gitSummaryClause(git);
  const left = (makeup || "").trim();
  if (left && gitClause) return `${left} ${gitClause}`;
  return left || gitClause;
}
