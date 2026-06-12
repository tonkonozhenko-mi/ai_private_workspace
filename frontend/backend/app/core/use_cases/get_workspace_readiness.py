from dataclasses import dataclass

from app.core.domain.command import CommandStatus
from app.core.domain.workspace_readiness import (
    WorkspaceCapability,
    WorkspaceReadiness,
)
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceReadinessInput:
    workspace_id: str


class WorkspaceReadinessNotFoundError(ValueError):
    pass


class GetWorkspaceReadinessUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        command_repository: CommandRepositoryPort,
        configuration: dict[str, str],
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.command_repository = command_repository
        self.configuration = configuration

    def execute(self, request: GetWorkspaceReadinessInput) -> WorkspaceReadiness:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceReadinessNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        index_status = self.index_status_repository.get(request.workspace_id)
        commands = self.command_repository.list_by_workspace(request.workspace_id)

        has_scan = latest_scan is not None
        is_indexed = index_status is not None and index_status.status == "indexed"
        index_failed = index_status is not None and index_status.status == "failed"
        command_runner = self.configuration.get("COMMAND_RUNNER", "")
        can_execute_commands = bool(command_runner)
        pending_commands_count = sum(
            command.status == CommandStatus.PENDING.value for command in commands
        )

        return WorkspaceReadiness(
            workspace_id=request.workspace_id,
            status=self._status(
                has_scan=has_scan,
                is_indexed=is_indexed,
                index_failed=index_failed,
            ),
            can_scan=True,
            can_analyze=has_scan,
            can_index=has_scan,
            can_ask=is_indexed,
            can_execute_commands=can_execute_commands,
            capabilities=self._capabilities(
                has_scan=has_scan,
                is_indexed=is_indexed,
                command_runner=command_runner,
            ),
            recommended_next_steps=self._recommended_next_steps(
                has_scan=has_scan,
                is_indexed=is_indexed,
                index_failed=index_failed,
                pending_commands_count=pending_commands_count,
            ),
            configuration=dict(self.configuration),
        )

    @staticmethod
    def _status(
        has_scan: bool,
        is_indexed: bool,
        index_failed: bool,
    ) -> str:
        if index_failed:
            return "degraded"
        if has_scan and is_indexed:
            return "ready"
        return "needs_setup"

    def _capabilities(
        self,
        has_scan: bool,
        is_indexed: bool,
        command_runner: str,
    ) -> list[WorkspaceCapability]:
        local_runner_enabled = command_runner == "local"
        vector_store = self.configuration.get("VECTOR_STORE", "unknown")
        embedding_provider = self.configuration.get("EMBEDDING_PROVIDER", "unknown")
        llm_provider = self.configuration.get("LLM_PROVIDER", "unknown")

        return [
            WorkspaceCapability(
                id="project_scan",
                available=True,
                reason="Workspace project scanning is available.",
            ),
            WorkspaceCapability(
                id="deterministic_analysis",
                available=has_scan,
                reason=(
                    "Deterministic analysis is available from the latest scan."
                    if has_scan
                    else "Run a project scan before deterministic analysis."
                ),
            ),
            WorkspaceCapability(
                id="project_overview_report",
                available=has_scan,
                reason=(
                    "Project overview generation is available from the latest scan."
                    if has_scan
                    else "Run a project scan before generating a project overview."
                ),
            ),
            WorkspaceCapability(
                id="command_suggestions",
                available=has_scan,
                reason=(
                    "Skill-based command suggestions are available."
                    if has_scan
                    else "Run a project scan before generating command suggestions."
                ),
            ),
            WorkspaceCapability(
                id="command_approval",
                available=True,
                reason="Command proposals can be reviewed and approved or rejected.",
            ),
            WorkspaceCapability(
                id="local_command_execution",
                available=local_runner_enabled,
                reason=(
                    "Local command runner is enabled; approval and execution policy "
                    "are still required."
                    if local_runner_enabled
                    else "Local command execution is disabled; the fake runner is configured."
                ),
            ),
            WorkspaceCapability(
                id="workspace_indexing",
                available=has_scan,
                reason=(
                    f"Workspace indexing is available with {embedding_provider} "
                    f"embeddings and {vector_store} vector storage."
                    if has_scan
                    else "Run a project scan before indexing workspace context."
                ),
            ),
            WorkspaceCapability(
                id="workspace_ask",
                available=is_indexed,
                reason=(
                    f"Workspace questions are available with the configured "
                    f"{llm_provider} LLM provider."
                    if is_indexed
                    else "Index workspace context before asking workspace questions."
                ),
            ),
            WorkspaceCapability(
                id="timeline",
                available=True,
                reason="Persistent workspace activity timeline is available.",
            ),
        ]

    def _recommended_next_steps(
        self,
        has_scan: bool,
        is_indexed: bool,
        index_failed: bool,
        pending_commands_count: int,
    ) -> list[str]:
        steps: list[str] = []

        if index_failed:
            steps.append("Review the failed index status and retry workspace indexing.")
        elif not has_scan:
            steps.append("Run project scan.")
        elif not is_indexed:
            steps.append("Index workspace context.")
        else:
            steps.append("Ask a workspace question or generate project overview.")

        if pending_commands_count:
            steps.append("Review pending command approvals.")
        if is_indexed and self.configuration.get("VECTOR_STORE") == "memory":
            steps.append(
                "Reindex workspace context after API restart when using the "
                "in-memory vector store."
            )
        if self.configuration.get("VECTOR_STORE") == "memory":
            steps.append("Use Qdrant for persistent vector search across restarts.")
        if self.configuration.get("LLM_PROVIDER") == "fake":
            steps.append("Enable Ollama LLM provider for real local answers.")

        return steps
