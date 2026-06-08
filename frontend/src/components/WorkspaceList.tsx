import type { WorkspaceOverviewItem } from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface WorkspaceListProps {
  workspaces: WorkspaceOverviewItem[];
  selectedWorkspaceId: string | null;
  onSelect: (workspaceId: string) => void;
}

export function WorkspaceList({
  workspaces,
  selectedWorkspaceId,
  onSelect,
}: WorkspaceListProps) {
  if (workspaces.length === 0) {
    return (
      <EmptyState
        title="No workspaces yet"
        message="Create one from onboarding or backend API."
        compact
      />
    );
  }

  return (
    <nav className="workspace-list" aria-label="Workspaces">
      {workspaces.map((workspace) => {
        const selected = workspace.workspace_id === selectedWorkspaceId;
        return (
          <button
            className={`workspace-list-item${selected ? " is-selected" : ""}`}
            key={workspace.workspace_id}
            type="button"
            aria-current={selected ? "page" : undefined}
            onClick={() => onSelect(workspace.workspace_id)}
          >
            <span className="workspace-list-heading">
              <strong>{workspace.name}</strong>
              <StatusBadge label={workspace.readiness_status} />
            </span>
            <span className="workspace-path" title={workspace.project_path}>
              {workspace.project_path}
            </span>
            <span className="workspace-list-labels">
              <span>{formatLabel(workspace.assistant_mode)} assistant</span>
              <span>{formatLabel(workspace.quick_start_status)}</span>
            </span>
            <span className="workspace-list-signals">
              <span>{workspace.detected_skills_count} skills</span>
              <span>Index: {formatLabel(workspace.index_status)}</span>
            </span>
            {workspace.next_action_title ? (
              <span className="workspace-next-action">
                <span>Next</span>
                <strong>{workspace.next_action_title}</strong>
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
