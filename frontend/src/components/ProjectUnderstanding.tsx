import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
  generateProjectUnderstanding,
  getProjectUnderstanding,
  getWorkspaceJob,
  getWorkspaceLatestScan,
  getWorkspaceScanChanges,
} from "../api/client";
import type {
  ProjectFileResponse,
  ProjectScanResponse,
  ProjectUnderstandingResponse,
  ScanChanges,
  WorkspaceDashboard,
  WorkspaceJob,
} from "../api/types";

async function pollJobDone(workspaceId: string, jobId: string): Promise<void> {
  for (let attempt = 0; attempt < 900; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    try {
      const job: WorkspaceJob = await getWorkspaceJob(workspaceId, jobId);
      if (["completed", "failed", "cancelled"].includes(job.status)) return;
    } catch {
      // keep polling through transient errors
    }
  }
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
  return new Date(iso).toLocaleDateString();
}

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
  projectPath,
  onOpenAsk,
  onOpenSettings,
  onStartScanJob,
  onStartIndexJob,
  onRefreshWorkspaceState,
}: {
  dashboard: WorkspaceDashboard;
  projectPath: string;
  onOpenAsk: () => void;
  onOpenSettings: () => void;
  onStartScanJob: () => Promise<unknown> | void;
  onStartIndexJob: () => Promise<unknown> | void;
  onRefreshWorkspaceState: () => Promise<void> | void;
}) {
  const [scan, setScan] = useState<ProjectScanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [understanding, setUnderstanding] = useState<ProjectUnderstandingResponse | null>(null);
  const [understandingChecked, setUnderstandingChecked] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [changes, setChanges] = useState<ScanChanges | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const autoTriedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setUnderstanding(null);
    setUnderstandingChecked(false);
    setGenError(null);
    setChanges(null);
    autoTriedRef.current = false;
    // Have files on disk changed since the last scan?
    getWorkspaceScanChanges(dashboard.workspace_id)
      .then((result) => {
        if (!cancelled && result.changed) setChanges(result);
      })
      .catch(() => {
        /* ignore — no banner if the check fails */
      });
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

  // Re-scan → rebuild context → re-analyze, in sequence, with status text.
  async function handleUpdateProject() {
    const ws = dashboard.workspace_id;
    try {
      setUpdating("Re-scanning project…");
      const scanJob = (await onStartScanJob()) as WorkspaceJob | undefined;
      if (scanJob?.job_id) await pollJobDone(ws, scanJob.job_id);

      setUpdating("Rebuilding search context…");
      const indexJob = (await onStartIndexJob()) as WorkspaceJob | undefined;
      if (indexJob?.job_id) await pollJobDone(ws, indexJob.job_id);

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
  const summaryLine =
    techNames.length > 0
      ? `Built with ${techNames.slice(0, 5).join(", ")}${techNames.length > 5 ? ", and more" : ""}.`
      : "No specific technologies detected — answers come from your project files.";

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
        <button className="pu-ask-button" type="button" onClick={onOpenAsk}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
          Ask about this
        </button>
      </header>

      {changes ? (
        <div className="pu-changes-banner">
          <svg className="pu-changes-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 4v5h-5" /></svg>
          <div className="pu-changes-text">
            <strong>Project files changed since the last scan.</strong>
            <span>
              {[
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
            {updating ?? "Re-scan & rebuild"}
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
        <p>{summaryLine}</p>
        <span className="pu-summary-foot">{lens.focus} · From your local scan.</span>
      </div>

      <div className="pu-card pu-analysis">
        <div className="pu-analysis-head">
          <div className="pu-card-head">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l1.9 4.9L19 9l-4.1 1.1L12 15l-1.9-4.9L6 9l4.1-1.1zM5 16l.9 2.1L8 19l-2.1.9L5 22l-.9-2.1L2 19l2.1-.9zM19 14l.7 1.8L21 16.5l-1.3.7L19 19l-.7-1.8L17 16.5l1.3-.7z" /></svg>
            <span>Deep project analysis</span>
          </div>
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
        </div>

        {generating ? (
          <p className="pu-analysis-loading">Analyzing your project with {selectedModel ?? "your local model"}… this runs locally and can take up to a minute.</p>
        ) : understanding ? (
          <>
            <p className="pu-analysis-summary">{understanding.summary}</p>
            {understanding.risks.length > 0 ? (
              <>
                <div className="pu-eyebrow pu-analysis-risks-label">Detected risks</div>
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
            <p className="pu-analysis-pitch">Your local AI reads the project and writes a grounded summary and risks — each pointing to the file it came from. Bigger models give sharper results. Runs locally.</p>
            <button className="pu-analysis-cta" type="button" disabled={!selectedModel} onClick={() => void handleAnalyze()}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l1.9 4.9L19 9l-4.1 1.1L12 15l-1.9-4.9L6 9l4.1-1.1z" /></svg>
              {selectedModel ? `Analyze with ${selectedModel}` : "Set up a model to analyze"}
            </button>
          </>
        )}
        {genError ? <p className="pu-analysis-error">{genError}</p> : null}
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
