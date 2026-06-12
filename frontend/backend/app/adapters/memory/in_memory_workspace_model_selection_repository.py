from app.core.domain.workspace_model_selection import WorkspaceModelSelection


class InMemoryWorkspaceModelSelectionRepository:
    def __init__(self) -> None:
        self._selections: dict[str, WorkspaceModelSelection] = {}

    def get(self, workspace_id: str) -> WorkspaceModelSelection | None:
        return self._selections.get(workspace_id)

    def save(self, selection: WorkspaceModelSelection) -> WorkspaceModelSelection:
        self._selections[selection.workspace_id] = selection
        return selection
