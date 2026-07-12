import { useState } from "react";

import type { ProjectGroupSummary, WorkspaceOverviewItem } from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface WorkspaceListProps {
  workspaces: WorkspaceOverviewItem[];
  archivedWorkspaces: WorkspaceOverviewItem[];
  selectedWorkspaceId: string | null;
  showArchived: boolean;
  archivingWorkspaceId?: string | null;
  restoringWorkspaceId?: string | null;
  deletingWorkspaceId?: string | null;
  clearingIndexWorkspaceId?: string | null;
  keepingWorkspaceId?: string | null;
  groups?: ProjectGroupSummary[];
  onToggleArchived: () => void;
  onSelect: (workspaceId: string) => void;
  onArchive: (workspace: WorkspaceOverviewItem) => void;
  onRestore: (workspace: WorkspaceOverviewItem) => void;
  onDelete: (workspace: WorkspaceOverviewItem) => void;
  onClearIndex: (workspace: WorkspaceOverviewItem) => void;
  onKeep: (workspace: WorkspaceOverviewItem) => void;
  onAddToGroup?: (workspace: WorkspaceOverviewItem, groupId: string) => void;
  onCreateGroupWith?: (workspace: WorkspaceOverviewItem) => void;
  onDropWorkspaceOnWorkspace?: (sourceWorkspaceId: string, targetWorkspaceId: string) => void;
}

export function WorkspaceList({
  workspaces,
  archivedWorkspaces,
  selectedWorkspaceId,
  showArchived,
  archivingWorkspaceId,
  restoringWorkspaceId,
  deletingWorkspaceId,
  clearingIndexWorkspaceId,
  keepingWorkspaceId,
  groups,
  onToggleArchived,
  onSelect,
  onArchive,
  onRestore,
  onDelete,
  onClearIndex,
  onKeep,
  onAddToGroup,
  onCreateGroupWith,
  onDropWorkspaceOnWorkspace,
}: WorkspaceListProps) {
  if (workspaces.length === 0 && archivedWorkspaces.length === 0) {
    return (
      <EmptyState
        title="No projects yet"
        message="Add a local project from onboarding to start analyzing it."
        compact
      />
    );
  }

  return (
    <nav className="workspace-list" aria-label="Workspaces">
      <div className="active-workspaces-section" aria-label="Active workspaces">
        {workspaces.length === 0 ? (
          <EmptyState
            title="No active projects"
            message="Restore an archived project or add a new local project."
            compact
          />
        ) : (
          <ActiveWorkspaces
            workspaces={workspaces}
            selectedWorkspaceId={selectedWorkspaceId}
            archivingWorkspaceId={archivingWorkspaceId}
            deletingWorkspaceId={deletingWorkspaceId}
            clearingIndexWorkspaceId={clearingIndexWorkspaceId}
            keepingWorkspaceId={keepingWorkspaceId}
            groups={groups}
            onSelect={onSelect}
            onArchive={onArchive}
            onDelete={onDelete}
            onClearIndex={onClearIndex}
            onKeep={onKeep}
            onAddToGroup={onAddToGroup}
            onCreateGroupWith={onCreateGroupWith}
            onDropWorkspaceOnWorkspace={onDropWorkspaceOnWorkspace}
          />
        )}
      </div>

      <div className="archived-workspaces-toggle">
        <button className="text-button" type="button" onClick={onToggleArchived}>
          {showArchived ? "Hide archived" : "Show archived"}
        </button>
        <span>{archivedWorkspaces.length}</span>
      </div>

      {showArchived ? (
        <section className="archived-workspaces-section" aria-label="Archived workspaces">
          <div className="archived-workspaces-heading">
            <span className="section-eyebrow">Archived</span>
            <p>Hidden from the main list. Restore brings a project back without touching local files.</p>
          </div>
          {archivedWorkspaces.length === 0 ? (
            <EmptyState
              title="No archived projects"
              message="Archived workspaces will appear here."
              compact
            />
          ) : (
            archivedWorkspaces.map((workspace) => (
              <WorkspaceCard
                key={workspace.workspace_id}
                workspace={workspace}
                selected={false}
                archived
                restoringBusy={restoringWorkspaceId === workspace.workspace_id}
                deletingBusy={deletingWorkspaceId === workspace.workspace_id}
                onSelect={() => undefined}
                onRestore={() => onRestore(workspace)}
                onDelete={() => onDelete(workspace)}
              />
            ))
          )}
        </section>
      ) : null}
    </nav>
  );
}

const COMPACT_LIMIT = 6;

function ActiveWorkspaces({
  workspaces,
  selectedWorkspaceId,
  archivingWorkspaceId,
  deletingWorkspaceId,
  clearingIndexWorkspaceId,
  keepingWorkspaceId,
  groups,
  onSelect,
  onArchive,
  onDelete,
  onClearIndex,
  onKeep,
  onAddToGroup,
  onCreateGroupWith,
  onDropWorkspaceOnWorkspace,
}: {
  workspaces: WorkspaceOverviewItem[];
  selectedWorkspaceId: string | null;
  archivingWorkspaceId?: string | null;
  deletingWorkspaceId?: string | null;
  clearingIndexWorkspaceId?: string | null;
  keepingWorkspaceId?: string | null;
  groups?: ProjectGroupSummary[];
  onSelect: (workspaceId: string) => void;
  onArchive: (workspace: WorkspaceOverviewItem) => void;
  onDelete: (workspace: WorkspaceOverviewItem) => void;
  onClearIndex: (workspace: WorkspaceOverviewItem) => void;
  onKeep: (workspace: WorkspaceOverviewItem) => void;
  onAddToGroup?: (workspace: WorkspaceOverviewItem, groupId: string) => void;
  onCreateGroupWith?: (workspace: WorkspaceOverviewItem) => void;
  onDropWorkspaceOnWorkspace?: (sourceWorkspaceId: string, targetWorkspaceId: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const selected =
    workspaces.find((item) => item.workspace_id === selectedWorkspaceId) ?? null;
  const others = workspaces.filter(
    (item) => item.workspace_id !== selectedWorkspaceId,
  );
  const hiddenCount = Math.max(0, others.length - COMPACT_LIMIT);
  const visibleOthers = showAll ? others : others.slice(0, COMPACT_LIMIT);

  return (
    <>
      {selected ? (
        <WorkspaceCard
          workspace={selected}
          selected
          archivingBusy={archivingWorkspaceId === selected.workspace_id}
          deletingBusy={deletingWorkspaceId === selected.workspace_id}
          clearingBusy={clearingIndexWorkspaceId === selected.workspace_id}
          keepingBusy={keepingWorkspaceId === selected.workspace_id}
          groups={groups}
          onSelect={() => onSelect(selected.workspace_id)}
          onArchive={() => onArchive(selected)}
          onDelete={() => onDelete(selected)}
          onClearIndex={() => onClearIndex(selected)}
          onKeep={() => onKeep(selected)}
          onAddToGroup={onAddToGroup}
          onCreateGroupWith={onCreateGroupWith}
          onDropWorkspaceOnWorkspace={onDropWorkspaceOnWorkspace}
        />
      ) : null}
      {visibleOthers.length > 0 ? (
        <div className="workspace-compact-list">
          {visibleOthers.map((workspace) => (
            <WorkspaceCompactRow
              key={workspace.workspace_id}
              workspace={workspace}
              onSelect={() => onSelect(workspace.workspace_id)}
              onDropWorkspace={onDropWorkspaceOnWorkspace}
            />
          ))}
        </div>
      ) : null}
      {hiddenCount > 0 ? (
        <button
          className="text-button workspace-show-more"
          type="button"
          onClick={() => setShowAll((value) => !value)}
        >
          {showAll ? "Show fewer" : `Show ${hiddenCount} more`}
        </button>
      ) : null}
    </>
  );
}

const DND_MIME = "application/x-aiworkspace-id";

function WorkspaceCompactRow({
  workspace,
  onSelect,
  onDropWorkspace,
}: {
  workspace: WorkspaceOverviewItem;
  onSelect: () => void;
  onDropWorkspace?: (sourceWorkspaceId: string, targetWorkspaceId: string) => void;
}) {
  const ready = workspace.readiness_status === "ready";
  const isTemporary = workspace.persistence === "temporary";
  const [dropActive, setDropActive] = useState(false);
  return (
    <button
      className={`workspace-compact-row${dropActive ? " is-drop-target" : ""}`}
      type="button"
      onClick={onSelect}
      title="Drag onto another project to group them"
      draggable={Boolean(onDropWorkspace)}
      onDragStart={(e) => {
        e.dataTransfer.setData(DND_MIME, workspace.workspace_id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragOver={(e) => {
        if (!onDropWorkspace) return;
        const src = e.dataTransfer.types.includes(DND_MIME);
        if (src) {
          e.preventDefault();
          setDropActive(true);
        }
      }}
      onDragLeave={() => setDropActive(false)}
      onDrop={(e) => {
        setDropActive(false);
        if (!onDropWorkspace) return;
        const sourceId = e.dataTransfer.getData(DND_MIME);
        if (sourceId && sourceId !== workspace.workspace_id) {
          e.preventDefault();
          onDropWorkspace(sourceId, workspace.workspace_id);
        }
      }}
    >
      <span
        className={`workspace-dot${ready ? " is-ready" : ""}`}
        aria-hidden="true"
      />
      <span className="workspace-compact-name">{workspace.name}</span>
      {isTemporary ? (
        <span className="workspace-compact-temp" title="Forgets when you quit">
          temp
        </span>
      ) : null}
      <span className="workspace-compact-size">
        {formatBytes(workspace.storage_total_bytes ?? 0)}
      </span>
    </button>
  );
}

type CardMode =
  | { kind: "idle" }
  | { kind: "menu" }
  | { kind: "group" }
  | { kind: "confirm"; action: "archive" | "delete" | "clear" };

interface WorkspaceCardProps {
  workspace: WorkspaceOverviewItem;
  selected: boolean;
  archived?: boolean;
  archivingBusy?: boolean;
  restoringBusy?: boolean;
  deletingBusy?: boolean;
  clearingBusy?: boolean;
  keepingBusy?: boolean;
  groups?: ProjectGroupSummary[];
  onSelect: () => void;
  onArchive?: () => void;
  onRestore?: () => void;
  onDelete?: () => void;
  onClearIndex?: () => void;
  onKeep?: () => void;
  onAddToGroup?: (workspace: WorkspaceOverviewItem, groupId: string) => void;
  onCreateGroupWith?: (workspace: WorkspaceOverviewItem) => void;
  onDropWorkspaceOnWorkspace?: (sourceWorkspaceId: string, targetWorkspaceId: string) => void;
}

function WorkspaceCard({
  workspace,
  selected,
  archived = false,
  archivingBusy = false,
  restoringBusy = false,
  deletingBusy = false,
  clearingBusy = false,
  keepingBusy = false,
  groups,
  onSelect,
  onArchive,
  onRestore,
  onDelete,
  onClearIndex,
  onKeep,
  onAddToGroup,
  onCreateGroupWith,
  onDropWorkspaceOnWorkspace,
}: WorkspaceCardProps) {
  const [mode, setMode] = useState<CardMode>({ kind: "idle" });
  const [dropActive, setDropActive] = useState(false);

  const busy = archivingBusy || restoringBusy || deletingBusy || clearingBusy || keepingBusy;
  const canClearIndex = workspace.index_status === "indexed";
  const isTemporary = workspace.persistence === "temporary";
  const canGroup = Boolean(onAddToGroup || onCreateGroupWith);
  const draggable = Boolean(onDropWorkspaceOnWorkspace) && !archived;

  const reset = () => setMode({ kind: "idle" });

  return (
    <div
      className={`workspace-list-card${selected ? " is-selected" : ""}${archived ? " is-archived" : ""}${isTemporary ? " is-temporary" : ""}${dropActive ? " is-drop-target" : ""}`}
      draggable={draggable}
      onDragStart={(e) => {
        if (!draggable) return;
        e.dataTransfer.setData(DND_MIME, workspace.workspace_id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragOver={(e) => {
        if (!onDropWorkspaceOnWorkspace || !e.dataTransfer.types.includes(DND_MIME)) return;
        e.preventDefault();
        setDropActive(true);
      }}
      onDragLeave={() => setDropActive(false)}
      onDrop={(e) => {
        setDropActive(false);
        if (!onDropWorkspaceOnWorkspace) return;
        const sourceId = e.dataTransfer.getData(DND_MIME);
        if (sourceId && sourceId !== workspace.workspace_id) {
          e.preventDefault();
          onDropWorkspaceOnWorkspace(sourceId, workspace.workspace_id);
        }
      }}
    >
      <button
        className="workspace-list-item"
        type="button"
        aria-current={selected ? "page" : undefined}
        disabled={archived}
        onClick={() => {
          reset();
          onSelect();
        }}
      >
        <span className="workspace-list-heading">
          <strong>{workspace.name}</strong>
          {isTemporary ? (
            <span className="workspace-temporary-pill" title="Forgets when you quit">
              Temporary
            </span>
          ) : (
            <StatusBadge label={archived ? "archived" : workspace.readiness_status} />
          )}
        </span>
        <span className="workspace-meta">
          <span className="workspace-meta-row">
            <span className="workspace-meta-key">Path</span>
            <span className="workspace-meta-val" title={workspace.project_path}>
              {workspace.project_path}
            </span>
          </span>
          <span className="workspace-meta-row">
            <span className="workspace-meta-key">Status</span>
            <span className="workspace-meta-val">
              {/* The role is chosen during setup, so a fresh project has none yet —
                  say nothing rather than print a dangling "· mode". */}
              {formatLabel(workspace.quick_start_status)}
              {workspace.assistant_mode
                ? ` · ${formatLabel(workspace.assistant_mode)} mode`
                : ""}
            </span>
          </span>
          {workspace.engine ? (
            <span className="workspace-meta-row">
              <span className="workspace-meta-key">Engine</span>
              <span className="workspace-meta-val">
                <span className={`workspace-engine-pill workspace-engine-pill--${workspace.engine}`}>
                  {workspace.engine === "llamacpp" ? "llama.cpp" : "Ollama"}
                </span>
              </span>
            </span>
          ) : null}
          <span className="workspace-meta-row">
            <span className="workspace-meta-key">Context</span>
            <span className="workspace-meta-val">
              {workspace.detected_skills_count} technologies · {formatContextStatus(workspace.index_status)}
            </span>
          </span>
        </span>
        {isTemporary && !archived ? (
          <span className="workspace-temporary-note">Forgets when you quit</span>
        ) : null}
      </button>

      <div className="workspace-card-actions" aria-label={`${workspace.name} actions`}>
        <StorageSize workspace={workspace} />

        <div className="workspace-card-action-controls">
          {mode.kind === "confirm" ? (
            <ConfirmBar
              action={mode.action}
              busy={busy}
              onConfirm={() => {
                if (mode.action === "archive") onArchive?.();
                else if (mode.action === "delete") onDelete?.();
                else onClearIndex?.();
                reset();
              }}
              onCancel={reset}
            />
          ) : archived ? (
            <>
              <button
                className="workspace-card-action is-restore"
                type="button"
                disabled={busy}
                onClick={() => onRestore?.()}
              >
                {restoringBusy ? "Restoring..." : "Restore"}
              </button>
              <button
                className="workspace-card-action is-danger"
                type="button"
                disabled={busy}
                onClick={() => setMode({ kind: "confirm", action: "delete" })}
              >
                {deletingBusy ? "Deleting..." : "Delete"}
              </button>
            </>
          ) : mode.kind === "group" ? (
            <GroupPicker
              groups={groups ?? []}
              busy={busy}
              onPick={(groupId) => {
                onAddToGroup?.(workspace, groupId);
                reset();
              }}
              onCreate={() => {
                onCreateGroupWith?.(workspace);
                reset();
              }}
              onCancel={() => setMode({ kind: "menu" })}
            />
          ) : mode.kind === "menu" ? (
            <div className="workspace-icon-actions" role="group" aria-label={`${workspace.name} actions`}>
              {isTemporary && onKeep ? (
                <IconAction
                  label={keepingBusy ? "Keeping…" : "Keep forever"}
                  disabled={busy}
                  onClick={() => {
                    onKeep();
                    reset();
                  }}
                  icon={ICON.keep}
                />
              ) : null}
              {canGroup ? (
                <IconAction
                  label="Add to group"
                  disabled={busy}
                  onClick={() => setMode({ kind: "group" })}
                  icon={ICON.group}
                />
              ) : null}
              {canClearIndex ? (
                <IconAction
                  label="Clear index"
                  disabled={busy}
                  onClick={() => setMode({ kind: "confirm", action: "clear" })}
                  icon={ICON.clear}
                />
              ) : null}
              <IconAction
                label="Archive"
                disabled={busy}
                onClick={() => setMode({ kind: "confirm", action: "archive" })}
                icon={ICON.archive}
              />
              <IconAction
                label="Delete"
                danger
                disabled={busy}
                onClick={() => setMode({ kind: "confirm", action: "delete" })}
                icon={ICON.trash}
              />
              <IconAction label="Close" disabled={busy} onClick={reset} icon={ICON.close} />
            </div>
          ) : (
            <button
              className="workspace-card-action workspace-card-manage"
              type="button"
              disabled={busy}
              aria-label={`Manage ${workspace.name}`}
              onClick={() => setMode({ kind: "menu" })}
            >
              {busy ? busyLabel({ archivingBusy, clearingBusy, deletingBusy, keepingBusy }) : "Manage"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const ICON = {
  group: "M4 7h6l2 2h8v9H4V7Z",
  clear: "M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13",
  archive: "M3 5h18v4H3V5Zm2 4v11h14V9M9 13h6",
  trash: "M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v6M14 11v6",
  keep: "M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5L12 3Z",
  close: "M6 6l12 12M18 6 6 18",
  plus: "M12 5v14M5 12h14",
} as const;

function IconAction({
  label,
  icon,
  onClick,
  disabled,
  danger,
}: {
  label: string;
  icon: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      className={`workspace-icon-action${danger ? " is-danger" : ""}`}
      disabled={disabled}
      data-tip={label}
      aria-label={label}
      onClick={onClick}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={icon} />
      </svg>
    </button>
  );
}

function GroupPicker({
  groups,
  busy,
  onPick,
  onCreate,
  onCancel,
}: {
  groups: ProjectGroupSummary[];
  busy: boolean;
  onPick: (groupId: string) => void;
  onCreate: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="workspace-group-picker">
      {groups.length === 0 ? (
        <button type="button" className="workspace-card-action is-primary" disabled={busy} onClick={onCreate}>
          Create a group with this
        </button>
      ) : (
        <>
          <span className="workspace-group-picker-label">Add to…</span>
          {groups.map((group) => (
            <button
              key={group.id}
              type="button"
              className="workspace-card-action"
              disabled={busy}
              onClick={() => onPick(group.id)}
            >
              {group.name}
            </button>
          ))}
          <button type="button" className="workspace-card-action is-primary" disabled={busy} onClick={onCreate}>
            New group…
          </button>
        </>
      )}
      <IconAction label="Back" icon={ICON.close} disabled={busy} onClick={onCancel} />
    </div>
  );
}

function ConfirmBar({
  action,
  busy,
  onConfirm,
  onCancel,
}: {
  action: "archive" | "delete" | "clear";
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const copy = {
    archive: { label: "Archive project?", confirm: "Archive", danger: false },
    delete: { label: "Delete permanently?", confirm: "Delete", danger: true },
    clear: { label: "Clear search index?", confirm: "Clear", danger: false },
  }[action];

  return (
    <div className="workspace-confirm">
      <span className="workspace-confirm-label">{copy.label}</span>
      <span className="workspace-confirm-buttons">
        <button
          className={`workspace-card-action${copy.danger ? " is-danger" : ""}`}
          type="button"
          disabled={busy}
          onClick={onConfirm}
        >
          {copy.confirm}
        </button>
        <button
          className="workspace-card-action"
          type="button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </span>
    </div>
  );
}

function StorageSize({ workspace }: { workspace: WorkspaceOverviewItem }) {
  const total = workspace.storage_total_bytes ?? 0;
  const breakdown = workspace.storage_breakdown ?? {};
  const rows = STORAGE_CATEGORIES.map(([key, label]) => [label, breakdown[key] ?? 0] as const);

  return (
    <span className="workspace-size" tabIndex={0} aria-label={`Storage used: ${formatBytes(total)}`}>
      <span className="workspace-size-value">{formatBytes(total)}</span>
      <span className="workspace-size-tooltip" role="tooltip">
        <span className="workspace-size-tooltip-title">App data for this project</span>
        {rows.map(([label, value]) => (
          <span className="workspace-size-tooltip-row" key={label}>
            <span>{label}</span>
            <span>{formatBytes(value)}</span>
          </span>
        ))}
        <span className="workspace-size-tooltip-row is-total">
          <span>Total</span>
          <span>{formatBytes(total)}</span>
        </span>
        <span className="workspace-size-tooltip-note">
          Your project files on disk are not counted.
        </span>
      </span>
    </span>
  );
}

const STORAGE_CATEGORIES: ReadonlyArray<readonly [string, string]> = [
  ["index", "Search index"],
  ["conversations", "Conversations"],
  ["notes", "Notes & reports"],
  ["scan", "Project scan"],
  ["other", "Other"],
];

function busyLabel(flags: {
  archivingBusy: boolean;
  clearingBusy: boolean;
  deletingBusy: boolean;
  keepingBusy: boolean;
}) {
  if (flags.deletingBusy) return "Deleting...";
  if (flags.clearingBusy) return "Clearing...";
  if (flags.archivingBusy) return "Archiving...";
  if (flags.keepingBusy) return "Keeping...";
  return "Working...";
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / Math.pow(1024, exponent);
  const rounded = value >= 100 || exponent === 0 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${units[exponent]}`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatContextStatus(value: string) {
  return value === "indexed" ? "ready" : formatLabel(value);
}
