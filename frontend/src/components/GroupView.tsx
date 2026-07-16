import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  addGroupMemory,
  getWorkspaceScanChanges,
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
  ScanChanges,
  WorkspaceDashboard,
} from "../api/types";
import { useProjectRefresh } from "../hooks/useProjectRefresh";
import {
  memberChangeBadge,
  memberChangeDetail,
  staleRepositoryNames,
} from "../lib/groupStaleness";
import { formatSourceLabel } from "../lib/sourceLabel";
import { hasUserInteracted } from "../lib/userInteraction";
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
  // Asked once for the whole group view, not once per tab: the walk that answers
  // it is the expensive part, and Home's badge and Ask's source note are the same
  // question. Two answers to one question is how two screens start disagreeing.
  const { changes, recheck } = useMemberChanges(overview?.members ?? []);

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

      {/* Membership belongs where the group is managed. On Ask and Intelligence it
          was a second row of chips that looked exactly like that tab's own filter
          and did something else entirely — twins that are not twins. */}
      {activeTab === "home" ? (
        <MemberBar
          detail={detail}
          addable={addable}
          busyMember={busyMember}
          onAdd={handleAdd}
          onRemove={handleRemove}
        />
      ) : null}

      <div className="grp-body">
        {activeTab === "home"
          ? <GroupHome overview={overview} groupId={groupId} changes={changes} onRecheck={recheck} />
          : null}
        {activeTab === "ask"
          ? <GroupAsk groupId={groupId} overview={overview} changes={changes} />
          : null}
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

/** A section heading: a short CAPS name, and — if it needs one — a plain-text
 * line saying what the section is. The name was carrying the explanation inside
 * the uppercase ("ENVIRONMENTS — WHICH REPO DEPLOYS WHERE"), which is a label
 * shouting a sentence. One pattern, every section. */
function SectionHead({
  name,
  sub,
  action,
}: {
  name: string;
  sub?: string;
  action?: ReactNode;
}) {
  return (
    <div className="grp-sechead">
      <div className="grp-sechead-text">
        <p className="grp-shead">{name}</p>
        {sub ? <p className="grp-subhead">{sub}</p> : null}
      </div>
      {action ? <div className="grp-sechead-act">{action}</div> : null}
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

/** What a repository row can honestly say about its git history.
 *
 * "0 commits · 0 contributors · 0 this week" is three facts that are one fact —
 * and for a folder that was never a repository, it is not even that: it is the
 * shape of an answer with no answer in it. Say the one true thing instead. */
function repoMeta(m: GroupOverviewResponse["members"][number]): string {
  if (!m.is_repo) return "Not a git repository";
  const parts: string[] = [];
  if (m.total_commits > 0) parts.push(`${m.total_commits.toLocaleString()} commits`);
  if (m.contributors_count > 0) parts.push(`${m.contributors_count} contributors`);
  if (m.commits_last_7_days > 0) parts.push(`${m.commits_last_7_days} this week`);
  if (m.last_commit_subject) parts.push(`latest: ${m.last_commit_subject}`);
  return parts.length > 0 ? parts.join(" · ") : "No commits yet";
}

/** Asks each member what has changed on disk since it was last indexed.
 *
 * The group holds no change log of its own: it calls the member's own endpoint,
 * the same one that member's Home calls, and keeps the answers only for as long
 * as this screen is open. Which is why opening the project on its own shows the
 * same thing — the answer was never copied anywhere to go stale.
 *
 * Gated on a real interaction, because the check walks the folder and macOS asks
 * for permission when it does.
 */
function useMemberChanges(members: { workspace_id: string }[]): {
  changes: Record<string, ScanChanges>;
  recheck: (workspaceId: string) => void;
} {
  const [changes, setChanges] = useState<Record<string, ScanChanges>>({});
  const ids = members.map((m) => m.workspace_id).join(",");

  const check = useCallback((workspaceId: string) => {
    return getWorkspaceScanChanges(workspaceId)
      .then((result) => {
        setChanges((prev) => ({ ...prev, [workspaceId]: result }));
      })
      .catch(() => {
        /* no badge if the check fails — silence is the safe default here */
      });
  }, []);

  useEffect(() => {
    if (!hasUserInteracted() || ids === "") return;
    for (const workspaceId of ids.split(",")) void check(workspaceId);
  }, [ids, check]);

  return { changes, recheck: check };
}

/** One member's "N files changed" badge and the button that acts on it.
 *
 * Rescan is the workspace's own refresh, called by the workspace's own hook —
 * not a group wrapper around it. Everything it writes (scan history, the change
 * journal, the index) is written where it always was, by the code that always
 * wrote it. The hook's state is keyed by workspace id and lives above the
 * component, so a rescan started here is still running, and still visible, when
 * you open that project on its own.
 */
function MemberFreshness({
  workspaceId,
  changes,
  onRescanned,
}: {
  workspaceId: string;
  changes: ScanChanges | undefined;
  onRescanned: () => void;
}) {
  const refresh = useProjectRefresh(workspaceId);
  const badge = memberChangeBadge(changes);
  const wasRunning = useRef(false);

  useEffect(() => {
    if (wasRunning.current && !refresh.running) onRescanned();
    wasRunning.current = refresh.running;
  }, [refresh.running, onRescanned]);

  if (refresh.running) {
    return <span className="grp-badge">Rescanning…</span>;
  }
  // Nothing changed, so nothing is said. An "up to date" badge on every card is
  // a row of green ticks nobody reads and one real warning nobody sees.
  if (!badge) return null;
  return (
    <>
      <span className="grp-badge" title={memberChangeDetail(changes) ?? undefined}>
        {badge}
      </span>
      <button type="button" className="grp-link" onClick={refresh.refresh}>
        Rescan
      </button>
    </>
  );
}

const plural = (count: number, singular: string, many?: string) =>
  count === 1 ? singular : (many ?? `${singular}s`);

interface HomeCard {
  value: number;
  label: string;
  sub?: string;
}

/** What this group is actually made of, in the counts worth a card.
 *
 * These used to be four fixed code-shaped numbers, so a group holding a wiki led
 * with "0 services" and never mentioned its 169 pages. A count of zero is not
 * worth a card; nor is a count the page already carries — "2 projects" was said
 * by the header, the chips and the list below it.
 * ("1 infrastructure components" is a number and a word that disagree.) */
function homeCards(overview: GroupOverviewResponse): HomeCard[] {
  const t = overview.totals;
  const cards: HomeCard[] = [];
  if ((t.pages ?? 0) > 0) {
    cards.push({
      value: t.pages ?? 0,
      label: plural(t.pages ?? 0, "document"),
      sub: (t.decisions ?? 0) > 0 ? `${t.decisions} ${plural(t.decisions, "decision record")}` : undefined,
    });
  }
  if ((t.services ?? 0) > 0) {
    cards.push({ value: t.services, label: plural(t.services, "service") });
  }
  if ((t.infrastructure ?? 0) > 0) {
    cards.push({ value: t.infrastructure, label: plural(t.infrastructure, "infrastructure component") });
  }
  if ((t.environments ?? 0) > 0) {
    cards.push({
      value: t.environments,
      label: plural(t.environments, "environment"),
      sub: overview.environments.join(", ") || undefined,
    });
  }
  return cards.slice(0, 4);
}

function RepositoryList({
  members,
  commitsThisWeek,
  changes,
  onRecheck,
}: {
  members: GroupOverviewResponse["members"];
  commitsThisWeek: number;
  changes: Record<string, ScanChanges>;
  onRecheck: (workspaceId: string) => void;
}) {
  return (
    <section className="grp-section">
      {/* Week activity is a property of the repositories, so it is a badge on the
          repositories — not a card of its own competing with what the group holds. */}
      <SectionHead
        name="Repositories"
        action={
          commitsThisWeek > 0 ? (
            <span className="grp-badge">
              {commitsThisWeek} {plural(commitsThisWeek, "commit")} this week
            </span>
          ) : null
        }
      />
      <ul className="grp-repo-list">
        {members.map((m) => (
          <li key={m.workspace_id} className="grp-repo">
            <div className="grp-repo-top">
              <span className="grp-repo-name">{m.name}</span>
              {m.branch ? <span className="grp-repo-branch">{m.branch}</span> : null}
              {!m.built ? <span className="grp-badge">Not analyzed</span> : null}
              <MemberFreshness
                workspaceId={m.workspace_id}
                changes={changes[m.workspace_id]}
                onRescanned={() => onRecheck(m.workspace_id)}
              />
            </div>
            <p className="grp-repo-desc">{m.description}</p>
            <p className="grp-repo-meta">{repoMeta(m)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function GroupHome({
  overview,
  groupId,
  changes,
  onRecheck,
}: {
  overview: GroupOverviewResponse | null;
  groupId: string;
  changes: Record<string, ScanChanges>;
  onRecheck: (workspaceId: string) => void;
}) {
  if (!overview) return <p className="grp-muted">Loading…</p>;
  if (overview.member_count === 0) {
    return <p className="grp-muted">No repositories in this group yet. Add one above.</p>;
  }
  const cards = homeCards(overview);
  return (
    <div className="grp-stack">
      {cards.length > 0 ? (
        <div className="grp-hero">
          {cards.map((card) => (
            <Metric key={card.label} value={card.value} label={card.label} sub={card.sub} />
          ))}
        </div>
      ) : null}
      <RepositoryList
        members={overview.members}
        commitsThisWeek={overview.totals.commits_last_7_days ?? 0}
        changes={changes}
        onRecheck={onRecheck}
      />
      <GroupMemory groupId={groupId} />
    </div>
  );
}

/** "This handbook was written before <member> last changed."
 *
 * An offer, never an action: rebuilding a handbook costs real time on a model,
 * so the app tells you and you decide. The stale handbook stays in every answer
 * meanwhile — an old summary is worth more than none, as long as nobody is
 * pretending it is current.
 *
 * The same component on Home and in Ask, reading the same endpoint: the group
 * keeps no second copy of this fact, and so the two can never disagree.
 */
function HandbookLag({ groupId, onRegenerated }: { groupId: string; onRegenerated?: () => void }) {
  const [stale, setStale] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const handbook = await getGroupHandbook(groupId);
      setStale(handbook.has_handbook ? (handbook.stale_members ?? []) : []);
    } catch {
      setStale([]);
    }
  }, [groupId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (stale.length === 0 || busy) {
    return busy ? <p className="grp-hint">Rebuilding the group handbook…</p> : null;
  }
  return (
    <p className="grp-lag">
      <span>Built before the latest changes in {stale.join(", ")}.</span>
      <button
        type="button"
        className="grp-link"
        onClick={async () => {
          setBusy(true);
          try {
            await buildGroupHandbook(groupId);
            await load();
            onRegenerated?.();
          } finally {
            setBusy(false);
          }
        }}
      >
        Regenerate?
      </button>
    </p>
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
      {/* One explanation, and the handbook button next to the heading it belongs
          to — the section was two paragraphs saying the same thing on either
          side of a list, with the button stranded at the bottom. */}
      <SectionHead
        name="Notes & handbook"
        sub="What you tell the group here is fed into every group answer."
        action={
          <span className="grp-handbook-row">
            {handbook ? <span className="pm-handbook-badge">In use</span> : null}
            {handbook ? (
              <button type="button" className="grp-link" onClick={() => setShowHandbook((v) => !v)}>
                {showHandbook ? "Hide handbook" : "View handbook"}
              </button>
            ) : null}
            <button
              type="button"
              className="grp-button grp-button-small"
              onClick={regenerate}
              disabled={busy}
              title="A short summary across all member repositories, used as background in every group answer."
            >
              {handbook ? "Regenerate handbook" : "Generate handbook"}
            </button>
          </span>
        }
      />
      <div className="grp-ask-row grp-note-row">
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

      <HandbookLag groupId={groupId} onRegenerated={() => void load()} />
      {handbook && showHandbook ? <pre className="grp-handbook">{handbook}</pre> : null}
    </section>
  );
}

// A group is a *portfolio*, not one merged project. So Intelligence compares
// repos rather than dumping a flat union: which repo has which environment,
// what tech is shared vs unique, and which risk patterns repeat where. A repo
// filter keeps the repo dimension first-class and lets you isolate one repo.
//
// Each section below owns the comparison it draws. They were one function of
// three hundred lines holding four unrelated derivations and a fetch, which is
// four things nobody can read at once and one thing nobody can change safely.

type GroupMember = GroupOverviewResponse["members"][number];

/** Nothing built yet: one invitation, one button per member — instead of five
 *  sections each finding a different way to say the page is empty, and none of
 *  them saying what to do about it. */
function IntelligenceEmptyState({
  members,
  onAnalyze,
}: {
  members: GroupMember[];
  onAnalyze: (workspaceId: string) => void;
}) {
  return (
    <div className="grp-stack">
      <section className="grp-empty-card">
        <p className="grp-empty-title">Build the project maps to see environments, technologies and risks</p>
        <p className="grp-empty-sub">
          Each repository is analyzed on its own; this tab compares what comes back.
        </p>
        <div className="grp-empty-actions">
          {members.map((m) => (
            <button key={m.workspace_id} type="button" className="grp-button" onClick={() => onAnalyze(m.workspace_id)}>
              Analyze {m.name}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

/** One member's FULL single-project Intelligence, in place: the group view is
 *  comparison on top and the same per-project depth on demand. It fetches its
 *  own dashboard, because the thing that shows it is the thing that needs it. */
function MemberDrillDown({
  workspaceId,
  name,
  onBack,
}: {
  workspaceId: string;
  name: string;
  onBack: () => void;
}) {
  const [dashboard, setDashboard] = useState<WorkspaceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getWorkspaceDashboard(workspaceId)
      .then((d) => {
        if (!cancelled) setDashboard(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this project.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  return (
    <div className="grp-stack">
      <div className="grp-drill-bar">
        <button type="button" className="grp-link" onClick={onBack}>
          ← Back to comparison
        </button>
        <span className="grp-drill-title">{name} · full intelligence</span>
      </div>
      {loading ? <p className="grp-muted">Loading…</p> : null}
      {error ? <p className="grp-error">{error}</p> : null}
      {dashboard ? <ProjectIntelligence dashboard={dashboard} /> : null}
    </div>
  );
}

/** Which repositories the comparison below is about.
 *
 * This row used to be the membership chips' identical twin — same pill, same
 * place, one removes a repository from the group and the other hides it from a
 * table. Membership now lives on Home; what is left here is a filter, and it
 * looks like one: a checkbox that shows its own state. */
function RepositoryFilter({
  members,
  active,
  onToggle,
  onAll,
}: {
  members: GroupMember[];
  active: Set<string> | null;
  onToggle: (workspaceId: string) => void;
  onAll: () => void;
}) {
  if (members.length <= 1) return null;
  return (
    <div className="grp-filter" role="group" aria-label="Compare repositories">
      <span className="grp-filter-label">Compare</span>
      {members.map((m) => {
        const on = active === null || active.has(m.workspace_id);
        return (
          <button
            key={m.workspace_id}
            type="button"
            className={`grp-filter-toggle${on ? " is-on" : ""}`}
            onClick={() => onToggle(m.workspace_id)}
            aria-pressed={on}
          >
            <span className="grp-filter-box" aria-hidden="true">{on ? "✓" : ""}</span>
            {m.name}
          </button>
        );
      })}
      {active !== null ? (
        <button type="button" className="grp-link" onClick={onAll}>
          All repositories
        </button>
      ) : null}
    </div>
  );
}

function PerRepositorySection({
  shown,
  onOpen,
}: {
  shown: GroupMember[];
  onOpen: (workspaceId: string) => void;
}) {
  return (
    <section className="grp-section">
      <SectionHead
        name="Per repository"
        sub="Compare across repositories below; open any one for its complete Intelligence."
      />
      <ul className="grp-memberlist">
        {shown.map((m) => (
          <li key={m.workspace_id} className="grp-memberrow">
            <div className="grp-memberrow-main">
              <span className="grp-memberrow-name">{m.name}</span>
              <span className="grp-memberrow-desc">{m.description}</span>
            </div>
            {/* A card that said "Not analyzed yet — build one" and offered no way
                to build one was a sign, not a control. */}
            {m.built ? null : <span className="grp-badge">Not analyzed</span>}
            <button
              type="button"
              className={m.built ? "grp-link" : "grp-button grp-button-small"}
              onClick={() => onOpen(m.workspace_id)}
            >
              {m.built ? "Open full intelligence →" : "Analyze"}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EnvironmentsSection({ shown }: { shown: GroupMember[] }) {
  const envMatrix = useMemo(() => {
    const envs = Array.from(new Set(shown.flatMap((m) => m.environments))).sort();
    return envs.map((env) => ({
      env,
      repos: shown.map((m) => ({ name: m.name, has: m.environments.includes(env) })),
    }));
  }, [shown]);

  return (
    <section className="grp-section">
      <SectionHead name="Environments" sub="Which repository deploys where — a ✓ means it defines that environment." />
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
        <p className="grp-muted">No environments detected in the selected repositories.</p>
      )}
    </section>
  );
}

/** Shared by all, shared by some, or nobody else's — the three things worth
 *  knowing about a technology when you are holding several repositories. */
function technologyGroups(shown: GroupMember[]) {
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
}

function TechnologiesSection({ shown }: { shown: GroupMember[] }) {
  const techGroups = useMemo(() => technologyGroups(shown), [shown]);
  const empty =
    techGroups.common.length === 0 &&
    techGroups.partial.length === 0 &&
    techGroups.uniqueByRepo.size === 0;

  return (
    <section className="grp-section">
      <SectionHead name="Technologies" sub="What every repository shares, and what belongs to only one." />
      {empty ? (
        <p className="grp-muted">No technologies detected in the selected repositories.</p>
      ) : (
        <div className="grp-tech-groups">
          {techGroups.common.length > 0 ? (
            <div className="grp-tech-group">
              <p className="grp-tech-label">Common to all {techGroups.total} repositories</p>
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
  );
}

interface RiskPattern {
  title: string;
  severity: string;
  attention: string;
  total: number;
  repos: Map<string, number>;
  explanation: string;
  recommendation: string | null;
}

/** The same finding in four repositories is one pattern, not four rows. */
function riskPatterns(
  risks: GroupOverviewResponse["risks"],
  shown: GroupMember[],
): RiskPattern[] {
  const shownIds = new Set(shown.map((m) => m.workspace_id));
  const byTitle = new Map<string, Omit<RiskPattern, "title">>();
  for (const r of risks) {
    if (!shownIds.has(r.workspace_id)) continue;
    const entry =
      byTitle.get(r.title) ??
      {
        severity: r.severity,
        attention: r.attention ?? r.severity,
        total: 0,
        repos: new Map<string, number>(),
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
}

function RiskPatternsSection({
  risks,
  shown,
}: {
  risks: GroupOverviewResponse["risks"];
  shown: GroupMember[];
}) {
  const groups = useMemo(() => riskPatterns(risks, shown), [risks, shown]);

  return (
    <section className="grp-section">
      <SectionHead
        name="Risk patterns"
        sub="The same finding across repositories is grouped, so you fix the pattern, not 20 rows. These are leads for a human, not verdicts."
      />
      {groups.length > 0 ? (
        <ul className="grp-riskgroups">
          {groups.map((r) => (
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
              {r.explanation ? <p className="grp-riskgroup-why">{r.explanation}</p> : null}
              {r.recommendation ? (
                <p className="grp-riskgroup-fix">
                  <span className="grp-riskgroup-fix-label">Fix</span> {r.recommendation}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="grp-muted">Nothing risky flagged across the selected repositories.</p>
      )}
    </section>
  );
}

function GroupIntelligence({ overview }: { overview: GroupOverviewResponse | null }) {
  const [active, setActive] = useState<Set<string> | null>(null); // null = all repos
  const [drillId, setDrillId] = useState<string | null>(null);

  const members = useMemo(() => overview?.members ?? [], [overview]);
  const shown = useMemo(
    () => members.filter((m) => active === null || active.has(m.workspace_id)),
    [members, active],
  );

  const toggle = (id: string) =>
    setActive((prev) => {
      const base = prev ?? new Set(members.map((m) => m.workspace_id));
      const next = new Set(base);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      if (next.size === 0 || next.size === members.length) return null; // empty or all → all
      return next;
    });

  if (!overview) return <p className="grp-muted">Loading…</p>;
  if (overview.member_count === 0) {
    return <p className="grp-muted">No repositories in this group yet.</p>;
  }

  if (drillId) {
    const member = members.find((m) => m.workspace_id === drillId);
    return (
      <MemberDrillDown
        workspaceId={drillId}
        name={member?.name ?? "Project"}
        onBack={() => setDrillId(null)}
      />
    );
  }

  // Nothing analyzed yet, so there is nothing to compare — and a comparison of
  // nothing is five empty sections. The sections come back the moment any one
  // member has something in it.
  if (members.every((m) => !m.built)) {
    return <IntelligenceEmptyState members={members} onAnalyze={setDrillId} />;
  }

  return (
    <div className="grp-stack">
      <RepositoryFilter
        members={members}
        active={active}
        onToggle={toggle}
        onAll={() => setActive(null)}
      />
      <PerRepositorySection shown={shown} onOpen={setDrillId} />
      <EnvironmentsSection shown={shown} />
      <TechnologiesSection shown={shown} />
      <RiskPatternsSection risks={overview.risks} shown={shown} />
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

/** One exchange in a group thread: the question as it was asked, beside the
 * answer it produced. Kept together because the composer is empty by the time
 * the answer arrives, and a thumbs-up needs to save the pair. */
type GroupTurn = { question: string; result: GroupAskResponse };

function GroupAsk({
  groupId,
  overview,
  changes,
}: {
  groupId: string;
  overview: GroupOverviewResponse | null;
  changes: Record<string, ScanChanges>;
}) {
  const staleRepos = staleRepositoryNames(overview?.members ?? [], changes);
  const [question, setQuestion] = useState("");
  // The thread, oldest first. A group exists to answer "what did we decide, and
  // where is it implemented?" — which is two questions, and the second one only
  // means something if the first is still on screen.
  const [turns, setTurns] = useState<GroupTurn[]>([]);
  const [asked, setAsked] = useState<string | null>(null);
  const [streamed, setStreamed] = useState("");
  const [loading, setLoading] = useState(false);
  const [think, setThink] = useState(false);
  const [answerMode, setAnswerMode] = useState("safe");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [traceFor, setTraceFor] = useState<string | null>(null);

  const starters = groupStarters(overview);

  async function submit(text?: string) {
    const trimmed = (text ?? question).trim();
    if (!trimmed || loading) return;
    // The composer empties on send, as it does in the single-project Ask — the question
    // is now in the conversation, and leaving it in the box invites sending it twice.
    setQuestion("");
    setAsked(trimmed);
    setLoading(true);
    setError(null);
    setStreamed("");
    try {
      const final = await askProjectGroupStream(groupId, trimmed, {
        think,
        conversationId,
        answerMode: answerMode === "safe" ? null : answerMode,
        onToken: (text) => setStreamed((prev) => prev + text),
      });
      // The question is kept beside its own answer: the composer is empty by now,
      // and a thumbs-up that saved "Q: <nothing>" was saving noise.
      setTurns((prev) => [...prev, { question: trimmed, result: final }]);
      setConversationId(final.conversation_id ?? conversationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The group could not answer.");
    } finally {
      setAsked(null);
      setStreamed("");
      setLoading(false);
    }
  }

  function startNewThread() {
    // A new thread, not an erasure: the old conversation keeps its turns on the
    // backend, and the next question starts a new one. Same as "+ New chat".
    setTurns([]);
    setConversationId(null);
    setStreamed("");
    setAsked(null);
    setError(null);
  }
  const empty = turns.length === 0 && !asked;
  return (
    <div className="grp-ask">
      {/* An invitation is for someone who has not come in yet. After the first
          answer it is a paragraph explaining the thing you are looking at. */}
      {empty ? (
        <p className="grp-hint">
          Ask once and the answer is drawn from every repository in the group, streamed as it's
          written. Each source is labelled with the repository it came from. Nothing leaves this
          computer.
        </p>
      ) : null}

      <HandbookLag groupId={groupId} />

      <div className="grp-ask-toolbar">
        <button
          type="button"
          className="grp-button"
          onClick={startNewThread}
          disabled={loading || empty}
        >
          + New chat
        </button>
        <label className="grp-mode">
          Answer style
          <select
            value={answerMode}
            onChange={(e) => setAnswerMode(e.target.value)}
            disabled={loading}
          >
            <option value="safe">Balanced</option>
            <option value="sources_only">Only from sources</option>
            <option value="deep">Deep dive</option>
            <option value="explain">Explain with sources</option>
          </select>
        </label>
      </div>

      {empty && starters.length > 0 ? (
        <div className="grp-ask-starters">
          {starters.map((q) => (
            <button key={q} type="button" className="grp-ask-starter" onClick={() => void submit(q)}>
              {q}
            </button>
          ))}
        </div>
      ) : null}

      {turns.map((turn, index) => (
        <GroupTurnCard
          key={`${turn.result.conversation_id ?? "t"}-${index}`}
          groupId={groupId}
          question={turn.question}
          result={turn.result}
          staleRepos={staleRepos}
          isLast={index === turns.length - 1 && !asked}
          traceOpen={traceFor === `${index}`}
          onOpenTrace={() => setTraceFor(`${index}`)}
          onCloseTrace={() => setTraceFor(null)}
        />
      ))}

      {asked ? (
        <div className="grp-turn">
          <GroupQuestion text={asked} />
          <div className="grp-answer">
            <p className="grp-answer-eyebrow">Answer · across all repos</p>
            <div className="grp-answer-body">
              <MarkdownAnswer content={streamed} />
              <span className="grp-caret" />
            </div>
          </div>
        </div>
      ) : null}

      <div className="grp-ask-row">
        <input
          className="grp-ask-input"
          type="text"
          value={question}
          placeholder={
            turns.length > 0
              ? "Ask a follow-up — “and where is that configured?”"
              : starters[0]
                ? `e.g. ${starters[0]}`
                : "Ask across every repository in this group"
          }
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
    </div>
  );
}

/** The user's turn, in the same clothes it wears in a single project's Ask: its
 * own block, right-aligned, tinted. It was a grey caption prefixed "You asked ·",
 * which reads as a footnote about a question rather than the question. */
function GroupQuestion({ text }: { text: string }) {
  return (
    <article className="ask-message-row is-user">
      <div className="ask-message-bubble user-bubble">{text}</div>
    </article>
  );
}

/** Which repositories contributed, and how much of each. */
function ContributionBar({ contributions }: { contributions: GroupAskResponse["contributions"] }) {
  if (contributions.length === 0) return null;
  return (
    <div className="grp-contrib-bar">
      {contributions.map((c) => (
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
  );
}

/** Where the answer came from, grouped by the repository it came from — the
 *  label a group answer cannot be read without, in every state. */
function SourcesByRepository({
  sources,
  staleRepos,
}: {
  sources: GroupSource[];
  staleRepos: Set<string>;
}) {
  if (sources.length === 0) return null;
  return (
    <div className="grp-sources">
      <p className="grp-shead">Sources by repository</p>
      {groupSourcesByRepo(sources).map(([repo, items]) => (
        <div className="grp-source-group" key={repo}>
          <p className="grp-source-grouphead">
            {repo}
            <span className="grp-source-groupn">{items.length}</span>
            {/* Not a warning and not a banner: the answer is as good as what was
                indexed, and this says how old that reading is. A person who knows
                they changed those files can weigh it; one who did not, need not. */}
            {staleRepos.has(repo) ? (
              <span className="grp-source-stale">index older than latest file changes</span>
            ) : null}
          </p>
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
  );
}

/** How the answer was reached — the panel, and the button that opens it. */
function AnswerTrace({
  result,
  traceOpen,
  onOpenTrace,
  onCloseTrace,
}: {
  result: GroupAskResponse;
  traceOpen: boolean;
  onOpenTrace: () => void;
  onCloseTrace: () => void;
}) {
  const memoryNote =
    result.memory_used > 0 || result.facts_used > 0
      ? `Used ${result.memory_used} memory note(s) and ${result.facts_used} map fact(s) from across the group.`
      : null;
  const hasTrace = result.memory_used > 0 || result.facts_used > 0 || result.sources.length > 0;

  if (!hasTrace) {
    return memoryNote ? <p className="grp-memory-note">{memoryNote}</p> : null;
  }
  return (
    <>
      <button type="button" className="why-answer-btn" onClick={onOpenTrace}>
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
          onClose={onCloseTrace}
        />
      ) : null}
    </>
  );
}

/** The tail of an older turn, folded into the one line that says what is in it. */
function FoldedTail({ result, onOpen }: { result: GroupAskResponse; onOpen: () => void }) {
  const repos = new Set(result.sources.map((s) => s.workspace_name)).size;
  const label =
    result.sources.length > 0
      ? `${result.sources.length} source${result.sources.length === 1 ? "" : "s"} · ${repos} repo${repos === 1 ? "" : "s"} · helpful?`
      : "How it was reached · helpful?";
  return (
    <button type="button" className="grp-turn-tail" onClick={onOpen}>
      {label}
      <span className="grp-turn-tail-chevron" aria-hidden="true">⌄</span>
    </button>
  );
}

/** One exchange: what was asked/** One exchange: what was asked, what came back, and everything that stands
 * behind it — the contributions, the trace, the sources, the feedback. Its own
 * component because a thread is a list of these, and the composer above is a
 * different job. */
function GroupTurnCard({
  groupId,
  question,
  result,
  staleRepos,
  isLast,
  traceOpen,
  onOpenTrace,
  onCloseTrace,
}: {
  groupId: string;
  question: string;
  result: GroupAskResponse;
  staleRepos: Set<string>;
  isLast: boolean;
  traceOpen: boolean;
  onOpenTrace: () => void;
  onCloseTrace: () => void;
}) {
  // The tail — how it was reached, where it came from, was it any good — is the
  // whole apparatus of trust, and it is three panels per turn. On a thread of
  // four questions that is twelve panels between you and the answer you are
  // reading. So an older turn folds its tail into one line and unfolds on ask.
  const [open, setOpen] = useState(isLast);
  // A new question arrives, so this turn is no longer the one being read: it folds.
  useEffect(() => {
    setOpen(isLast);
  }, [isLast]);
  const warnings = (result.quality_warnings ?? []).filter((w) => w.severity === "high");

  return (
    <div className="grp-turn">
      <GroupQuestion text={question} />
      <div className="grp-answer">
        <p className="grp-answer-eyebrow">Answer · across {result.contributions.length} repositories</p>
        <div className="grp-answer-body">
          <MarkdownAnswer content={result.answer} />
        </div>

        {/* Never inside the fold: a warning you have to ask for is not a warning. */}
        {warnings.length > 0 ? (
          <div className="ask-trust-notice" role="alert">
            {warnings.map((warning, index) => (
              <p key={`${warning.code}-${index}`}>{warning.message}</p>
            ))}
          </div>
        ) : null}

        <ContributionBar contributions={result.contributions} />

        {!open ? (
          <FoldedTail result={result} onOpen={() => setOpen(true)} />
        ) : (
          <>
            <AnswerTrace
              result={result}
              traceOpen={traceOpen}
              onOpenTrace={onOpenTrace}
              onCloseTrace={onCloseTrace}
            />
            <SourcesByRepository sources={result.sources} staleRepos={staleRepos} />
            <AnswerFeedback
              question={question}
              answer={result.answer}
              onSave={(text, k) => addGroupMemory(groupId, text, k)}
            />
            {!isLast ? (
              <button type="button" className="grp-link grp-turn-fold" onClick={() => setOpen(false)}>
                Fold this turn
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
