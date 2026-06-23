import { useEffect, useMemo, useState } from "react";

import { getProjectIntelligence, getWorkspaceFileActivity, getWorkspaceGitInsights } from "../api/client";
import type {
  GitFileActivityResponse,
  GitInsightsResponse,
  ProjectIntelligenceResponse,
} from "../api/types";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const days = Math.round((Date.now() - then) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} d ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months} mo ago`;
  return `${Math.round(months / 12)} y ago`;
}

const TYPE_LABEL: Record<string, string> = {
  environment: "Environment",
  infra_component: "Infrastructure",
  pipeline: "Pipeline",
  pipeline_job: "Pipeline job",
  application: "Application",
  module: "Module",
  service: "Service",
  container_image: "Container image",
  cloud_service: "Cloud service",
  dependency: "Dependency",
  config_file: "Config file",
};

// A read-only lens on a single file: who owns it, what it changes together with,
// what it connects to in the project graph (its blast radius), and which risks
// touch it. Everything is derived from data the app already computed.
export function FileInspector({
  workspaceId,
  path,
  role,
  onClose,
}: {
  workspaceId: string;
  path: string;
  role?: string;
  onClose: () => void;
}) {
  const [activity, setActivity] = useState<GitFileActivityResponse | null>(null);
  const [git, setGit] = useState<GitInsightsResponse | null>(null);
  const [intel, setIntel] = useState<ProjectIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setActivity(null);
    Promise.allSettled([
      getWorkspaceFileActivity(workspaceId, path, { signal: controller.signal }),
      getWorkspaceGitInsights(workspaceId, { signal: controller.signal }),
      getProjectIntelligence(workspaceId, role, { signal: controller.signal }),
    ]).then((results) => {
      if (controller.signal.aborted) return;
      if (results[0].status === "fulfilled") setActivity(results[0].value);
      if (results[1].status === "fulfilled") setGit(results[1].value);
      if (results[2].status === "fulfilled") setIntel(results[2].value);
      setLoading(false);
    });
    return () => controller.abort();
  }, [workspaceId, path, role]);

  const name = path.split("/").pop() ?? path;
  const dir = path.slice(0, path.length - name.length);

  // Couplings involving this file.
  const couplings = useMemo(() => {
    const list = git?.file_couplings ?? [];
    return list
      .filter((c) => c.file_a === path || c.file_b === path)
      .map((c) => ({ other: c.file_a === path ? c.file_b : c.file_a, share: c.share, together: c.together }))
      .sort((a, b) => b.share - a.share);
  }, [git, path]);

  // Graph node for this file + its blast radius (direct neighbours).
  const impact = useMemo(() => {
    const graph = intel?.graph;
    if (!graph) return null;
    const node = graph.nodes.find((n) => n.source_file === path);
    if (!node) return null;
    const nameOf = (id: string) => graph.nodes.find((n) => n.id === id)?.name ?? id;
    const downstream = graph.edges.filter((e) => e.source === node.id).map((e) => nameOf(e.target));
    const upstream = graph.edges.filter((e) => e.target === node.id).map((e) => nameOf(e.source));
    return { node, upstream: [...new Set(upstream)], downstream: [...new Set(downstream)] };
  }, [intel, path]);

  // Findings whose evidence references this file.
  const risks = useMemo(() => {
    const findings = intel?.view?.risks?.findings ?? [];
    return findings.filter((f) => (f.evidence ?? []).some((e) => e.includes(path)));
  }, [intel, path]);

  const owner = activity?.top_authors?.[0];

  return (
    <div className="fi-overlay" onMouseDown={onClose} role="presentation">
      <aside className="fi" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-label={`File: ${name}`}>
        <header className="fi-head">
          <div>
            <p className="fi-eyebrow">File inspector</p>
            <h2 className="fi-name">{name}</h2>
            {dir ? <p className="fi-dir">{dir}</p> : null}
            {impact?.node ? (
              <span className="fi-type">{TYPE_LABEL[impact.node.type] ?? impact.node.type}</span>
            ) : null}
          </div>
          <button type="button" className="fi-close" onClick={onClose} aria-label="Close">✕</button>
        </header>

        {loading ? <p className="fi-muted">Reading…</p> : null}

        {!loading ? (
          <div className="fi-body">
            <section className="fi-section">
              <p className="fi-shead">Ownership</p>
              {owner ? (
                <p className="fi-line">
                  Most changes by <strong>{owner.name}</strong> — likely the person to ask.
                  {activity && activity.total_commits > 0 ? ` ${activity.total_commits} commit(s) total.` : ""}
                </p>
              ) : (
                <p className="fi-muted">No git history for this file.</p>
              )}
              {activity && activity.top_authors.length > 1 ? (
                <div className="fi-chips">
                  {activity.top_authors.slice(0, 5).map((a) => (
                    <span key={a.name} className="fi-chip">{a.name}<span className="fi-chip-n">{a.commits}</span></span>
                  ))}
                </div>
              ) : null}
            </section>

            {couplings.length > 0 ? (
              <section className="fi-section">
                <p className="fi-shead">Changes together with</p>
                <p className="fi-hint">If you touch this file, these tend to change too.</p>
                <ul className="fi-list">
                  {couplings.slice(0, 8).map((c) => (
                    <li key={c.other} title={c.other}>
                      <code>{c.other.split("/").pop()}</code>
                      <span className="fi-share">{Math.round(c.share * 100)}%</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {impact && (impact.upstream.length > 0 || impact.downstream.length > 0) ? (
              <section className="fi-section">
                <p className="fi-shead">Connected in the project map</p>
                {impact.upstream.length > 0 ? (
                  <p className="fi-line"><span className="fi-tag">depends on</span> {impact.upstream.join(", ")}</p>
                ) : null}
                {impact.downstream.length > 0 ? (
                  <p className="fi-line"><span className="fi-tag">affects</span> {impact.downstream.join(", ")}</p>
                ) : null}
              </section>
            ) : null}

            {risks.length > 0 ? (
              <section className="fi-section">
                <p className="fi-shead">Risks touching this file</p>
                <ul className="fi-risks">
                  {risks.map((f) => (
                    <li key={f.id}>
                      <span className={`fi-sev fi-sev-${f.severity}`}>{f.severity}</span>
                      {f.title}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {activity && activity.recent_commits.length > 0 ? (
              <section className="fi-section">
                <p className="fi-shead">Recent changes</p>
                <ul className="fi-commits">
                  {activity.recent_commits.slice(0, 6).map((c) => (
                    <li key={c.short_hash} title={c.subject}>
                      <span className="fi-commit-subject">{c.subject}</span>
                      <span className="fi-commit-meta">{c.author}{c.committed_at ? ` · ${relativeTime(c.committed_at)}` : ""}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {!owner && couplings.length === 0 && !impact && risks.length === 0 ? (
              <p className="fi-muted">Nothing notable recorded for this file yet — it may be new or rarely changed.</p>
            ) : null}
          </div>
        ) : null}
      </aside>
    </div>
  );
}
