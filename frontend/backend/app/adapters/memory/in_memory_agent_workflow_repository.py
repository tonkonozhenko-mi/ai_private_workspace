from app.core.domain.agent_workflow import AgentWorkflowDraft


class InMemoryAgentWorkflowRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AgentWorkflowDraft] = {}

    def save_workflow(self, workflow: AgentWorkflowDraft) -> AgentWorkflowDraft:
        self._items[(workflow.workspace_id, workflow.id)] = workflow
        return workflow

    def get_workflow(self, workspace_id: str, workflow_id: str) -> AgentWorkflowDraft | None:
        return self._items.get((workspace_id, workflow_id))

    def list_workflows(self, workspace_id: str, include_archived: bool = False) -> list[AgentWorkflowDraft]:
        workflows = [item for (item_workspace_id, _), item in self._items.items() if item_workspace_id == workspace_id]
        if not include_archived:
            workflows = [item for item in workflows if item.archived_at is None]
        return sorted(workflows, key=lambda item: item.updated_at, reverse=True)

    def delete_workflow(self, workspace_id: str, workflow_id: str) -> bool:
        return self._items.pop((workspace_id, workflow_id), None) is not None
