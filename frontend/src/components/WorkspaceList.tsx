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
  onToggleArchived: () => void;
  onSelect: (workspaceId: string) => void;
  onArchive: (workspace: WorkspaceOverviewItem) => void;
  onRestore: (workspace: WorkspaceOverviewItem) => void;
}

export function WorkspaceList({
  workspaces,
  archivedWorkspaces,
  selectedWorkspaceId,
  showArchived,
  archivingWorkspaceId,
  restoringWorkspaceId,
  onToggleArchived,
  onSelect,
  onArchive,
  onRestore,
}: WorkspaceListProps) {
  const [confirmingWorkspaceId, setConfirmingWorkspaceId] = useState<string | null>(
    null,
  );

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
            confirming={confirmingWorkspaceId === workspace.workspace_id}
            busy={archivingWorkspaceId === workspace.workspace_id}
            actionLabel="Archive"
            confirmingLabel="Confirm archive"
            busyLabel="Archiving..."
            danger
            onSelect={() => {
              setConfirmingWorkspaceId(null);
              onSelect(workspace.workspace_id);
            }}
            onStartConfirm={() => setConfirmingWorkspaceId(workspace.workspace_id)}
            onCancelConfirm={() => setConfirmingWorkspaceId(null)}
            onConfirm={() => onArchive(workspace)}
          />
        ))
      )}

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
                confirming={false}
                busy={restoringWorkspaceId === workspace.workspace_id}
                actionLabel="Restore"
                busyLabel="Restoring..."
                onSelect={() => undefined}
                onStartConfirm={() => onRestore(workspace)}
                onCancelConfirm={() => undefined}
                onConfirm={() => undefined}
              />
            ))
          )}
        </section>
      ) : null}
    </nav>
  );
}

interface WorkspaceCardProps {
  workspace: WorkspaceOverviewItem;
  selected: boolean;
  confirming: boolean;
  busy: boolean;
  archived?: boolean;
  danger?: boolean;
  actionLabel: string;
  confirmingLabel?: string;
  busyLabel: string;
  onSelect: () => void;
  onStartConfirm: () => void;
  onCancelConfirm: () => void;
  onConfirm: () => void;
}

function WorkspaceCard({
  workspace,
  selected,
  confirming,
  busy,
  archived = false,
  danger = false,
  actionLabel,
  confirmingLabel,
  busyLabel,
  onSelect,
  onStartConfirm,
  onCancelConfirm,
  onConfirm,
}: WorkspaceCardProps) {
  return (
    <div
      className={`workspace-list-card${selected ? " is-selected" : ""}${archived ? " is-archived" : ""}`}
    >
      <button
        className="workspace-list-item"
        type="button"
        aria-current={selected ? "page" : undefined}
        disabled={archived}
        onClick={onSelect}
      >
        <span className="workspace-list-heading">
          <strong>{workspace.name}</strong>
          <StatusBadge label={archived ? "archived" : workspace.readiness_status} />
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
        {workspace.next_action_title && !archived ? (
          <span className="workspace-next-action">
            <span>Next</span>
            <strong>{formatNextAction(workspace.next_action_title)}</strong>
          </span>
        ) : null}
      </button>
      <div className="workspace-card-actions" aria-label={`${workspace.name} actions`}>
        {confirming ? (
          <>
            <button
              className={`workspace-card-action${danger ? " is-danger" : ""}`}
              type="button"
              disabled={busy}
              onClick={onConfirm}
            >
              {busy ? busyLabel : confirmingLabel ?? actionLabel}
            </button>
            <button
              className="workspace-card-action"
              type="button"
              disabled={busy}
              onClick={onCancelConfirm}
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            className={`workspace-card-action${danger ? "" : " is-restore"}`}
            type="button"
            disabled={busy}
            onClick={onStartConfirm}
          >
            {busy ? busyLabel : actionLabel}
          </button>
        )}
      </div>
    </div>
  );
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
