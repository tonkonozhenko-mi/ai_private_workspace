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
        title="No active workspaces yet"
        message="Create one through the backend onboarding flow."
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
            <span className="workspace-path">{workspace.project_path}</span>
            <span className="workspace-list-meta">
              <span>{formatLabel(workspace.quick_start_status)}</span>
              <span>{workspace.detected_skills_count} skills</span>
            </span>
            <span className="workspace-next-action">
              {workspace.next_action_title ?? "Open workspace"}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
