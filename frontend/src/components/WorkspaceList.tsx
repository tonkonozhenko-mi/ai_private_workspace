import { useState } from "react";

import type { WorkspaceOverviewItem } from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface WorkspaceListProps {
  workspaces: WorkspaceOverviewItem[];
  selectedWorkspaceId: string | null;
  archivingWorkspaceId?: string | null;
  onSelect: (workspaceId: string) => void;
  onArchive: (workspace: WorkspaceOverviewItem) => void;
}

export function WorkspaceList({
  workspaces,
  selectedWorkspaceId,
  archivingWorkspaceId,
  onSelect,
  onArchive,
}: WorkspaceListProps) {
  const [confirmingWorkspaceId, setConfirmingWorkspaceId] = useState<string | null>(
    null,
  );

  if (workspaces.length === 0) {
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
      {workspaces.map((workspace) => {
        const selected = workspace.workspace_id === selectedWorkspaceId;
        const isConfirming = confirmingWorkspaceId === workspace.workspace_id;
        const isArchiving = archivingWorkspaceId === workspace.workspace_id;
        return (
          <div
            className={`workspace-list-card${selected ? " is-selected" : ""}`}
            key={workspace.workspace_id}
          >
            <button
              className="workspace-list-item"
              type="button"
              aria-current={selected ? "page" : undefined}
              onClick={() => {
                setConfirmingWorkspaceId(null);
                onSelect(workspace.workspace_id);
              }}
            >
              <span className="workspace-list-heading">
                <strong>{workspace.name}</strong>
                <StatusBadge label={workspace.readiness_status} />
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
              {workspace.next_action_title ? (
                <span className="workspace-next-action">
                  <span>Next</span>
                  <strong>{formatNextAction(workspace.next_action_title)}</strong>
                </span>
              ) : null}
            </button>
            <div className="workspace-card-actions" aria-label={`${workspace.name} actions`}>
              {isConfirming ? (
                <>
                  <button
                    className="workspace-card-action is-danger"
                    type="button"
                    disabled={isArchiving}
                    onClick={() => onArchive(workspace)}
                  >
                    {isArchiving ? "Archiving..." : "Confirm archive"}
                  </button>
                  <button
                    className="workspace-card-action"
                    type="button"
                    disabled={isArchiving}
                    onClick={() => setConfirmingWorkspaceId(null)}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  className="workspace-card-action"
                  type="button"
                  disabled={isArchiving}
                  onClick={() => setConfirmingWorkspaceId(workspace.workspace_id)}
                >
                  Archive
                </button>
              )}
            </div>
          </div>
        );
      })}
    </nav>
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
