from app.core.domain.project_understanding import ProjectUnderstanding


class InMemoryProjectUnderstandingRepository:
    def __init__(self) -> None:
        self._by_workspace: dict[str, ProjectUnderstanding] = {}

    def save(self, understanding: ProjectUnderstanding) -> ProjectUnderstanding:
        self._by_workspace[understanding.workspace_id] = understanding
        return understanding

    def get(self, workspace_id: str) -> ProjectUnderstanding | None:
        return self._by_workspace.get(workspace_id)
