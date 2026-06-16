from typing import Protocol

from app.core.domain.agent_workflow import AgentWorkflowDraft


class AgentWorkflowRepositoryPort(Protocol):
    def save_workflow(self, workflow: AgentWorkflowDraft) -> AgentWorkflowDraft: ...

    def get_workflow(self, workspace_id: str, workflow_id: str) -> AgentWorkflowDraft | None: ...

    def list_workflows(
        self, workspace_id: str, include_archived: bool = False
    ) -> list[AgentWorkflowDraft]: ...

    def delete_workflow(self, workspace_id: str, workflow_id: str) -> bool: ...
