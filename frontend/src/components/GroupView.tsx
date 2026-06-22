import { useCallback, useEffect, useState } from "react";

import {
  addProjectGroupMember,
  askProjectGroupStream,
  deleteProjectGroup,
  getProjectGroup,
  getProjectGroupOverview,
  removeProjectGroupMember,
  updateProjectGroup,
} from "../api/client";
import type {
  GroupAskResponse,
  GroupOverviewResponse,
  ProjectGroupDetail,
} from "../api/types";

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
  onChanged: () => void;
  onDeleted?: () => void;
}

export function GroupView({ groupId, groupName, allWorkspaces, onChanged, onDeleted }: GroupViewProps) {
  const [detail, setDetail] = useState<ProjectGroupDetail | null>(null);
  const [overview, setOverview] = useState<GroupOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState<GroupTab>("home");
  const [error, setError] = useState<string | null>(null);
  const [busyMember, setBusyMember] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [draftName, setDraftName] = useState(groupName);

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

  const handleDelete = async () => {
    if (!window.confirm(`Delete the group "${groupName}"? The repositories themselves are not deleted.`)) {
      return;
    }
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
            </h1>
          )}
          <p className="grp-subtitle">
            {detail ? `${detail.member_count} ${detail.member_count === 1 ? "repository" : "repositories"}` : "…"}
            {" "}· treated as one project for Home, Ask and Intelligence
          </p>
        </div>
        <button type="button" className="grp-delete" onClick={handleDelete}>
          Delete group
        </button>
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
        {activeTab === "home" ? <GroupHome overview={overview} /> : null}
        {activeTab === "ask" ? <GroupAsk groupId={groupId} /> : null}
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

function GroupHome({ overview }: { overview: GroupOverviewResponse | null }) {
  if (!overview) return <p className="grp-muted">Loading…</p>;
  if (overview.member_count === 0) {
    return <p className="grp-muted">No repositories in this group yet. Add one above.</p>;
  }
  const t = overview.totals;
  return (
    <div className="grp-stack">
      <div className="grp-hero">
        <Metric value={t.repos ?? overview.member_count} label="repositories" />
        <Metric value={t.services ?? 0} label="services" sub="across all repos" />
        <Metric value={t.environments ?? 0} label="environments" sub={overview.environments.join(", ") || undefined} />
        <Metric value={t.commits_last_7_days ?? 0} label="commits this week" />
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
    </div>
  );
}

function GroupIntelligence({ overview }: { overview: GroupOverviewResponse | null }) {
  if (!overview) return <p className="grp-muted">Loading…</p>;
  if (overview.member_count === 0) {
    return <p className="grp-muted">No repositories in this group yet.</p>;
  }
  return (
    <div className="grp-stack">
      <section className="grp-section">
        <p className="grp-shead">Environments across the group</p>
        <p className="grp-hint">Unioned by name — the same environment may live in several repos.</p>
        {overview.environments.length > 0 ? (
          <div className="grp-chips">
            {overview.environments.map((e) => (
              <span key={e} className="grp-chip">{e}</span>
            ))}
          </div>
        ) : (
          <p className="grp-muted">No environments detected yet.</p>
        )}
      </section>

      <section className="grp-section">
        <p className="grp-shead">Technologies</p>
        {overview.technologies.length > 0 ? (
          <div className="grp-chips">
            {overview.technologies.map((tech) => (
              <span key={tech} className="grp-chip">{tech}</span>
            ))}
          </div>
        ) : (
          <p className="grp-muted">No technologies detected yet.</p>
        )}
      </section>

      <section className="grp-section">
        <p className="grp-shead">
          Risks
          {overview.totals.risks_high ? ` · ${overview.totals.risks_high} high` : ""}
          {overview.totals.risks_medium ? ` · ${overview.totals.risks_medium} medium` : ""}
        </p>
        {overview.risks.length > 0 ? (
          <ul className="grp-risks">
            {overview.risks.map((r, i) => (
              <li key={i} className="grp-risk">
                <span className={`grp-sev grp-sev-${r.severity}`}>{r.severity}</span>
                <span className="grp-risk-title">{r.title}</span>
                <span className="grp-risk-repo">{r.workspace_name}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="grp-muted">Nothing risky flagged across the group.</p>
        )}
      </section>
    </div>
  );
}

function GroupAsk({ groupId }: { groupId: string }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<GroupAskResponse | null>(null);
  const [streamed, setStreamed] = useState("");
  const [loading, setLoading] = useState(false);
  const [think, setThink] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
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
      <div className="grp-ask-row">
        <input
          className="grp-ask-input"
          type="text"
          value={question}
          placeholder="e.g. Where is the user record created and consumed?"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          disabled={loading}
        />
        <button
          type="button"
          className="grp-button grp-button-primary"
          onClick={submit}
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
          <p className="grp-ask-answer">
            {answerText}
            {loading && !result ? <span className="grp-caret" /> : null}
          </p>
          {memoryNote ? <p className="grp-memory-note">{memoryNote}</p> : null}
          {result && result.contributions.length > 0 ? (
            <p className="grp-contrib">
              {result.contributions
                .map((c) =>
                  c.indexed
                    ? `${c.workspace_name}: ${c.chunks_used} chunk(s)`
                    : `${c.workspace_name}: not indexed`,
                )
                .join(" · ")}
            </p>
          ) : null}
          {result && result.sources.length > 0 ? (
            <div className="grp-sources">
              <p className="grp-shead">Sources</p>
              <ul>
                {result.sources.map((s) => (
                  <li key={s.chunk_id} title={s.preview}>
                    <span className="grp-source-repo">{s.workspace_name}</span>
                    <code>{s.source_path}</code>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
