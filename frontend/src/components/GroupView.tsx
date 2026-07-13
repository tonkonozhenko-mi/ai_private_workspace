import { useCallback, useEffect, useMemo, useState } from "react";

import {
  addGroupMemory,
  addProjectGroupMember,
  askProjectGroupStream,
  buildGroupHandbook,
  deleteGroupMemory,
  deleteProjectGroup,
  getGroupHandbook,
  getProjectGroup,
  getProjectGroupOverview,
  getWorkspaceDashboard,
  listGroupMemory,
  pinGroupMemory,
  removeProjectGroupMember,
  updateProjectGroup,
} from "../api/client";
import type {
  GroupAskResponse,
  GroupMemoryItem,
  GroupOverviewResponse,
  ProjectGroupDetail,
  WorkspaceDashboard,
} from "../api/types";
import { formatSourceLabel } from "../lib/sourceLabel";
import { AnswerFeedback } from "./AnswerFeedback";
import { AnswerTracePanel } from "./AnswerTracePanel";
import { MarkdownAnswer } from "./AskWorkspace";
import { ProjectIntelligence } from "./ProjectIntelligence";

const MEMORY_KIND_LABEL: Record<string, string> = {
  note: "Note",
  decision: "Decision",
  correction: "Correction",
  fact: "Fact",
  qa: "Earlier Q&A",
};

type GroupTab = "home" | "ask" | "intelligence";

const TABS: { id: GroupTab; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "ask", label: "Ask" },
  { id: "intelligence", label: "Intelligence" },
];

interface GroupViewProps {
  groupId: string;
  groupName: string;
  allWorkspaces: { id: string; name: string }[];
  autoRename?: boolean;
  onChanged: () => void;
  onDeleted?: () => void;
  onAutoRenameHandled?: () => void;
}

export function GroupView({
  groupId,
  groupName,
  allWorkspaces,
  autoRename = false,
  onChanged,
  onDeleted,
  onAutoRenameHandled,
}: GroupViewProps) {
  const [detail, setDetail] = useState<ProjectGroupDetail | null>(null);
  const [overview, setOverview] = useState<GroupOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState<GroupTab>("home");
  const [error, setError] = useState<string | null>(null);
  const [busyMember, setBusyMember] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [draftName, setDraftName] = useState(groupName);

  // A freshly created group lands in rename mode so it can be named immediately.
  useEffect(() => {
    if (autoRename) {
      setDraftName(groupName);
      setRenaming(true);
      onAutoRenameHandled?.();
    }
    // Only react to the initial autoRename signal for this group.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRename, groupId]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [d, o] = await Promise.all([
        getProjectGroup(groupId),
        getProjectGroupOverview(groupId),
      ]);
      setDetail(d);
      setOverview(o);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the group.");
    }
  }, [groupId]);

  useEffect(() => {
    setDetail(null);
    setOverview(null);
    void load();
  }, [load]);

  const memberIds = new Set(detail?.members.map((m) => m.workspace_id) ?? []);
  const addable = allWorkspaces.filter((w) => !memberIds.has(w.id));

  const handleAdd = async (workspaceId: string) => {
    setBusyMember(workspaceId);
    try {
      await addProjectGroupMember(groupId, workspaceId);
      await load();
      onChanged();
    } finally {
      setBusyMember(null);
    }
  };
  const handleRemove = async (workspaceId: string) => {
    setBusyMember(workspaceId);
    try {
      await removeProjectGroupMember(groupId, workspaceId);
      await load();
      onChanged();
    } finally {
      setBusyMember(null);
    }
  };

  const saveRename = async () => {
    const name = draftName.trim();
    setRenaming(false);
    if (!name || name === groupName) return;
    try {
      await updateProjectGroup(groupId, { name });
      onChanged();
    } catch {
      // keep the old name on failure
    }
  };

  // window.confirm is disabled in the Tauri webview, so deletion uses an inline
  // two-step confirm instead of a native dialog.
  const handleDelete = async () => {
    try {
      await deleteProjectGroup(groupId);
      onChanged();
      onDeleted?.();
    } catch {
      // ignore
    }
  };

  return (
    <div className="grp">
      <header className="grp-head">
        <div>
          <p className="grp-eyebrow">Project group</p>
          {renaming ? (
            <input
              className="grp-title-input"
              value={draftName}
              autoFocus
              onChange={(e) => setDraftName(e.target.value)}
              onBlur={saveRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveRename();
                if (e.key === "Escape") {
                  setDraftName(groupName);
                  setRenaming(false);
                }
              }}
            />
          ) : (
            <h1
              className="grp-title"
              title="Click to rename"
              onClick={() => {
                setDraftName(groupName);
                setRenaming(true);
              }}
            >
              {groupName}
              <span className="grp-title-edit" aria-hidden="true">✎</span>
            </h1>
          )}
          <p className="grp-subtitle">
            {detail ? `${detail.member_count} ${detail.member_count === 1 ? "repository" : "repositories"}` : "…"}
            {" "}· treated as one project for Home, Ask and Intelligence
          </p>
        </div>
        {confirmDelete ? (
          <span className="grp-delete-confirm">
            <span className="grp-delete-q">Delete group?</span>
            <button type="button" className="grp-delete" onClick={() => void handleDelete()}>
              Yes, delete
            </button>
            <button type="button" className="grp-delete-cancel" onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
          </span>
        ) : (
          <button type="button" className="grp-delete" onClick={() => setConfirmDelete(true)}>
            Delete group
          </button>
        )}
      </header>

      {error ? <p className="grp-error">{error}</p> : null}

      <nav className="grp-tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`grp-tab${activeTab === tab.id ? " is-active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <MemberBar
        detail={detail}
        addable={addable}
        busyMember={busyMember}
        onAdd={handleAdd}
        onRemove={handleRemove}
      />

      <div className="grp-body">
        {activeTab === "home" ? <GroupHome overview={overview} groupId={groupId} /> : null}
        {activeTab === "ask" ? <GroupAsk groupId={groupId} overview={overview} /> : null}
        {activeTab === "intelligence" ? <GroupIntelligence overview={overview} /> : null}
      </div>
    </div>
  );
}

function MemberBar({
  detail,
  addable,
  busyMember,
  onAdd,
  onRemove,
}: {
  detail: ProjectGroupDetail | null;
  addable: { id: string; name: string }[];
  busyMember: string | null;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  if (!detail) return null;
  return (
    <div className="grp-members">
      {detail.members.map((m) => (
        <span
          key={m.workspace_id}
          className={`grp-member-chip${busyMember === m.workspace_id ? " is-busy" : ""}`}
          title={m.project_path}
        >
          {m.name}
          <button
            type="button"
            aria-label={`Remove ${m.name}`}
            disabled={busyMember !== null}
            onClick={() => onRemove(m.workspace_id)}
          >
            ×
          </button>
        </span>
      ))}
      {detail.members.length === 0 ? (
        <span className="grp-members-empty">No repositories yet — add some →</span>
      ) : null}
      {addable.length > 0 ? (
        <select
          className="grp-add-select"
          value=""
          disabled={busyMember !== null}
          onChange={(e) => {
            if (e.target.value) onAdd(e.target.value);
          }}
        >
          <option value="">+ Add repository…</option>
          {addable.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  );
}

function Metric({ value, label, sub }: { value: string | number; label: string; sub?: string }) {
  return (
    <div className="grp-metric">
      <strong>{value}</strong>
      <span className="grp-metric-label">{label}</span>
      {sub ? <span className="grp-metric-sub">{sub}</span> : null}
    </div>
  );
}

function GroupHome({ overview, groupId }: { overview: GroupOverviewResponse | null; groupId: string }) {
  if (!overview) return <p className="grp-muted">Loading…</p>;
  if (overview.member_count === 0) {
    return <p className="grp-muted">No repositories in this group yet. Add one above.</p>;
  }
  const t = overview.totals;
  // The cards show what this group is actually made of. They used to be four fixed
  // code-shaped numbers, so a group holding a wiki led with "0 services" and never
  // mentioned its 169 pages. A count of zero is not worth a card.
  // "1 infrastructure components" is a number and a word that disagree with it.
  const plural = (count: number, singular: string, many?: string) =>
    count === 1 ? singular : (many ?? `${singular}s`);
  const cards: { value: number; label: string; sub?: string }[] = [
    {
      value: t.repos ?? overview.member_count,
      label: plural(t.repos ?? overview.member_count, "project"),
    },
  ];
  if ((t.pages ?? 0) > 0) {
    cards.push({
      value: t.pages ?? 0,
      label: plural(t.pages ?? 0, "document"),
      sub:
        (t.decisions ?? 0) > 0
          ? `${t.decisions} ${plural(t.decisions, "decision record")}`
          : undefined,
    });
  }
  if ((t.services ?? 0) > 0) {
    cards.push({ value: t.services, label: plural(t.services, "service") });
  }
  if ((t.infrastructure ?? 0) > 0) {
    cards.push({
      value: t.infrastructure,
      label: plural(t.infrastructure, "infrastructure component"),
    });
  }
  if ((t.environments ?? 0) > 0) {
    cards.push({
      value: t.environments,
      label: plural(t.environments, "environment"),
      sub: overview.environments.join(", ") || undefined,
    });
  }
  cards.push({
    value: t.commits_last_7_days ?? 0,
    label: `${plural(t.commits_last_7_days ?? 0, "commit")} this week`,
  });
  return (
    <div className="grp-stack">
      <div className="grp-hero">
        {cards.slice(0, 4).map((card) => (
          <Metric key={card.label} value={card.value} label={card.label} sub={card.sub} />
        ))}
      </div>

      <section className="grp-section">
        <p className="grp-shead">Repositories</p>
        <ul className="grp-repo-list">
          {overview.members.map((m) => (
            <li key={m.workspace_id} className="grp-repo">
              <div className="grp-repo-top">
                <span className="grp-repo-name">{m.name}</span>
                {m.branch ? <span className="grp-repo-branch">{m.branch}</span> : null}
                {!m.built ? <span className="grp-repo-tag">not analyzed</span> : null}
              </div>
              <p className="grp-repo-desc">{m.description}</p>
              <p className="grp-repo-meta">
                {m.is_repo
                  ? `${m.total_commits.toLocaleString()} commits · ${m.contributors_count} contributors · ${m.commits_last_7_days} this week`
                  : "Not a git repository"}
                {m.last_commit_subject ? ` · latest: ${m.last_commit_subject}` : ""}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <GroupMemory groupId={groupId} />
    </div>
  );
}

function GroupMemory({ groupId }: { groupId: string }) {
  const [items, setItems] = useState<GroupMemoryItem[]>([]);
  const [draft, setDraft] = useState("");
  const [handbook, setHandbook] = useState<string | null>(null);
  const [showHandbook, setShowHandbook] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [mem, hb] = await Promise.all([listGroupMemory(groupId), getGroupHandbook(groupId)]);
      setItems(mem.items);
      setHandbook(hb.has_handbook ? (hb.handbook ?? null) : null);
    } catch {
      // optional
    }
  }, [groupId]);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = items.filter((i) => i.kind !== "handbook");

  const add = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await addGroupMemory(groupId, text);
      setDraft("");
      await load();
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: string) => {
    await deleteGroupMemory(groupId, id);
    await load();
  };
  const togglePin = async (item: GroupMemoryItem) => {
    await pinGroupMemory(groupId, item.id, !item.pinned);
    await load();
  };
  const regenerate = async () => {
    setBusy(true);
    try {
      const res = await buildGroupHandbook(groupId);
      setHandbook(res.handbook);
      setShowHandbook(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="grp-section">
      <p className="grp-shead">Notes &amp; handbook</p>
      <p className="grp-hint">
        What you tell the group here is remembered and fed into every group answer — so the AI
        gets better at this project over time.
      </p>
      <div className="grp-ask-row">
        <input
          className="grp-ask-input"
          type="text"
          value={draft}
          placeholder="e.g. prod is called 'prd' in this org; billing lives in the api repo"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
          disabled={busy}
        />
        <button type="button" className="grp-button" onClick={add} disabled={busy || draft.trim().length === 0}>
          Remember
        </button>
      </div>

      {visible.length > 0 ? (
        <ul className="grp-memory-list">
          {visible.map((item) => (
            <li key={item.id} className="grp-memory-item">
              <span className={`grp-memory-kind${item.pinned ? " is-pinned" : ""}`}>
                {MEMORY_KIND_LABEL[item.kind] ?? item.kind}
              </span>
              <span className="grp-memory-text">{item.text}</span>
              <button type="button" className="grp-memory-act" title={item.pinned ? "Unpin" : "Pin"} onClick={() => togglePin(item)}>
                {item.pinned ? "★" : "☆"}
              </button>
              <button type="button" className="grp-memory-act" title="Delete" onClick={() => remove(item.id)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="grp-muted">No notes yet.</p>
      )}

      <p className="grp-hint">
        {handbook
          ? "Group handbook is generated from all member repos and fed into every group answer as background — nothing to do with it, it just keeps answers grounded."
          : "Generate a group handbook — a short summary across all repos that's automatically used as background in every group answer."}
      </p>
      <div className="grp-handbook-row">
        <button type="button" className="grp-button" onClick={regenerate} disabled={busy}>
          {handbook ? "Regenerate handbook" : "Generate handbook"}
        </button>
        {handbook ? <span className="pm-handbook-badge">In use</span> : null}
        {handbook ? (
          <button type="button" className="grp-link" onClick={() => setShowHandbook((v) => !v)}>
            {showHandbook ? "Hide handbook" : "View handbook"}
          </button>
        ) : null}
      </div>
      {handbook && showHandbook ? <pre className="grp-handbook">{handbook}</pre> : null}
    </section>
  );
}

// A group is a *portfolio*, not one merged project. So Intelligence compares
// repos rather than dumping a flat union: which repo has which environment,
// what tech is shared vs unique, and which risk patterns repeat where. A repo
// filter keeps the repo dimension first-class and lets you isolate one repo.
function GroupIntelligence({ overview }: { overview: GroupOverviewResponse | null }) {
  const [active, setActive] = useState<Set<string> | null>(null); // null = all repos
  // Drill-down: open one member's FULL single-project Intelligence in place, so the
  // group view is comparison on top + the same per-project depth on demand.
  const [drillId, setDrillId] = useState<string | null>(null);
  const [drillDashboard, setDrillDashboard] = useState<WorkspaceDashboard | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);
  const [drillError, setDrillError] = useState<string | null>(null);

  const members = overview?.members ?? [];
  const drillMember = members.find((m) => m.workspace_id === drillId) ?? null;

  useEffect(() => {
    if (!drillId) {
      setDrillDashboard(null);
      setDrillError(null);
      return;
    }
    let cancelled = false;
    setDrillLoading(true);
    setDrillError(null);
    getWorkspaceDashboard(drillId)
      .then((d) => {
        if (!cancelled) setDrillDashboard(d);
      })
      .catch((err) => {
        if (!cancelled)
          setDrillError(err instanceof Error ? err.message : "Could not load this project.");
      })
      .finally(() => {
        if (!cancelled) setDrillLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [drillId]);
  const shown = useMemo(
    () => members.filter((m) => active === null || active.has(m.workspace_id)),
    [members, active],
  );

  const envMatrix = useMemo(() => {
    const envs = Array.from(new Set(shown.flatMap((m) => m.environments))).sort();
    return envs.map((env) => ({
      env,
      repos: shown.map((m) => ({ name: m.name, has: m.environments.includes(env) })),
    }));
  }, [shown]);

  const techGroups = useMemo(() => {
    const techToRepos = new Map<string, string[]>();
    for (const m of shown) {
      for (const tech of m.technology_chips) {
        const list = techToRepos.get(tech) ?? [];
        if (!list.includes(m.name)) list.push(m.name);
        techToRepos.set(tech, list);
      }
    }
    const total = shown.length;
    const common: string[] = [];
    const partial: { tech: string; count: number }[] = [];
    const uniqueByRepo = new Map<string, string[]>();
    for (const [tech, repos] of techToRepos) {
      if (total > 1 && repos.length === total) common.push(tech);
      else if (repos.length === 1) {
        const list = uniqueByRepo.get(repos[0]) ?? [];
        list.push(tech);
        uniqueByRepo.set(repos[0], list);
      } else partial.push({ tech, count: repos.length });
    }
    common.sort();
    partial.sort((a, b) => b.count - a.count || a.tech.localeCompare(b.tech));
    return { common, partial, uniqueByRepo, total };
  }, [shown]);

  const riskGroups = useMemo(() => {
    const shownIds = new Set(shown.map((m) => m.workspace_id));
    const byTitle = new Map<
      string,
      {
        severity: string;
        attention: string;
        total: number;
        repos: Map<string, number>;
        explanation: string;
        recommendation: string | null;
      }
    >();
    for (const r of overview?.risks ?? []) {
      if (!shownIds.has(r.workspace_id)) continue;
      const entry =
        byTitle.get(r.title) ??
        {
          severity: r.severity,
          attention: r.attention ?? r.severity,
          total: 0,
          repos: new Map(),
          explanation: "",
          recommendation: null,
        };
      entry.total += 1;
      entry.repos.set(r.workspace_name, (entry.repos.get(r.workspace_name) ?? 0) + 1);
      // Keep the most severe label seen for this title.
      if (r.severity === "high") {
        entry.severity = "high";
        entry.attention = r.attention ?? "high";
      }
      // Keep the first human-readable detail seen (all repos share the finding text).
      if (!entry.explanation && r.explanation) entry.explanation = r.explanation;
      if (!entry.recommendation && r.recommendation) entry.recommendation = r.recommendation;
      byTitle.set(r.title, entry);
    }
    return Array.from(byTitle.entries())
      .map(([title, v]) => ({ title, ...v }))
      .sort((a, b) => (a.severity === b.severity ? b.total - a.total : a.severity === "high" ? -1 : 1));
  }, [overview, shown]);

  if (!overview) return <p className="grp-muted">Loading…</p>;
  if (overview.member_count === 0) {
    return <p className="grp-muted">No repositories in this group yet.</p>;
  }

  // Drilled into one repo: show its full single-project Intelligence, same
  // component and depth as opening that project on its own.
  if (drillId) {
    return (
      <div className="grp-stack">
        <div className="grp-drill-bar">
          <button type="button" className="grp-link" onClick={() => setDrillId(null)}>
            ← Back to comparison
          </button>
          <span className="grp-drill-title">
            {drillMember?.name ?? "Project"} · full intelligence
          </span>
        </div>
        {drillLoading ? <p className="grp-muted">Loading…</p> : null}
        {drillError ? <p className="grp-error">{drillError}</p> : null}
        {drillDashboard ? <ProjectIntelligence dashboard={drillDashboard} /> : null}
      </div>
    );
  }

  const toggle = (id: string) =>
    setActive((prev) => {
      const base = prev ?? new Set(members.map((m) => m.workspace_id));
      const next = new Set(base);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      if (next.size === 0 || next.size === members.length) return null; // empty or all → all
      return next;
    });

  return (
    <div className="grp-stack">
      {members.length > 1 ? (
        <div className="grp-filter">
          <span className="grp-filter-label">Show</span>
          {members.map((m) => {
            const on = active === null || active.has(m.workspace_id);
            return (
              <button
                key={m.workspace_id}
                type="button"
                className={`grp-filter-chip${on ? " is-on" : ""}`}
                onClick={() => toggle(m.workspace_id)}
                aria-pressed={on}
              >
                {m.name}
              </button>
            );
          })}
          {active !== null ? (
            <button type="button" className="grp-link" onClick={() => setActive(null)}>
              All repos
            </button>
          ) : null}
        </div>
      ) : null}

      <section className="grp-section">
        <p className="grp-shead">Per repository — open the full project view</p>
        <p className="grp-hint">Compare across repos above; open any one for its complete Intelligence.</p>
        <ul className="grp-memberlist">
          {shown.map((m) => (
            <li key={m.workspace_id} className="grp-memberrow">
              <div className="grp-memberrow-main">
                <span className="grp-memberrow-name">{m.name}</span>
                <span className="grp-memberrow-desc">{m.description}</span>
              </div>
              <button
                type="button"
                className="grp-link"
                onClick={() => setDrillId(m.workspace_id)}
                disabled={!m.built}
              >
                {m.built ? "Open full intelligence →" : "Not analyzed yet"}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="grp-section">
        <p className="grp-shead">Environments — which repo deploys where</p>
        <p className="grp-hint">A ✓ means that repo defines that environment.</p>
        {envMatrix.length > 0 && shown.length > 0 ? (
          <div className="grp-matrix-wrap">
            <table className="grp-matrix">
              <thead>
                <tr>
                  <th />
                  {shown.map((m) => (
                    <th key={m.workspace_id} title={m.name}>{m.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {envMatrix.map((row) => (
                  <tr key={row.env}>
                    <td className="grp-matrix-row-h">
                      {row.env}
                      {row.env.toLowerCase().includes("prod") ? <span className="grp-prod-dot" title="production" /> : null}
                    </td>
                    {row.repos.map((c, i) => (
                      <td key={i} className={c.has ? "is-yes" : "is-no"}>{c.has ? "✓" : "·"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="grp-muted">No environments detected in the selected repos.</p>
        )}
      </section>

      <section className="grp-section">
        <p className="grp-shead">Technologies — shared vs specific</p>
        {techGroups.common.length === 0 && techGroups.partial.length === 0 && techGroups.uniqueByRepo.size === 0 ? (
          <p className="grp-muted">No technologies detected in the selected repos.</p>
        ) : (
          <div className="grp-tech-groups">
            {techGroups.common.length > 0 ? (
              <div className="grp-tech-group">
                <p className="grp-tech-label">Common to all {techGroups.total} repos</p>
                <div className="grp-chips">
                  {techGroups.common.map((t) => <span key={t} className="grp-chip is-common">{t}</span>)}
                </div>
              </div>
            ) : null}
            {techGroups.partial.length > 0 ? (
              <div className="grp-tech-group">
                <p className="grp-tech-label">Shared by some</p>
                <div className="grp-chips">
                  {techGroups.partial.map((p) => (
                    <span key={p.tech} className="grp-chip">{p.tech}<span className="grp-chip-count">{p.count}/{techGroups.total}</span></span>
                  ))}
                </div>
              </div>
            ) : null}
            {Array.from(techGroups.uniqueByRepo.entries()).map(([repo, techs]) => (
              <div className="grp-tech-group" key={repo}>
                <p className="grp-tech-label">Only in {repo}</p>
                <div className="grp-chips">
                  {techs.sort().map((t) => <span key={t} className="grp-chip">{t}</span>)}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="grp-section">
        <p className="grp-shead">Risk patterns — what repeats, and where</p>
        <p className="grp-hint">
          Same finding across repos is grouped, so you fix the pattern, not 20 rows. These are
          leads for a human, not verdicts.
        </p>
        {riskGroups.length > 0 ? (
          <ul className="grp-riskgroups">
            {riskGroups.map((r) => (
              <li key={r.title} className="grp-riskgroup">
                {/* The same softened word the single view uses — a risk is a lead for
                    a human, not a verdict, whichever screen it is read on. */}
                <span className={`grp-sev grp-sev-${r.severity}`}>{r.attention}</span>
                <span className="grp-riskgroup-title">{r.title}</span>
                <span className="grp-riskgroup-count">{r.total}×</span>
                <span className="grp-riskgroup-repos">
                  {Array.from(r.repos.entries())
                    .sort((a, b) => b[1] - a[1])
                    .map(([name, n]) => `${name} ×${n}`)
                    .join(" · ")}
                </span>
                {r.explanation ? (
                  <p className="grp-riskgroup-why">{r.explanation}</p>
                ) : null}
                {r.recommendation ? (
                  <p className="grp-riskgroup-fix">
                    <span className="grp-riskgroup-fix-label">Fix</span> {r.recommendation}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="grp-muted">Nothing risky flagged across the selected repos.</p>
        )}
      </section>
    </div>
  );
}

type GroupSource = GroupAskResponse["sources"][number];

function groupSourcesByRepo(sources: GroupSource[]): [string, GroupSource[]][] {
  const map = new Map<string, GroupSource[]>();
  for (const s of sources) {
    const list = map.get(s.workspace_name) ?? [];
    list.push(s);
    map.set(s.workspace_name, list);
  }
  return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
}

/** The questions a group of *these* members can answer.
 *
 * The composer offered "Where is the user record created and consumed?" to a group of a
 * Terraform monorepo and a wiki — a developer's example, in a place that has no
 * application. What a group is *for* is the question no single member can answer, so
 * the starters are built from what the members are actually made of. */
function groupStarters(overview: GroupOverviewResponse | null): string[] {
  const totals = overview?.totals ?? {};
  const questions: string[] = [];
  const hasDocs = (totals.pages ?? 0) > 0;
  const hasInfra = (totals.infrastructure ?? 0) > 0 || (totals.environments ?? 0) > 0;
  if (hasDocs && (hasInfra || (totals.services ?? 0) > 0)) {
    // The whole point of a group: a decision in one place, its implementation in another.
    questions.push("What did we decide, and where is it implemented?");
  }
  if (hasInfra) questions.push("Which environments exist, and which repository deploys where?");
  if (hasDocs) questions.push("Which decisions have been recorded, and are any of them stale?");
  if ((totals.services ?? 0) > 0) questions.push("Which services talk to which?");
  questions.push("What changed across these projects recently?");
  return questions.slice(0, 4);
}

function GroupAsk({
  groupId,
  overview,
}: {
  groupId: string;
  overview: GroupOverviewResponse | null;
}) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<GroupAskResponse | null>(null);
  const [streamed, setStreamed] = useState("");
  const [loading, setLoading] = useState(false);
  const [think, setThink] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);

  const starters = groupStarters(overview);

  async function submit(text?: string) {
    const trimmed = (text ?? question).trim();
    if (!trimmed || loading) return;
    // The composer empties on send, as it does in the single-project Ask — the question
    // is now in the conversation, and leaving it in the box invites sending it twice.
    setQuestion("");
    setLoading(true);
    setError(null);
    setResult(null);
    setStreamed("");
    try {
      const final = await askProjectGroupStream(groupId, trimmed, {
        think,
        onToken: (text) => setStreamed((prev) => prev + text),
      });
      setResult(final);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The group could not answer.");
    } finally {
      setLoading(false);
    }
  }

  const answerText = result?.answer ?? streamed;
  const memoryNote =
    result && (result.memory_used > 0 || result.facts_used > 0)
      ? `Used ${result.memory_used} memory note(s) and ${result.facts_used} map fact(s) from across the group.`
      : null;

  return (
    <div className="grp-ask">
      <p className="grp-hint">
        Ask once and the answer is drawn from every repository in the group, streamed as it's
        written. Each source is labelled with the repo it came from. Nothing leaves this computer.
      </p>
      {!result && !loading && starters.length > 0 ? (
        <div className="grp-ask-starters">
          {starters.map((q) => (
            <button key={q} type="button" className="grp-ask-starter" onClick={() => void submit(q)}>
              {q}
            </button>
          ))}
        </div>
      ) : null}
      <div className="grp-ask-row">
        <input
          className="grp-ask-input"
          type="text"
          value={question}
          placeholder={starters[0] ? `e.g. ${starters[0]}` : "Ask across every repository in this group"}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void submit();
          }}
          disabled={loading}
        />
        <button
          type="button"
          className="grp-button grp-button-primary"
          onClick={() => void submit()}
          disabled={loading || question.trim().length === 0}
        >
          {loading ? "Asking…" : "Ask the group"}
        </button>
      </div>
      <label className="grp-reasoning">
        <input type="checkbox" checked={think} onChange={(e) => setThink(e.target.checked)} disabled={loading} />
        Reasoning — let the model think step by step before answering
      </label>

      {error ? <p className="grp-muted">{error}</p> : null}

      {answerText || loading ? (
        <div className="grp-answer">
          <p className="grp-answer-eyebrow">Answer · across {result ? result.contributions.length : "all"} repos</p>
          <div className="grp-answer-body">
            <MarkdownAnswer content={answerText} />
            {loading && !result ? <span className="grp-caret" /> : null}
          </div>

          {result && (result.quality_warnings ?? []).some((w) => w.severity === "high") ? (
            <div className="ask-trust-notice" role="alert">
              {(result.quality_warnings ?? [])
                .filter((w) => w.severity === "high")
                .map((warning, index) => (
                  <p key={`${warning.code}-${index}`}>{warning.message}</p>
                ))}
            </div>
          ) : null}

          {result && result.contributions.length > 0 ? (
            <div className="grp-contrib-bar">
              {result.contributions.map((c) => (
                <span
                  key={c.workspace_name}
                  className={`grp-contrib-chip${c.indexed ? "" : " is-empty"}`}
                  title={c.indexed ? `${c.chunks_used} chunk(s) used` : "not indexed"}
                >
                  <span className="grp-contrib-dot" />
                  {c.workspace_name}
                  <span className="grp-contrib-n">{c.indexed ? c.chunks_used : "—"}</span>
                </span>
              ))}
            </div>
          ) : null}
          {result &&
          (result.memory_used > 0 || result.facts_used > 0 || result.sources.length > 0) ? (
            <>
              <button type="button" className="why-answer-btn" onClick={() => setTraceOpen(true)}>
                <span className="wab-icon" aria-hidden="true">?</span>
                How did the AI reach this?
                <span className="wab-meta">
                  {result.memory_used} note{result.memory_used === 1 ? "" : "s"} · {result.facts_used} map
                  fact{result.facts_used === 1 ? "" : "s"} · {result.contributions.length} repo
                  {result.contributions.length === 1 ? "" : "s"}
                </span>
              </button>
              {traceOpen ? (
                <AnswerTracePanel
                  scope="group"
                  memoryUsed={result.memory_used}
                  factsUsed={result.facts_used}
                  chunks={result.used_context_chunks}
                  files={result.sources.map((source) => ({
                    source_path: source.source_path,
                    repo: source.workspace_name,
                    chunk_id: source.chunk_id,
                    score: source.score,
                  }))}
                  onClose={() => setTraceOpen(false)}
                />
              ) : null}
            </>
          ) : memoryNote ? (
            <p className="grp-memory-note">{memoryNote}</p>
          ) : null}

          {result && result.sources.length > 0 ? (
            <div className="grp-sources">
              <p className="grp-shead">Sources by repository</p>
              {groupSourcesByRepo(result.sources).map(([repo, items]) => (
                <div className="grp-source-group" key={repo}>
                  <p className="grp-source-grouphead">{repo}<span className="grp-source-groupn">{items.length}</span></p>
                  <ul>
                    {items.map((s) => (
                      <li key={s.chunk_id} title={s.preview}>
                        <code>{formatSourceLabel(s.source_path)}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : null}
          {result ? (
            <AnswerFeedback
              question={question}
              answer={result.answer}
              onSave={(text, k) => addGroupMemory(groupId, text, k)}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
