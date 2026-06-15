import { useState } from "react";

import type { WorkspaceOverviewItem } from "../api/types";
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
  onToggleArchived: () => void;
  onSelect: (workspaceId: string) => void;
  onArchive: (workspace: WorkspaceOverviewItem) => void;
  onRestore: (workspace: WorkspaceOverviewItem) => void;
  onDelete: (workspace: WorkspaceOverviewItem) => void;
  onClearIndex: (workspace: WorkspaceOverviewItem) => void;
  onKeep: (workspace: WorkspaceOverviewItem) => void;
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
  onToggleArchived,
  onSelect,
  onArchive,
  onRestore,
  onDelete,
  onClearIndex,
  onKeep,
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
        <div className="active-workspaces-heading">
          <span className="section-eyebrow">Active</span>
          <p>Projects available for setup, context building, and questions.</p>
        </div>
        {workspaces.length === 0 ? (
          <EmptyState
            title="No active projects"
            message="Restore an archived project or add a new local project."
            compact
          />
        ) : (
          workspaces.map((workspace) => (
            <WorkspaceCard
              key={workspace.workspace_id}
              workspace={workspace}
              selected={workspace.workspace_id === selectedWorkspaceId}
              archivingBusy={archivingWorkspaceId === workspace.workspace_id}
              deletingBusy={deletingWorkspaceId === workspace.workspace_id}
              clearingBusy={clearingIndexWorkspaceId === workspace.workspace_id}
              keepingBusy={keepingWorkspaceId === workspace.workspace_id}
              onSelect={() => onSelect(workspace.workspace_id)}
              onArchive={() => onArchive(workspace)}
              onDelete={() => onDelete(workspace)}
              onClearIndex={() => onClearIndex(workspace)}
              onKeep={() => onKeep(workspace)}
            />
          ))
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

type CardMode =
  | { kind: "idle" }
  | { kind: "menu" }
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
  onSelect: () => void;
  onArchive?: () => void;
  onRestore?: () => void;
  onDelete?: () => void;
  onClearIndex?: () => void;
  onKeep?: () => void;
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
  onSelect,
  onArchive,
  onRestore,
  onDelete,
  onClearIndex,
  onKeep,
}: WorkspaceCardProps) {
  const [mode, setMode] = useState<CardMode>({ kind: "idle" });

  const busy = archivingBusy || restoringBusy || deletingBusy || clearingBusy || keepingBusy;
  const canClearIndex = workspace.index_status === "indexed";
  const isTemporary = workspace.persistence === "temporary";

  const reset = () => setMode({ kind: "idle" });

  return (
    <div
      className={`workspace-list-card${selected ? " is-selected" : ""}${archived ? " is-archived" : ""}${isTemporary ? " is-temporary" : ""}`}
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
        <span className="workspace-path" title={workspace.project_path}>
          {workspace.project_path}
        </span>
        <span className="workspace-list-labels">
          <span>{formatLabel(workspace.assistant_mode)} mode</span>
          <span>{formatLabel(workspace.quick_start_status)}</span>
        </span>
        <span className="workspace-list-signals">
          <span>{workspace.detected_skills_count} technologies found</span>
          <span>{formatContextStatus(workspace.index_status)}</span>
        </span>
        {isTemporary && !archived ? (
          <span className="workspace-temporary-note">Forgets when you quit</span>
        ) : null}
        {workspace.next_action_title && !archived ? (
          <span className="workspace-next-action">
            <span>Next</span>
            <strong>{formatNextAction(workspace.next_action_title)}</strong>
          </span>
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
          ) : mode.kind === "menu" ? (
            <>
              {isTemporary && onKeep ? (
                <button
                  className="workspace-card-action is-keep"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    onKeep();
                    reset();
                  }}
                >
                  {keepingBusy ? "Keeping..." : "Keep forever"}
                </button>
              ) : null}
              {canClearIndex ? (
                <button
                  className="workspace-card-action"
                  type="button"
                  disabled={busy}
                  onClick={() => setMode({ kind: "confirm", action: "clear" })}
                >
                  Clear index
                </button>
              ) : null}
              <button
                className="workspace-card-action"
                type="button"
                disabled={busy}
                onClick={() => setMode({ kind: "confirm", action: "archive" })}
              >
                Archive
              </button>
              <button
                className="workspace-card-action is-danger"
                type="button"
                disabled={busy}
                onClick={() => setMode({ kind: "confirm", action: "delete" })}
              >
                Delete
              </button>
              <button
                className="workspace-card-action"
                type="button"
                disabled={busy}
                onClick={reset}
              >
                Cancel
              </button>
            </>
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
  return value === "indexed" ? "Context ready" : `Context: ${formatLabel(value)}`;
}

function formatNextAction(value: string) {
  return value
    .replace(/Ask using selected LLM/gi, "Ask with chosen AI model")
    .replace(/Ask first workspace question/gi, "Ask a question")
    .replace(/Run project scan/gi, "Scan project")
    .replace(/selected LLM/gi, "chosen AI model")
    .replace(/LLM/gi, "AI model");
}
