import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { formatModelLabel } from "../lib/modelLabel";

// models_summary.selected_llm is a provider-qualified id like
// "llamacpp/Org/Repo-GGUF/file.Q4_K_M.gguf" — unreadable in body copy.
function humanizeSelectedModel(selected: string | null): string | null {
  if (!selected) return null;
  const [provider, ...rest] = selected.split("/");
  if (rest.length === 0) return selected;
  return formatModelLabel(provider, rest.join("/"));
}

import {
  generateProjectUnderstanding,
  getProjectIntelligence,
  getProjectUnderstanding,
  getWorkspaceGitInsights,
  getWorkspaceJob,
  getWorkspaceLatestScan,
  getWorkspaceScanChanges,
  getWorkspaceTodos,
} from "../api/client";
import type {
  GitInsightsResponse,
  ProjectGraphFinding,
  ProjectIntelligenceResponse,
  ProjectFileResponse,
  ProjectScanResponse,
  ProjectTodosResponse,
  ProjectUnderstandingResponse,
  ScanChanges,
  WorkspaceDashboard,
  WorkspaceJob,
} from "../api/types";

// The on-disk change check walks the project folder, which makes macOS prompt
// for folder access. We only run it AFTER the user has interacted with the app,
// so the prompt is tied to deliberate use — never to a silent cold launch.
let userHasInteracted = false;
if (typeof window !== "undefined") {
  const mark = () => {
    userHasInteracted = true;
    window.removeEventListener("pointerdown", mark);
    window.removeEventListener("keydown", mark);
  };
  window.addEventListener("pointerdown", mark);
  window.addEventListener("keydown", mark);
}

async function pollJobDone(
  workspaceId: string,
  jobId: string,
  onProgress?: (job: WorkspaceJob) => void,
): Promise<void> {
  for (let attempt = 0; attempt < 900; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    try {
      const job: WorkspaceJob = await getWorkspaceJob(workspaceId, jobId);
      // The job already knows exactly where it is — it just was not being asked. The
      // banner used to say "Rebuilding search context…" for minutes with no sign of
      // life, which is indistinguishable from being hung.
      onProgress?.(job);
      if (["completed", "failed", "cancelled"].includes(job.status)) return;
    } catch {
      // keep polling through transient errors
    }
  }
}

/** "2,112 of 3,232 pieces · 65%" — the job's own numbers, or its own words. */
function jobProgressLine(job: WorkspaceJob): string {
  const parts: string[] = [];
  if (job.progress_current !== null && job.progress_total) {
    parts.push(`${job.progress_current.toLocaleString()} of ${job.progress_total.toLocaleString()}`);
  }
  if (job.progress_percent !== null) parts.push(`${Math.round(job.progress_percent)}%`);
  const step = job.current_step ?? job.message ?? "";
  return [step, parts.join(" · ")].filter(Boolean).join(" · ");
}

// Some local models return the deep analysis wrapped in a ```json code block
// (sometimes truncated). Salvage the human summary instead of dumping raw JSON.
function cleanAnalysisSummary(raw: string): string {
  if (!raw) return raw;
  // Strip a leading ```json fence (even when the closing fence is missing because
  // the model's output was truncated), then salvage the human summary.
  let text = raw.trim().replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/i, "").trim();
  if (text.startsWith("{")) {
    try {
      const parsed = JSON.parse(text) as { summary?: unknown };
      if (typeof parsed.summary === "string") return parsed.summary;
    } catch {
      // Truncated/invalid JSON — pull just the summary string out by regex.
    }
    const match = text.match(/"summary"\s*:\s*"((?:[^"\\]|\\.)*)"/);
    if (match) return match[1].replace(/\\"/g, '"').replace(/\\n/g, " ");
  }
  return raw;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return new Date(iso).toLocaleDateString();
}

// Human-readable span since the first commit, e.g. "8 months" or "12 days".
function humanAge(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const days = Math.max(0, Math.round((Date.now() - then) / 86400000));
  if (days < 1) return "today";
  if (days < 30) return `${days} day${days === 1 ? "" : "s"}`;
  const months = Math.round(days / 30.4);
  if (months < 12) return `${months} month${months === 1 ? "" : "s"}`;
  const years = (days / 365).toFixed(days < 730 ? 1 : 0);
  return `${years} year${years === "1" ? "" : "s"}`;
}

// What a project is made of, said in its own terms. The map already knows: it has
// pages, or modules, or tables, or pipelines — and NOT the other things. Home used to
// announce technologies ("Built with Terraform, Python") and, when there were none,
// "No specific technologies detected", which is how a 400-page wiki was greeted with
// a shrug. A project is now described by what it contains.
const MAKEUP: { section: string; key: string; singular: string; plural: string }[] = [
  { section: "documents", key: "pages", singular: "page", plural: "pages" },
  { section: "documents", key: "decisions", singular: "decision", plural: "decisions" },
  { section: "code", key: "modules", singular: "module", plural: "modules" },
  { section: "tests", key: "suites", singular: "test suite", plural: "test suites" },
  { section: "data", key: "tables", singular: "table", plural: "tables" },
  { section: "api", key: "endpoints", singular: "endpoint", plural: "endpoints" },
  { section: "infrastructure", key: "components", singular: "infra component", plural: "infra components" },
  { section: "deployment", key: "pipelines", singular: "pipeline", plural: "pipelines" },
  { section: "environments", key: "environments", singular: "environment", plural: "environments" },
];

function makeupOf(intel: ProjectIntelligenceResponse | null): string[] {
  if (!intel?.built || !intel.view) return [];
  const view = intel.view as unknown as Record<string, Record<string, unknown[]>>;
  const order = intel.view.section_order;
  const lines: string[] = [];

  const documents = intel.view.documents;
  const pages = documents ? documents.pages.length + documents.decisions.length : 0;
  // What the project mostly is goes first. A Terraform monorepo with a README in every
  // module led with "106 pages" and never mentioned its 938 .tf files — because pages
  // happened to be counted first. Documentation is the headline only when there is
  // nothing else here; inside a repository it is a part, called what it is: documents.
  const hasASystem = MAKEUP.some(
    (item) => item.section !== "documents" && (view[item.section]?.[item.key]?.length ?? 0) > 0,
  );
  const isDocumentationProject = pages > 0 && !hasASystem;

  if (isDocumentationProject && documents) {
    // A decision record is a page. Counting them apart made Home say "146 pages" while
    // the risk beside it said "169 pages nothing links to" — two true numbers that,
    // side by side, look like a bug in the app.
    const decisions = documents.decisions.length;
    lines.push(
      decisions > 0
        ? `${pages.toLocaleString()} pages, ${decisions} of them decision records`
        : `${pages.toLocaleString()} ${pages === 1 ? "page" : "pages"}`,
    );
    if (documents.topics.length > 0) {
      lines.push(`${documents.topics.length} ${documents.topics.length === 1 ? "area" : "areas"}`);
    }
  }

  for (const item of MAKEUP) {
    if (item.section === "documents" || !order.includes(item.section)) continue;
    const count = view[item.section]?.[item.key]?.length ?? 0;
    if (count === 0) continue;
    lines.push(`${count.toLocaleString()} ${count === 1 ? item.singular : item.plural}`);
  }

  if (!isDocumentationProject && pages > 0) {
    lines.push(`${pages.toLocaleString()} ${pages === 1 ? "document" : "documents"}`);
  }
  return lines;
}

type FileGroupKey = "code" | "infra" | "ci" | "tests" | "docs" | "config";

interface Lens {
  label: string;
  focus: string;
  groups: FileGroupKey[];
  risksLabel: string;
}

// Each assistant mode is a lens: same project, different emphasis. Unknown
// modes fall back to the developer lens (matches the backend default). The
// backend now also retrieves and prompts through the same role lens, so the
// summary and risks below are written from this role's point of view.
const LENSES: Record<string, Lens> = {
  developer: { label: "Developer", focus: "Code structure, where to start, and tests.", groups: ["code", "tests", "docs"], risksLabel: "Risks & gaps" },
  devops: { label: "DevOps", focus: "Deployment, infrastructure, and CI/CD.", groups: ["infra", "ci", "config"], risksLabel: "Operational risks" },
  tester: { label: "Tester / QA", focus: "Tests, what to verify, and how to run them.", groups: ["tests", "code", "ci"], risksLabel: "What to verify" },
  business_analyst: { label: "Business analyst", focus: "What the project does, in plain language.", groups: ["docs", "code"], risksLabel: "Gaps & limitations" },
  manager: { label: "Manager", focus: "Summary, key areas, and where the risk sits.", groups: ["docs", "infra"], risksLabel: "Key risks" },
  manager_summary: { label: "Manager", focus: "Summary, key areas, and where the risk sits.", groups: ["docs", "infra"], risksLabel: "Key risks" },
  documentation: { label: "Documentation", focus: "Docs, structure, and onboarding.", groups: ["docs", "code"], risksLabel: "Documentation gaps" },
  support_incident: { label: "Support", focus: "Runbooks, config, and troubleshooting.", groups: ["docs", "config", "infra"], risksLabel: "Failure modes" },
};

const GROUP_META: Record<FileGroupKey, { label: string; icon: ReactNode }> = {
  code: { label: "Key modules", icon: <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" /> },
  infra: { label: "Infrastructure & deploy", icon: <path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M3 12l9 4 9-4" /> },
  ci: { label: "CI / CD", icon: <><circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><path d="M6 9v6a3 3 0 0 0 3 3h6" /></> },
  tests: { label: "Tests", icon: <path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /> },
  docs: { label: "Docs", icon: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8" /> },
  config: { label: "Config", icon: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-2.82 1.17V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 8 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 14H4.5a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 6 8.6l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 11 5.6V4.5a2 2 0 1 1 4 0v.09A1.65 1.65 0 0 0 18.4 6l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 21.4 12H21" /></> },
};

// Real source-code extensions. Anything outside this set (requirements.txt,
// package.json, *.lock, LICENSE, …) is treated as config, so "Key modules"
// stays a list of actual code rather than metadata files.
const SOURCE_EXTENSIONS = new Set([
  "py", "ts", "tsx", "js", "jsx", "mjs", "cjs", "rs", "go", "java", "kt", "kts",
  "rb", "php", "c", "cc", "cpp", "h", "hpp", "cs", "swift", "scala", "m", "mm",
  "vue", "svelte", "sh", "bash", "sql", "lua", "r", "dart", "ex", "exs", "clj",
]);

// The scan already decided what each file is; trust it rather than re-deriving a
// second, subtly different answer here. The regexes below stay as a fallback for
// files the scanner leaves as "unknown".
const GROUP_BY_DETECTED_TYPE: Record<string, FileGroupKey> = {
  terraform: "infra",
  terragrunt: "infra",
  kubernetes: "infra",
  helm: "infra",
  docker: "infra",
  gitlab_ci: "ci",
  github_actions: "ci",
  python: "code",
  source_code: "code",
  shell: "code",
  makefile: "code",
  notebook: "code",
  markdown: "docs",
  plain_text: "docs",
  word_document: "docs",
  pdf_document: "docs",
  html: "docs",
  tabular_data: "docs",
  // Documents, whatever container they arrived in. Left out of this table, a
  // spreadsheet attached to a wiki page fell through to "Config", and a page called
  // "…_retry_test.html" was filed under Tests because its NAME contains "test".
  excel_workbook: "docs",
  presentation: "docs",
  diagram: "docs",
  image: "docs",
  yaml: "config",
  json: "config",
  config: "config",
  xml_config: "config",
};

// A file the scan already recognised as a document IS a document — no path rule may
// overrule that. "Payments_Webhook_-_retry_test.html" is a wiki page about a test, not
// a test; filing it under Tests is how a documentation folder ended up reporting one
// lonely, imaginary test suite.
const DOCUMENT_GROUPS = new Set<FileGroupKey>(["docs"]);

function categorize(file: ProjectFileResponse): FileGroupKey {
  const p = file.path.toLowerCase();
  const detected = GROUP_BY_DETECTED_TYPE[file.detected_type];
  if (detected && DOCUMENT_GROUPS.has(detected)) return detected;
  // Tests are about *where* a file lives, not what it is written in — a test .ts is a
  // test, not a module. But only code can be a test.
  if (/(^|\/)tests?\/|\.test\.|\.spec\.|__tests__|_test\.|\/spec\//.test(p)) return "tests";
  if (detected) return detected;

  if (/dockerfile|docker-compose|\.tf(\.|$)|\/terraform\/|\/k8s\/|kubernetes|\/helm\/|\/charts\/|ansible/.test(p)) return "infra";
  if (/\.github\/workflows|\.gitlab-ci|jenkinsfile|\.circleci|azure-pipelines|\.drone/.test(p)) return "ci";
  const ext = (file.extension ?? "").toLowerCase();
  if (ext === "md" || ext === "rst" || ext === "txt" || /(^|\/)docs?\//.test(p) || /readme|license|changelog|contributing/.test(p)) return "docs";
  if (SOURCE_EXTENSIONS.has(ext)) return "code";
  return "config";
}

// Turn a group of raw file paths into meaningful, human-readable items, so the
// Home columns answer "what is this" instead of listing `main.tf` six times.
type GroupItem = { primary: string; secondary?: string };

function prettyWorkflowName(path: string): string {
  const base = (path.split("/").pop() ?? path).replace(/\.(ya?ml)$/i, "");
  return base
    .split(/[-_]/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

const CONFIG_PURPOSE: Array<[RegExp, string]> = [
  [/(^|\/)\.pre-commit-config\.ya?ml$/, "Pre-commit hooks"],
  [/\.tflint\.hcl$/, "Terraform lint"],
  [/(^|\/)\.gitignore$/, "Git ignore rules"],
  [/(^|\/)\.gitmodules$/, "Git submodules"],
  [/(^|\/)\.editorconfig$/, "Editor config"],
  [/(^|\/)agents?\.md$/i, "Agent instructions"],
  [/(^|\/)\.env/, "Environment"],
  [/(^|\/)package\.json$/, "Node manifest"],
  [/pyproject\.toml$|requirements.*\.txt$|setup\.(py|cfg)$|pipfile/i, "Python deps"],
  [/dockerfile|docker-compose/i, "Container"],
  [/eslint\.config\.(c|m)?[jt]s$/, "ESLint config"],
  [/prettier|\.prettierrc/, "Prettier config"],
  [/\.config\.(c|m)?[jt]s$/, "Build config"],
  [/\.ya?ml$/, "YAML config"],
  [/\.json$/, "JSON config"],
  [/\.toml$/, "TOML config"],
  [/\.(c|m)?js$/, "JS module"],
  [/\.(c|m)?ts$/, "TS module"],
];

function configPurpose(path: string): string {
  const lower = path.toLowerCase();
  for (const [re, label] of CONFIG_PURPOSE) if (re.test(lower)) return label;
  return "Config";
}

function groupItems(
  groupKey: FileGroupKey,
  files: ProjectFileResponse[],
  titles?: Map<string, string>,
): GroupItem[] {
  if (groupKey === "infra") {
    // Distinct "modules" (the folder each file lives in) — `acm`, `cloudfront`…
    const byDir = new Map<string, number>();
    for (const f of files) {
      const parts = f.path.split("/");
      const dir = parts.length > 1 ? parts[parts.length - 2] : parts[0];
      byDir.set(dir, (byDir.get(dir) ?? 0) + 1);
    }
    return [...byDir.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([dir, n]) => ({ primary: dir, secondary: `${n} file${n === 1 ? "" : "s"}` }));
  }
  if (groupKey === "ci") {
    return [...files]
      .slice(0, 6)
      .map((f) => ({ primary: prettyWorkflowName(f.path), secondary: f.path.split("/").pop() }));
  }
  if (groupKey === "config") {
    return [...files]
      .sort(byImportance)
      .slice(0, 6)
      .map((f) => ({ primary: f.path.split("/").pop() ?? f.path, secondary: configPurpose(f.path) }));
  }
  // code / tests / docs: basename + faded parent folder, easier to scan than a path.
  // For a document the map has already read, its own title beats the underscored file
  // name the exporter produced — "[Capability] Ingestion layer", not
  // "[Capability]_Ingestion_layer.html".
  return [...files]
    .sort(byImportance)
    .slice(0, 6)
    .map((f) => {
      const title = titles?.get(f.path);
      const parts = f.path.split("/");
      const file = parts.pop() ?? f.path;
      if (title && title !== file) return { primary: title, secondary: file };
      return { primary: file, secondary: parts.length ? parts.join("/") : undefined };
    });
}

// Surface likely entry points first (main/index/app/cli/server…), then shallower
// paths, so the short preview list shows the files that matter most.
function keyFileRank(path: string): number {
  const name = path.toLowerCase().split("/").pop() ?? "";
  if (/^(main|index|app|server|cli|__main__|lib|mod)\.[a-z]+$/.test(name)) return 0;
  return 1;
}

function byImportance(a: ProjectFileResponse, b: ProjectFileResponse): number {
  const rank = keyFileRank(a.path) - keyFileRank(b.path);
  if (rank !== 0) return rank;
  const depth = a.path.split("/").length - b.path.split("/").length;
  if (depth !== 0) return depth;
  return a.path.localeCompare(b.path);
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes < 1024) return `${bytes || 0} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

function MetaIcon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

// A plain-language one-liner so the activity panel reads like a sentence, not a
// wall of numbers. Computed only from data we already have.
function gitLeadSentence(git: GitInsightsResponse): string {
  const last7 = git.commits_last_7_days ?? 0;
  const pace = last7 > 20 ? "very active" : last7 > 3 ? "active" : last7 > 0 ? "ticking along" : "quiet lately";
  const age = git.first_commit_at ? humanAge(git.first_commit_at) : null;
  const parts: string[] = [];
  parts.push(
    `A ${pace} project — ${git.total_commits.toLocaleString()} commits` +
      (age ? ` over ${age}` : "") +
      ` by ${git.contributors_count} ${git.contributors_count === 1 ? "person" : "people"}` +
      (last7 > 0 ? `, ${last7} this week.` : "."),
  );
  if (git.branch_strategy && git.branch_strategy.inferred_strategy !== "Unknown") {
    parts.push(`Ships via ${git.branch_strategy.inferred_strategy}.`);
  }
  const top = git.hotspots[0];
  if (top) {
    const name = top.path.split("/").pop() ?? top.path;
    parts.push(`Most-changed file lately: ${name}.`);
  }
  return parts.join(" ");
}

// Two-letter monogram for a contributor avatar.
function gaInitials(name: string): string {
  const parts = name.trim().split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// Stable hue per name so each avatar is its own colour but consistent across renders.
function gaHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

function GaSection({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="pu-ga-section">
      <div className="pu-ga-head">
        <span className="pu-eyebrow">{title}</span>
        {hint ? <span className="pu-ga-hint">{hint}</span> : null}
      </div>
      {children}
    </section>
  );
}

// 12-week commit volume with a plain-language trend caption instead of a bare chart.
function GitMomentum({ git }: { git: GitInsightsResponse }) {
  const weeks = git.activity_weeks;
  const maxWeek = weeks.reduce((m, w) => Math.max(m, w.commits), 0);
  if (maxWeek === 0) return null;
  const avg = (xs: typeof weeks) =>
    xs.length ? xs.reduce((s, w) => s + w.commits, 0) / xs.length : 0;
  // The last bucket is the current, still-incomplete week — it's always low
  // mid-week and would fake a "slowing down". Compare only completed weeks.
  const complete = weeks.slice(0, -1);
  const m = complete.length;
  let trend = "holding steady";
  if (m >= 4) {
    const recent = avg(complete.slice(Math.max(0, m - 3)));
    const prior = avg(complete.slice(Math.max(0, m - 6), Math.max(0, m - 3)));
    if (recent > prior * 1.25 || (prior === 0 && recent > 0)) trend = "picking up";
    else if (prior > 0 && recent < prior * 0.75) trend = "slowing down";
  }
  return (
    <GaSection title="Momentum" hint={`Commits per week · ${trend}`}>
      <div className="pu-git-bars pu-ga-bars">
        {weeks.map((w) => (
          <span
            key={w.period_start}
            className="pu-git-bar"
            title={`Week of ${w.period_start}: ${w.commits} commit(s)`}
          >
            <span style={{ height: `${Math.round((w.commits / maxWeek) * 100)}%` }} />
          </span>
        ))}
      </div>
      <p className="pu-ga-caption">
        Last 12 weeks · busiest week saw {maxWeek.toLocaleString()} commits.
      </p>
    </GaSection>
  );
}

function GitPeople({ git }: { git: GitInsightsResponse }) {
  const maxShare = git.top_contributors.reduce((m, c) => Math.max(m, c.share), 0) || 1;
  return (
    <GaSection title="Who knows this code" hint="Most commits — likely the right people to ask">
      <ul className="pu-people">
        {git.top_contributors.map((c) => {
          const active = c.commits_last_90_days > 0;
          const hue = gaHue(c.name);
          return (
            <li key={c.name} className="pu-person">
              <span
                className="pu-avatar"
                style={{ background: `hsl(${hue} 58% 92%)`, color: `hsl(${hue} 42% 32%)` }}
              >
                {gaInitials(c.name)}
              </span>
              <span className="pu-person-main">
                <span className="pu-person-top">
                  <span className="pu-person-name" title={c.name}>{c.name}</span>
                  <span className="pu-person-share">{Math.round(c.share * 100)}%</span>
                </span>
                <span className="pu-person-bar">
                  <span style={{ width: `${Math.round((c.share / maxShare) * 100)}%` }} />
                </span>
              </span>
              <span className={`pu-person-status${active ? " is-active" : ""}`}>
                <span className="pu-person-dot" />
                {active ? "active" : c.last_active ? `seen ${relativeTime(c.last_active)}` : "—"}
              </span>
            </li>
          );
        })}
      </ul>
    </GaSection>
  );
}

function GitShip({ git }: { git: GitInsightsResponse }) {
  const bs = git.branch_strategy;
  const ma = git.merge_activity;
  const hasStrategy = !!bs && bs.total_branches > 0 && bs.inferred_strategy !== "Unknown";
  const prs = ma ? ma.pull_requests_detected + ma.merge_requests_detected : 0;
  const mergeShare = Math.round(git.merge_commit_share * 100);
  if (!hasStrategy && prs === 0 && mergeShare === 0) return null;

  const facts: string[] = [];
  if (prs > 0) facts.push(`${prs.toLocaleString()} pull request${prs === 1 ? "" : "s"} merged`);
  if (mergeShare > 0) facts.push(`${mergeShare}% of commits arrived through merges`);
  if (bs && bs.total_branches > 0)
    facts.push(`${bs.total_branches} branch${bs.total_branches === 1 ? "" : "es"} seen`);

  // What kinds of branches actually get merged — a concrete picture of the flow.
  const mergedTypes = ma
    ? Object.entries(ma.source_branch_types)
        .filter(([key]) => key && key !== "other")
        .slice(0, 3)
    : [];
  const longLived = bs?.long_lived_branches ?? [];

  return (
    <GaSection title="How they ship" hint="Inferred from branch names and merge history">
      {hasStrategy ? <span className="pu-ship-name">{bs!.inferred_strategy}</span> : null}
      {bs && bs.rationale ? <p className="pu-ga-caption">{bs.rationale}</p> : null}
      {facts.length > 0 ? <p className="pu-ship-facts">{facts.join(" · ")}</p> : null}
      {longLived.length > 0 ? (
        <p className="pu-ga-caption">
          Long-lived: {longLived.map((b) => <code key={b} className="pu-ship-branch">{b}</code>).reduce((acc, el, i) => (i === 0 ? [el] : [...acc, <span key={`s${i}`}>, </span>, el]), [] as ReactNode[])}
        </p>
      ) : null}
      {mergedTypes.length > 0 ? (
        <p className="pu-ga-caption">
          Most merges come from {mergedTypes.map(([key]) => `${key}/`).join(", ")} branches.
        </p>
      ) : null}
      {bs && bs.prefixes.length > 0 ? (
        <div className="pu-chips">
          {bs.prefixes.map((p) => (
            <span key={p} className="pu-chip">{p}/</span>
          ))}
        </div>
      ) : null}
    </GaSection>
  );
}

function GitHotspots({ git, onInspectFile }: { git: GitInsightsResponse; onInspectFile?: (path: string) => void }) {
  const maxHotspot = git.hotspots.reduce((m, h) => Math.max(m, h.changes), 0) || 1;
  if (git.hotspots.length === 0) return null;
  return (
    <GaSection
      title="Where the work is going"
      hint="Files touched most in the last 90 days — click one to inspect it"
    >
      <ul className="pu-hotspots">
        {git.hotspots.map((h) => {
          const name = h.path.split("/").pop() ?? h.path;
          const dir = h.path.length > name.length ? h.path.slice(0, h.path.length - name.length) : "";
          return (
            <li key={h.path} className={`pu-hotspot${onInspectFile ? " is-clickable" : ""}`} title={onInspectFile ? `Inspect ${h.path}` : h.path}>
              <span
                className="pu-hotspot-label"
                role={onInspectFile ? "button" : undefined}
                tabIndex={onInspectFile ? 0 : undefined}
                onClick={onInspectFile ? () => onInspectFile(h.path) : undefined}
                onKeyDown={onInspectFile ? (e) => { if (e.key === "Enter") onInspectFile(h.path); } : undefined}
              >
                <span className="pu-hotspot-name">{name}</span>
                {dir ? <span className="pu-hotspot-dir">{dir}</span> : null}
              </span>
              <span className="pu-hotspot-bar">
                <span style={{ width: `${Math.round((h.changes / maxHotspot) * 100)}%` }} />
              </span>
              <span className="pu-hotspot-count">{h.changes}</span>
            </li>
          );
        })}
      </ul>
    </GaSection>
  );
}

// Temporal coupling: files that keep changing in the same commits. High pairs
// that live in different folders reveal hidden dependencies the import graph misses.
function GitCoupling({ git }: { git: GitInsightsResponse }) {
  const couples = git.file_couplings ?? [];
  if (couples.length === 0) return null;
  const base = (p: string) => p.split("/").pop() ?? p;
  const dir = (p: string) => {
    const parts = p.split("/");
    return parts.length > 1 ? parts.slice(0, -1).join("/") + "/" : "";
  };
  return (
    <GaSection
      title="Changes together"
      hint="Files that keep changing in the same commits — often a hidden dependency"
    >
      <ul className="pu-couples">
        {couples.map((c) => {
          const crossDir = dir(c.file_a) !== dir(c.file_b);
          return (
            <li key={`${c.file_a}|${c.file_b}`} className="pu-couple" title={`${c.file_a}  ↔  ${c.file_b}`}>
              <span className="pu-couple-pair">
                <span className="pu-couple-file">{base(c.file_a)}</span>
                <span className="pu-couple-link">↔</span>
                <span className="pu-couple-file">{base(c.file_b)}</span>
                {crossDir ? <span className="pu-couple-flag" title="The two files live in different folders">cross-module</span> : null}
              </span>
              <span className="pu-couple-share">{Math.round(c.share * 100)}%</span>
            </li>
          );
        })}
      </ul>
      <p className="pu-ga-caption">
        Share = how often the pair changes together when either one changes. Cross-module pairs are
        the ones worth a second look.
      </p>
    </GaSection>
  );
}

function RecentCommits({ git }: { git: GitInsightsResponse }) {
  if (git.recent_commits.length === 0) return null;
  return (
    <GaSection title="Latest commits">
      <ul className="pu-git-feed-list">
        {git.recent_commits.slice(0, 6).map((commit) => (
          <li key={commit.short_hash} title={commit.subject}>
            <span className="pu-git-feed-subject">{commit.subject}</span>
            <span className="pu-git-feed-meta">
              {commit.author}
              {commit.committed_at ? ` · ${relativeTime(commit.committed_at)}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </GaSection>
  );
}

// Same git facts, ordered and framed for the role chosen at project creation.
// DevOps cares how it ships and what's entangled; a developer wants where to work
// and who to ask; a tester wants the risk surface; an analyst/manager wants pace
// and team. Purely a presentation choice over the same deterministic data.
type GitSectionId = "momentum" | "people" | "ship" | "hotspots" | "coupling" | "recent";

const GIT_LAYOUT_BY_ROLE: Record<string, { order: GitSectionId[]; lens: string }> = {
  developer: { order: ["hotspots", "coupling", "people", "recent", "momentum"], lens: "where to work and who to ask" },
  devops: { order: ["ship", "coupling", "hotspots", "momentum", "people"], lens: "how it ships and what's entangled" },
  tester: { order: ["hotspots", "coupling", "recent", "momentum", "people"], lens: "where change concentrates — your risk map" },
  business_analyst: { order: ["momentum", "people", "ship", "recent"], lens: "delivery pace and the team behind it" },
  manager: { order: ["momentum", "people", "ship", "recent"], lens: "delivery pace and the team behind it" },
  manager_summary: { order: ["momentum", "people", "ship", "recent"], lens: "delivery pace and the team behind it" },
};

const DEFAULT_GIT_LAYOUT: { order: GitSectionId[]; lens: string } = {
  order: ["momentum", "people", "ship", "hotspots", "coupling", "recent"],
  lens: "",
};

function GitActivityCard({ git, role, onInspectFile }: { git: GitInsightsResponse; role: string; onInspectFile?: (path: string) => void }) {
  // Three "at a glance" metrics that answer: how alive is it, how big is the
  // team right now, and how does work land. Everything else has its own section.
  const heroes: Array<{ value: string; label: string; sub?: string }> = [
    {
      value: git.commits_last_7_days.toLocaleString(),
      label: "commits this week",
      sub: `${git.commits_last_30_days.toLocaleString()} in the last 30 days`,
    },
    {
      value: git.active_contributors_90d.toLocaleString(),
      label: git.active_contributors_90d === 1 ? "active contributor" : "active contributors",
      sub: `of ${git.contributors_count.toLocaleString()} all-time · last 90 days`,
    },
  ];
  if (git.merge_commit_share > 0) {
    heroes.push({
      value: `${Math.round(git.merge_commit_share * 100)}%`,
      label: "shipped via merges",
      sub:
        git.branch_strategy && git.branch_strategy.inferred_strategy !== "Unknown"
          ? git.branch_strategy.inferred_strategy
          : "of all commits",
    });
  } else if (git.first_commit_at) {
    heroes.push({
      value: humanAge(git.first_commit_at),
      label: "in development",
      sub: `${git.total_commits.toLocaleString()} commits total`,
    });
  }

  return (
    <details className="pu-card pu-git-activity pu-collapse">
      <summary className="pu-card-head pu-collapse-summary">
        <MetaIcon><><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="9" r="3" /><path d="M18 12a9 9 0 0 1-9 9M6 9v6" /></></MetaIcon>
        <span>Project activity</span>
        {(() => {
          // The project's main line, not whichever feature branch happens to be
          // checked out — that long ticket branch dominates and misleads.
          const branch = git.branch_strategy?.default_branch || git.branch;
          return branch ? (
            <small className="pu-git-branch" title={branch}>{branch}</small>
          ) : null;
        })()}
        <span className="pu-collapse-teaser">
          {git.total_commits.toLocaleString()} commits · {git.contributors_count} contributors
        </span>
      </summary>

      <p className="pu-git-lead">{gitLeadSentence(git)}</p>

      <div className="pu-ga-hero">
        {heroes.map((h) => (
          <div className="pu-ga-metric" key={h.label}>
            <strong>{h.value}</strong>
            <span className="pu-ga-metric-label">{h.label}</span>
            {h.sub ? <span className="pu-ga-metric-sub">{h.sub}</span> : null}
          </div>
        ))}
      </div>

      {(() => {
        const layout = GIT_LAYOUT_BY_ROLE[role] ?? DEFAULT_GIT_LAYOUT;
        const sections: Record<GitSectionId, ReactNode> = {
          momentum: <GitMomentum git={git} />,
          people: git.top_contributors.length > 0 ? <GitPeople git={git} /> : null,
          ship: <GitShip git={git} />,
          hotspots: <GitHotspots git={git} onInspectFile={onInspectFile} />,
          coupling: <GitCoupling git={git} />,
          recent: <RecentCommits git={git} />,
        };
        return (
          <>
            {layout.lens ? (
              <p className="pu-ga-lens">Arranged for your role — {layout.lens}.</p>
            ) : null}
            {layout.order.map((id) => (
              <Fragment key={id}>{sections[id]}</Fragment>
            ))}
          </>
        );
      })()}
    </details>
  );
}

/** What the map found worth a look — before any model is asked anything.
 *
 * Home already offers an LLM-written analysis, but that costs a minute and a model.
 * These are facts: a page a year old that six others still link to, a foreign key
 * with no index, a pipeline that deploys straight to prod. Deterministic, cited by
 * file, and — the part that matters — phrased as things to check, never as verdicts.
 * A wiki's risks are wiki risks; a repo's are repo risks. Same card, whatever the
 * project is made of.
 */
function MapRisksCard({
  findings,
  label,
  onInspectFile,
  onAskQuestion,
}: {
  findings: ProjectGraphFinding[];
  label: string;
  onInspectFile?: (path: string) => void;
  onAskQuestion?: (question: string) => void;
}) {
  if (findings.length === 0) return null;
  // The same finding, once per file, is one thing to look at — not three. Three cards
  // reading "Secrets referenced" (one per workflow) ate three of the five slots on
  // Home, so a project's five most important things were two things and an echo.
  const byTitle = new Map<string, { finding: ProjectGraphFinding; count: number }>();
  for (const finding of findings) {
    const seen = byTitle.get(finding.title);
    if (seen) seen.count += 1;
    else byTitle.set(finding.title, { finding, count: 1 });
  }
  const grouped = Array.from(byTitle.values());
  const shown = grouped.slice(0, 5);
  return (
    <div className="pu-card">
      <div className="pu-card-head">
        <MetaIcon>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
        </MetaIcon>
        <span>{label}</span>
        <small>{grouped.length}</small>
      </div>
      <div className="pu-analysis-risks">
        {shown.map(({ finding, count }) => {
          const file = finding.source_file ?? finding.evidence[0] ?? null;
          return (
            <div className="pu-risk" key={finding.id}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
              </svg>
              <div>
                <span className="pu-risk-text">
                  {finding.title}
                  {count > 1 ? <span className="pu-risk-count"> · in {count} places</span> : null}
                </span>
                {/* The title states the fact; this says why it may matter. The backend
                    already writes that line deterministically — use its words rather
                    than inventing a second voice for the same finding. */}
                <span className="pu-risk-why">
                  {finding.explained?.why_it_may_matter ?? finding.explanation}
                </span>
                {file ? (
                  <button
                    type="button"
                    className="pu-risk-file"
                    onClick={() => onInspectFile?.(file)}
                  >
                    {file}
                  </button>
                ) : null}
                {/* The fact already contains the question it raises. One click asks
                    it, instead of leaving the person to re-type it in their own
                    words and hope those words are the ones in the files. */}
                {finding.ask && onAskQuestion ? (
                  <button
                    type="button"
                    className="pu-risk-ask"
                    onClick={() => onAskQuestion(finding.ask as string)}
                  >
                    {finding.ask}
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      {grouped.length > shown.length ? (
        <p className="pu-guide-foot">
          Showing {shown.length} of {grouped.length} — the rest are in Intelligence › Risks.
        </p>
      ) : null}
    </div>
  );
}

export function ProjectUnderstanding({
  dashboard,
  projectPath,
  onOpenAsk,
  onOpenSettings,
  onStartScanJob,
  onStartIndexJob,
  onRefreshWorkspaceState,
  onInspectFile,
  onAskQuestion,
}: {
  dashboard: WorkspaceDashboard;
  projectPath: string;
  onOpenAsk: () => void;
  onOpenSettings: () => void;
  onStartScanJob: () => Promise<unknown> | void;
  onStartIndexJob: () => Promise<unknown> | void;
  onRefreshWorkspaceState: () => Promise<void> | void;
  onInspectFile?: (path: string) => void;
  // Each risk carries the question it is the beginning of; one click asks it.
  onAskQuestion?: (question: string) => void;
}) {
  const [scan, setScan] = useState<ProjectScanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [understanding, setUnderstanding] = useState<ProjectUnderstandingResponse | null>(null);
  const [understandingChecked, setUnderstandingChecked] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [changes, setChanges] = useState<ScanChanges | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [git, setGit] = useState<GitInsightsResponse | null>(null);
  const [todos, setTodos] = useState<ProjectTodosResponse | null>(null);
  // The project map, when it has been built. Home does not build it — it just tells
  // the truth about what it found, in the project's own terms.
  const [intel, setIntel] = useState<ProjectIntelligenceResponse | null>(null);
  const autoTriedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setUnderstanding(null);
    setUnderstandingChecked(false);
    setGenError(null);
    setChanges(null);
    setGit(null);
    setTodos(null);
    setIntel(null);
    autoTriedRef.current = false;
    getProjectIntelligence(dashboard.workspace_id)
      .then((result) => {
        if (!cancelled) setIntel(result);
      })
      .catch(() => {
        /* the map is optional here; Home still shows the scan */
      });
    // Have files on disk changed since the last scan? Only after a user gesture,
    // so this never triggers a macOS folder-access prompt on a cold launch.
    if (userHasInteracted) {
      getWorkspaceScanChanges(dashboard.workspace_id)
        .then((result) => {
          if (!cancelled && result.changed) setChanges(result);
        })
        .catch(() => {
          /* ignore — no banner if the check fails */
        });
      // Read-only git snapshot (also walks the folder, so it is gated too).
      getWorkspaceGitInsights(dashboard.workspace_id)
        .then((result) => {
          if (!cancelled && result.is_repo) setGit(result);
        })
        .catch(() => {
          /* ignore — the activity card simply does not render */
        });
      // Deterministic TODO/FIXME inventory (also walks the folder).
      getWorkspaceTodos(dashboard.workspace_id)
        .then((result) => {
          if (!cancelled && result.total > 0) setTodos(result);
        })
        .catch(() => {
          /* ignore — the TODO card simply does not render */
        });
    }
    getWorkspaceLatestScan(dashboard.workspace_id)
      .then((result) => {
        if (!cancelled) setScan(result);
      })
      .catch(() => {
        if (!cancelled) setScan(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    // Load any previously generated deep analysis (404 = none yet, treated as null).
    getProjectUnderstanding(dashboard.workspace_id)
      .then((result) => {
        if (!cancelled) setUnderstanding(result);
      })
      .catch(() => {
        if (!cancelled) setUnderstanding(null);
      })
      .finally(() => {
        if (!cancelled) setUnderstandingChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);

  const selectedModel = dashboard.models_summary?.selected_llm ?? null;

  // First time on a ready project with no cached analysis: run it automatically,
  // once, in the background. Failure (e.g. backend without the endpoint) falls
  // back to the manual button and is not retried in a loop.
  useEffect(() => {
    if (
      understandingChecked &&
      !understanding &&
      !generating &&
      !genError &&
      selectedModel &&
      !autoTriedRef.current
    ) {
      autoTriedRef.current = true;
      void handleAnalyze();
    }
    // handleAnalyze is intentionally omitted; it is stable in effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [understandingChecked, understanding, generating, genError, selectedModel]);

  async function handleAnalyze() {
    setGenerating(true);
    setGenError(null);
    try {
      const result = await generateProjectUnderstanding(dashboard.workspace_id);
      setUnderstanding(result);
    } catch (error) {
      setGenError(error instanceof Error ? error.message : "Could not analyze the project.");
    } finally {
      setGenerating(false);
    }
  }

  // Re-scan → rebuild context → re-analyze, in sequence — and say where it is. Each
  // stage reports the job's own progress, so a five-minute rebuild reads as work being
  // done rather than as an app that has stopped responding.
  async function handleUpdateProject() {
    const ws = dashboard.workspace_id;
    const show = (stage: string) => (job: WorkspaceJob) => {
      const line = jobProgressLine(job);
      setUpdating(line ? `${stage} · ${line}` : stage);
    };
    try {
      setUpdating("Re-scanning project…");
      const scanJob = (await onStartScanJob()) as WorkspaceJob | undefined;
      if (scanJob?.job_id) await pollJobDone(ws, scanJob.job_id, show("Re-scanning"));

      setUpdating("Rebuilding search context…");
      const indexJob = (await onStartIndexJob()) as WorkspaceJob | undefined;
      if (indexJob?.job_id) await pollJobDone(ws, indexJob.job_id, show("Rebuilding search context"));

      await onRefreshWorkspaceState();
      setChanges(null);

      setUpdating("Re-analyzing…");
      await handleAnalyze();
    } catch (error) {
      setGenError(error instanceof Error ? error.message : "Could not update the project.");
    } finally {
      setUpdating(null);
    }
  }

  const lens = LENSES[dashboard.assistant_mode] ?? LENSES.developer;
  const skills = scan ? scan.detected_skills : [];
  const files = scan ? scan.files : [];

  const grouped: Record<FileGroupKey, ProjectFileResponse[]> = {
    code: [], infra: [], ci: [], tests: [], docs: [], config: [],
  };
  for (const file of files) grouped[categorize(file)].push(file);

  const techNames = Array.from(new Set(skills.map((skill) => skill.name)));
  // What this project is made of — pages, modules, tables, pipelines — from the map's
  // own facts. It leads, because "Built with Python, Terraform" says nothing at all
  // about a folder of documentation, and "No specific technologies detected" is a
  // shrug at a project that is simply of a different kind.
  const makeup = makeupOf(intel);
  // path → the title the map read out of the document itself.
  const documentTitles = new Map<string, string>();
  for (const page of [
    ...(intel?.view?.documents?.pages ?? []),
    ...(intel?.view?.documents?.decisions ?? []),
  ]) {
    if (page.source_file) documentTitles.set(page.source_file, page.name);
  }
  const summaryLine =
    scan === null
      ? "Reading your project…"
      : makeup.length > 0
        ? `${makeup.slice(0, 4).join(" · ")}.`
        : techNames.length > 0
          ? `Built with ${techNames.slice(0, 5).join(", ")}${techNames.length > 5 ? ", and more" : ""}.`
          : intel?.built
            // The map exists but found nothing nameable. Say what we do know — the
            // file count — rather than telling the person to build what they built.
            ? `${scan.scanned_files.toLocaleString()} files, and nothing the map recognises yet.`
            : "Build the project map to see what this project is made of.";

  // A project with no code of its own cannot be "run". The commands the scan finds in
  // a wiki are commands the DOCUMENTS mention — `terraform apply` in a runbook, a
  // `drop table` in an ADR — and presenting them under "How to run" invites someone to
  // run, against their own machine, a line that was only ever being described.
  const hasOwnCode = files.some((file) => {
    const group = categorize(file);
    return group === "code" || group === "infra" || group === "ci";
  });

  const gitAvailable = files.some((file) => file.path.toLowerCase().includes(".git"));

  return (
    <section className="project-understanding">
      <header className="pu-header">
        <div className="pu-header-main">
          <h1>{dashboard.workspace_name}</h1>
          <p className="pu-path">{projectPath}</p>
          <button className="pu-lens-chip" type="button" onClick={onOpenSettings} data-tip="Change the project lens in Settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" /></svg>
            {lens.label} view
          </button>
        </div>
      </header>

      {changes ? (
        <div className="pu-changes-banner">
          <svg className="pu-changes-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 4v5h-5" /></svg>
          <div className="pu-changes-text">
            <strong>
              {updating === null
                ? "Project files changed since the last scan."
                : "Updating this project…"}
            </strong>
            {/* While it works, the line says what it is doing and how far it has got —
                the job knows both. A five-minute rebuild that says nothing is
                indistinguishable from one that has hung. */}
            <span>
              {updating ??
                [
                  changes.added_count ? `${changes.added_count} added` : null,
                  changes.modified_count ? `${changes.modified_count} changed` : null,
                  changes.removed_count ? `${changes.removed_count} removed` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
            </span>
          </div>
          <button
            className="pu-changes-update"
            type="button"
            disabled={updating !== null}
            onClick={() => void handleUpdateProject()}
          >
            {updating === null ? "Re-scan & rebuild" : "Working…"}
          </button>
          {updating === null ? (
            <button
              className="pu-changes-dismiss"
              type="button"
              aria-label="Dismiss"
              onClick={() => setChanges(null)}
            >
              ✕
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="pu-summary-card">
        <span className="pu-eyebrow">What this project is</span>
        <p className="pu-lead-line">
          {summaryLine}
          {git
            ? ` ${git.total_commits.toLocaleString()} ${
                git.total_commits === 1 ? "commit" : "commits"
              } by ${git.contributors_count} ${
                git.contributors_count === 1 ? "person" : "people"
              }${git.commits_last_7_days > 0 ? `, ${git.commits_last_7_days} this week` : ""}.`
            : ""}
        </p>
        <div className="pu-lead-foot">
          <span className="pu-summary-foot">{lens.focus} · from your local scan</span>
          <button type="button" className="pu-lead-ask" onClick={onOpenAsk}>
            Ask anything about it →
          </button>
        </div>
      </div>

      <details className="pu-card pu-analysis pu-collapse">
        <summary className="pu-card-head pu-collapse-summary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l1.9 4.9L19 9l-4.1 1.1L12 15l-1.9-4.9L6 9l4.1-1.1zM5 16l.9 2.1L8 19l-2.1.9L5 22l-.9-2.1L2 19l2.1-.9zM19 14l.7 1.8L21 16.5l-1.3.7L19 19l-.7-1.8L17 16.5l1.3-.7z" /></svg>
          <span>AI deep analysis</span>
          <span className="pu-collapse-teaser">optional · the Intelligence tab covers most of this</span>
        </summary>
        {understanding && !generating ? (
          <button
            className={`pu-analysis-reanalyze${understanding.is_stale ? " is-prominent" : ""}`}
            type="button"
            disabled={generating || !selectedModel}
            onClick={() => void handleAnalyze()}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 4v5h-5" /></svg>
            {understanding.is_stale ? "Re-analyze with new model" : "Re-analyze"}
          </button>
        ) : null}

        {generating ? (
          <p className="pu-analysis-loading">Analyzing your project with {humanizeSelectedModel(selectedModel) ?? "your local model"}… this runs locally and can take up to a minute.</p>
        ) : understanding ? (
          <>
            <p className="pu-analysis-summary">{cleanAnalysisSummary(understanding.summary)}</p>
            {understanding.risks.length > 0 ? (
              <>
                <div className="pu-eyebrow pu-analysis-risks-label">{lens.risksLabel}</div>
                <div className="pu-analysis-risks">
                  {understanding.risks.map((risk, index) => (
                    <div className="pu-risk" key={`${risk.text}-${index}`}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" /></svg>
                      <div>
                        <span className="pu-risk-text">{risk.text}</span>
                        {risk.file ? <span className="pu-risk-file">{risk.file}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
            <div className="pu-analysis-foot">
              <span className="pu-analysis-model">Analyzed with <strong>{understanding.model}</strong> · {relativeTime(understanding.generated_at)}</span>
              {understanding.is_stale ? (
                <span className="pu-analysis-nudge">
                  Now using {selectedModel ?? "a different model"} — re-analyze for an updated view.
                </span>
              ) : (
                <span className="pu-analysis-hint">Want sharper insight? Use a bigger model, then re-analyze.</span>
              )}
            </div>
          </>
        ) : (
          <>
            <p className="pu-analysis-pitch">Your local AI reads the project through your <strong>{lens.label}</strong> lens and writes a grounded summary and risks — each pointing to the file it came from. Bigger models give sharper results. Runs locally.</p>
            <button className="pu-analysis-cta" type="button" disabled={!selectedModel} onClick={() => void handleAnalyze()}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l1.9 4.9L19 9l-4.1 1.1L12 15l-1.9-4.9L6 9l4.1-1.1z" /></svg>
              {selectedModel ? `Analyze with ${selectedModel}` : "Set up a model to analyze"}
            </button>
          </>
        )}
        {genError ? <p className="pu-analysis-error">{genError}</p> : null}
      </details>

      {understanding && understanding.architecture ? (
        <div className="pu-card">
          <div className="pu-card-head">
            <MetaIcon><><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></></MetaIcon>
            <span>Architecture at a glance</span>
            {/* Prose a model wrote, standing among deterministic facts, unlabelled —
                the one thing this app promises never to do. Whose words these are is
                part of what they mean. */}
            <small>written by {understanding.model} from your files</small>
          </div>
          <p className="pu-guide-text">{understanding.architecture}</p>
        </div>
      ) : null}

      {understanding && understanding.start_here.length > 0 ? (
        <div className="pu-card">
          <div className="pu-card-head">
            <MetaIcon><><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M9 13l2 2 4-4" /></></MetaIcon>
            <span>Where to start</span>
          </div>
          <ol className="pu-start-list">
            {understanding.start_here.map((point) => (
              <li key={point.file}>
                {onInspectFile ? (
                  <button type="button" className="pu-file-link" title={`Inspect ${point.file}`} onClick={() => onInspectFile(point.file)}>
                    {point.file}
                  </button>
                ) : (
                  <code title={point.file}>{point.file}</code>
                )}
                {point.reason ? <span>{point.reason}</span> : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {understanding && understanding.run_commands.length > 0 ? (
        <details className="pu-card pu-collapse">
          <summary className="pu-card-head pu-collapse-summary">
            <MetaIcon><><path d="M4 17l6-6-6-6M12 19h8" /></></MetaIcon>
            <span>{hasOwnCode ? "How to run" : "Commands mentioned in the documents"}</span>
            <span className="pu-collapse-teaser">{understanding.run_commands.length} command(s) found</span>
          </summary>
          <div className="pu-run-list">
            {understanding.run_commands.map((command, index) => (
              <div className="pu-run-row" key={`${command.command}-${index}`}>
                <code>{command.command}</code>
                {command.note ? <span>{command.note}</span> : null}
              </div>
            ))}
          </div>
          <p className="pu-guide-foot">
            {hasOwnCode
              ? "Commands found in your project files — review before running."
              : "Quoted from your documents — they describe another system, so they are not commands to run here."}
          </p>
        </details>
      ) : null}

      {todos ? (
        <details className="pu-card pu-collapse">
          <summary className="pu-card-head pu-collapse-summary">
            <MetaIcon><><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></></MetaIcon>
            <span>TODOs &amp; loose ends</span>
            <span className="pu-collapse-teaser">{todos.total} found</span>
          </summary>
          <ul className="pu-todo-list">
            {todos.items.slice(0, 8).map((item, index) => (
              <li key={`${item.file}-${item.line}-${index}`}>
                <span className={`pu-todo-marker pu-todo-${item.marker.toLowerCase()}`}>{item.marker}</span>
                <span className="pu-todo-text">{item.text}</span>
                <code className="pu-todo-loc" title={`${item.file}:${item.line}`}>{item.file.split("/").pop()}:{item.line}</code>
              </li>
            ))}
          </ul>
          {todos.truncated || todos.total > Math.min(8, todos.items.length) ? (
            <p className="pu-guide-foot">Showing {Math.min(8, todos.items.length)} of {todos.total} found in your files.</p>
          ) : null}
        </details>
      ) : null}

      {loading ? (
        <p className="pu-loading">Reading your project…</p>
      ) : (
        <details className="pu-card pu-collapse">
          <summary className="pu-card-head pu-collapse-summary">
            <MetaIcon>{GROUP_META.code.icon}</MetaIcon>
            <span>Files by area</span>
            <span className="pu-collapse-teaser">
              {techNames.length > 0 ? `${techNames.length} technolog${techNames.length === 1 ? "y" : "ies"} · ` : ""}
              {files.length.toLocaleString()} files
            </span>
          </summary>
          {techNames.length > 0 ? (
            <div className="pu-chips pu-stack-chips">
              {techNames.map((name) => (
                <span className="pu-chip" key={name}>{name}</span>
              ))}
            </div>
          ) : null}

          <div className="pu-grid">
            {/* The role's own areas first, then everything else the project actually
                has. A wiki opened as a developer used to show one lonely "Docs" card,
                because the other two the lens asked for did not exist here. */}
            {([
              ...lens.groups,
              ...(Object.keys(grouped) as FileGroupKey[]).filter((k) => !lens.groups.includes(k)),
            ] as FileGroupKey[]).map((groupKey) => {
              const groupFiles = grouped[groupKey];
              if (groupFiles.length === 0) return null;
              return (
                <div className="pu-card" key={groupKey}>
                  <div className="pu-card-head">
                    <MetaIcon>{GROUP_META[groupKey].icon}</MetaIcon>
                    <span>{GROUP_META[groupKey].label}</span>
                    <small>{groupFiles.length}</small>
                  </div>
                  <ul className="pu-file-list pu-file-list-rich">
                    {groupItems(groupKey, groupFiles, documentTitles).map((item, i) => (
                      <li key={`${item.primary}-${i}`} title={item.secondary}>
                        <span className="pu-file-primary">{item.primary}</span>
                        {item.secondary ? (
                          <span className="pu-file-secondary">{item.secondary}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </details>
      )}

      {intel?.built && intel.view ? (
        <MapRisksCard
          findings={intel.view.risks.findings}
          label={lens.risksLabel}
          onInspectFile={onInspectFile}
          onAskQuestion={onAskQuestion}
        />
      ) : null}

      {git ? <GitActivityCard git={git} role={dashboard.assistant_mode} onInspectFile={onInspectFile} /> : null}

      <details className="pu-card pu-sources pu-collapse">
        <summary className="pu-sources-head pu-collapse-summary">
          <span className="pu-eyebrow">Sources</span>
          <span className="pu-sources-note">Local-first · connect more when you have them</span>
        </summary>
        <div className="pu-sources-grid">
          <div className="pu-source is-active">
            <MetaIcon>{GROUP_META.docs.icon}</MetaIcon>
            <div>
              <strong>Local files</strong>
              <small>
                {scan
                  ? `${scan.scanned_files.toLocaleString()} scanned${
                      scan.skipped_files ? ` · ${scan.skipped_files.toLocaleString()} skipped` : ""
                    }${scan.total_size_bytes ? ` · ${formatBytes(scan.total_size_bytes)}` : ""}`
                  : "Active"}
              </small>
              <small className="pu-source-note">Searchable · respects .gitignore</small>
            </div>
          </div>
          {git || gitAvailable ? (
            <div className={`pu-source${git ? " is-active" : ""}`}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="9" r="3" /><path d="M18 12a9 9 0 0 1-9 9M6 9v6" /></svg>
              <div>
                <strong>Git history</strong>
                {git ? (
                  <small>
                    {git.total_commits.toLocaleString()} commits · {git.contributors_count} contributors
                    {git.branch_strategy?.default_branch || git.branch
                      ? ` · ${git.branch_strategy?.default_branch || git.branch}`
                      : ""}
                  </small>
                ) : (
                  <small>Available</small>
                )}
                {git?.last_commit?.committed_at ? (
                  <small className="pu-source-note">Last commit {relativeTime(git.last_commit.committed_at)}</small>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
        <p className="pu-sources-trust">Everything stays on your computer — nothing is uploaded.</p>
      </details>
    </section>
  );
}
