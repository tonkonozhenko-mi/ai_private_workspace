// What the map was actually read from — the analyzers that FOUND something,
// not the ones that ran.
//
// Live on a Bicep project (0.7.4): the Intelligence header said the map was
// "read from your links and references, documents, tests and JavaScript and
// TypeScript code" — on a project with no JavaScript, no tests, and no
// documents. The header listed `analyzers_run`, and an analyzer runs on every
// project; whether it found anything is a different question. Naming a source
// that contributed nothing is a small lie, and small lies about what the app
// read are exactly the thing this app spends its effort not telling.
//
// The honest set is derivable without asking the backend anything new: every
// node in the project graph carries the analyzer that produced it, so the
// analyzers that appear on at least one node are precisely the ones that found
// something. This turns "ran" into "found".

const ANALYZER_SOURCES: Record<string, string> = {
  terraform: "Terraform files",
  terragrunt: "Terragrunt files",
  kubernetes: "Kubernetes manifests",
  helm: "Helm charts",
  github_actions: "GitHub Actions workflows",
  gitlab_ci: "GitLab CI files",
  python: "Python code",
  javascript: "JavaScript and TypeScript code",
  sql: "SQL files",
  tests: "tests",
  api: "API definitions",
  documentation: "documents",
  references: "links and references",
  ownership: "git history",
};

/** The human name for one analyzer, or a best-effort fallback. */
export function analyzerSourceLabel(analyzer: string): string {
  return ANALYZER_SOURCES[analyzer] ?? analyzer.replace(/_/g, " ");
}

/** The distinct analyzers that produced at least one node in the graph.
 *
 *  This is the "found something" set. It is deliberately computed from the
 *  nodes rather than trusted from a separate "ran" list, because the whole bug
 *  was that the two were being conflated. */
export function analyzersThatFound(nodes: { analyzer: string }[] | undefined | null): string[] {
  const seen = new Set<string>();
  for (const node of nodes ?? []) {
    if (node.analyzer) seen.add(node.analyzer);
  }
  return [...seen];
}

/** "Terraform files and Python code" — the sources a map was really built from.
 *
 *  Returns "" when nothing was found, so the caller can drop the whole "read
 *  from your …" clause rather than print an empty one. Order follows the
 *  analyzers given, so it is stable for a given graph. */
export function readFromClause(analyzers: string[]): string {
  const sources = [...new Set(analyzers.map(analyzerSourceLabel))];
  if (sources.length === 0) return "";
  if (sources.length <= 2) return sources.join(" and ");
  return `${sources.slice(0, -1).join(", ")} and ${sources[sources.length - 1]}`;
}
