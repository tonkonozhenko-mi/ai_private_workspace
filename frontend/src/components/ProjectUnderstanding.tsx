import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { getWorkspaceLatestScan } from "../api/client";
import type {
  ProjectFileResponse,
  ProjectScanResponse,
  WorkspaceDashboard,
} from "../api/types";

type FileGroupKey = "code" | "infra" | "ci" | "tests" | "docs" | "config";

interface Lens {
  label: string;
  focus: string;
  groups: FileGroupKey[];
}

// Each assistant mode is a lens: same project, different emphasis. Unknown
// modes fall back to the developer lens (matches the backend default).
const LENSES: Record<string, Lens> = {
  developer: { label: "Developer", focus: "Code structure, where to start, and tests.", groups: ["code", "tests", "docs"] },
  devops: { label: "DevOps", focus: "Deployment, infrastructure, and CI/CD.", groups: ["infra", "ci", "config"] },
  tester: { label: "Tester / QA", focus: "Tests, what to verify, and how to run them.", groups: ["tests", "code", "ci"] },
  business_analyst: { label: "Business analyst", focus: "What the project does, in plain language.", groups: ["docs", "code"] },
  manager_summary: { label: "Manager", focus: "Summary, key areas, and where the risk sits.", groups: ["docs", "infra"] },
  documentation: { label: "Documentation", focus: "Docs, structure, and onboarding.", groups: ["docs", "code"] },
  support_incident: { label: "Support", focus: "Runbooks, config, and troubleshooting.", groups: ["docs", "config", "infra"] },
};

const GROUP_META: Record<FileGroupKey, { label: string; icon: ReactNode }> = {
  code: { label: "Key modules", icon: <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" /> },
  infra: { label: "Infrastructure & deploy", icon: <path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M3 12l9 4 9-4" /> },
  ci: { label: "CI / CD", icon: <><circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><path d="M6 9v6a3 3 0 0 0 3 3h6" /></> },
  tests: { label: "Tests", icon: <path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /> },
  docs: { label: "Docs", icon: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8" /> },
  config: { label: "Config", icon: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-2.82 1.17V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 8 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 14H4.5a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 6 8.6l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 11 5.6V4.5a2 2 0 1 1 4 0v.09A1.65 1.65 0 0 0 18.4 6l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 21.4 12H21" /></> },
};

function categorize(file: ProjectFileResponse): FileGroupKey {
  const p = file.path.toLowerCase();
  if (/dockerfile|docker-compose|\.tf(\.|$)|\/terraform\/|\/k8s\/|kubernetes|\/helm\/|\/charts\/|ansible/.test(p)) return "infra";
  if (/\.github\/workflows|\.gitlab-ci|jenkinsfile|\.circleci|azure-pipelines|\.drone/.test(p)) return "ci";
  if (/(^|\/)tests?\/|\.test\.|\.spec\.|__tests__|_test\.|\/spec\//.test(p)) return "tests";
  const ext = (file.extension ?? "").toLowerCase();
  if (ext === "md" || /(^|\/)docs?\//.test(p) || /readme/.test(p)) return "docs";
  if (/\.(ya?ml|toml|ini|cfg|conf)$/.test(p) || /\.env/.test(p) || /(^|\/)config/.test(p)) return "config";
  return "code";
}

function MetaIcon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

export function ProjectUnderstanding({
  dashboard,
  onOpenAsk,
  onOpenSettings,
}: {
  dashboard: WorkspaceDashboard;
  onOpenAsk: () => void;
  onOpenSettings: () => void;
}) {
  const [scan, setScan] = useState<ProjectScanResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
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
    return () => {
      cancelled = true;
    };
  }, [dashboard.workspace_id]);

  const lens = LENSES[dashboard.assistant_mode] ?? LENSES.developer;
  const skills = scan ? scan.detected_skills : [];
  const files = scan ? scan.files : [];

  const grouped: Record<FileGroupKey, ProjectFileResponse[]> = {
    code: [], infra: [], ci: [], tests: [], docs: [], config: [],
  };
  for (const file of files) grouped[categorize(file)].push(file);

  const techNames = Array.from(new Set(skills.map((skill) => skill.name)));
  const summaryLine =
    techNames.length > 0
      ? `Built with ${techNames.slice(0, 5).join(", ")}${techNames.length > 5 ? ", and more" : ""}.`
      : "No specific technologies detected — answers come from your project files.";

  const gitAvailable = files.some((file) => file.path.toLowerCase().includes(".git"));

  return (
    <section className="project-understanding">
      <header className="pu-header">
        <div>
          <span className="pu-eyebrow">Project</span>
          <h1>{dashboard.workspace_name}</h1>
          <button className="pu-lens-chip" type="button" onClick={onOpenSettings} title="Change the project lens in Settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" /></svg>
            Tuned for {lens.label} · change in Settings
          </button>
        </div>
        <button className="pu-ask-button" type="button" onClick={onOpenAsk}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
          Ask about this
        </button>
      </header>

      <div className="pu-summary-card">
        <span className="pu-eyebrow">What this project is</span>
        <p>{summaryLine}</p>
        <span className="pu-summary-foot">{lens.focus} · From your local scan.</span>
      </div>

      {loading ? (
        <p className="pu-loading">Reading your project…</p>
      ) : (
        <>
          {techNames.length > 0 ? (
            <div className="pu-card">
              <div className="pu-card-head"><MetaIcon>{GROUP_META.code.icon}</MetaIcon><span>Stack</span></div>
              <div className="pu-chips">
                {techNames.map((name) => (
                  <span className="pu-chip" key={name}>{name}</span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="pu-grid">
            {lens.groups.map((groupKey) => {
              const groupFiles = grouped[groupKey];
              if (groupFiles.length === 0) return null;
              return (
                <div className="pu-card" key={groupKey}>
                  <div className="pu-card-head">
                    <MetaIcon>{GROUP_META[groupKey].icon}</MetaIcon>
                    <span>{GROUP_META[groupKey].label}</span>
                    <small>{groupFiles.length}</small>
                  </div>
                  <ul className="pu-file-list">
                    {groupFiles.slice(0, 6).map((file) => (
                      <li key={file.path} title={file.path}>{file.path}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </>
      )}

      <div className="pu-card pu-sources">
        <div className="pu-sources-head">
          <span className="pu-eyebrow">Sources</span>
          <span className="pu-sources-note">Local-first · connect more when you have them</span>
        </div>
        <div className="pu-sources-grid">
          <div className="pu-source is-active">
            <MetaIcon>{GROUP_META.docs.icon}</MetaIcon>
            <div><strong>Local files</strong><small>{scan ? `Active · ${scan.scanned_files.toLocaleString()} files` : "Active"}</small></div>
          </div>
          <div className="pu-source" title="Integration coming soon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>
            <div><strong>Confluence</strong><small>Coming soon</small></div>
          </div>
          <div className="pu-source" title="Integration coming soon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 10-12h-9z" /></svg>
            <div><strong>Jira</strong><small>Coming soon</small></div>
          </div>
          {gitAvailable ? (
            <div className="pu-source">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="9" r="3" /><path d="M18 12a9 9 0 0 1-9 9M6 9v6" /></svg>
              <div><strong>Git history</strong><small>Available</small></div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
