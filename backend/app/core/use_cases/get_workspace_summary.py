from dataclasses import dataclass

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.domain.project_scan import ProjectScanResult
from app.core.domain.workspace import Workspace
from app.core.domain.workspace_summary import (
    CommandActivitySummary,
    SuggestedAction,
    WorkspaceSummary,
)
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceSummaryInput:
    workspace_id: str


class WorkspaceSummaryNotFoundError(ValueError):
    pass


class GetWorkspaceSummaryUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        command_repository: CommandRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.command_repository = command_repository

    def execute(self, request: GetWorkspaceSummaryInput) -> WorkspaceSummary:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceSummaryNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        command_activity = self._summarize_command_activity(
            self.command_repository.list_by_workspace(request.workspace_id)
        )
        if latest_scan is None:
            return self._without_scan(workspace, command_activity)

        return self._with_scan(workspace, latest_scan, command_activity)

    def _without_scan(
        self,
        workspace: Workspace,
        command_activity: CommandActivitySummary,
    ) -> WorkspaceSummary:
        return WorkspaceSummary(
            workspace_id=workspace.id,
            name=workspace.name,
            project_path=workspace.project_path,
            assistant_mode=workspace.assistant_mode,
            privacy_mode=workspace.privacy_mode,
            created_at=workspace.created_at.isoformat(),
            has_scan=False,
            detected_skills_count=0,
            detected_skills=[],
            suggested_actions=[
                SuggestedAction(
                    id="scan_project",
                    title="Scan project",
                    description="Scan the workspace project to detect files and skills.",
                    category="setup",
                    priority="high",
                )
            ],
            command_activity=command_activity,
        )

    def _with_scan(
        self,
        workspace: Workspace,
        latest_scan: ProjectScanResult,
        command_activity: CommandActivitySummary,
    ) -> WorkspaceSummary:
        return WorkspaceSummary(
            workspace_id=workspace.id,
            name=workspace.name,
            project_path=workspace.project_path,
            assistant_mode=workspace.assistant_mode,
            privacy_mode=workspace.privacy_mode,
            created_at=workspace.created_at.isoformat(),
            has_scan=True,
            detected_skills_count=len(latest_scan.detected_skills),
            detected_skills=latest_scan.detected_skills,
            suggested_actions=self._suggest_actions(latest_scan),
            command_activity=command_activity,
        )

    def _summarize_command_activity(
        self,
        commands: list[CommandProposal],
    ) -> CommandActivitySummary:
        counts_by_status = {
            CommandStatus.PENDING.value: 0,
            CommandStatus.APPROVED.value: 0,
            CommandStatus.REJECTED.value: 0,
            CommandStatus.EXECUTED.value: 0,
            CommandStatus.FAILED.value: 0,
        }
        for command in commands:
            if command.status in counts_by_status:
                counts_by_status[command.status] += 1

        last_command = max(commands, key=lambda command: command.created_at, default=None)
        return CommandActivitySummary(
            total_commands=len(commands),
            pending_commands=counts_by_status[CommandStatus.PENDING.value],
            approved_commands=counts_by_status[CommandStatus.APPROVED.value],
            rejected_commands=counts_by_status[CommandStatus.REJECTED.value],
            executed_commands=counts_by_status[CommandStatus.EXECUTED.value],
            failed_commands=counts_by_status[CommandStatus.FAILED.value],
            last_command_id=last_command.id if last_command is not None else None,
            last_command_status=last_command.status if last_command is not None else None,
            last_command=last_command.command if last_command is not None else None,
        )

    def _suggest_actions(self, latest_scan: ProjectScanResult) -> list[SuggestedAction]:
        skill_names = {skill.name for skill in latest_scan.detected_skills}
        actions = [
            SuggestedAction(
                id="generate_project_overview",
                title="Generate project overview",
                description="Create a concise overview from the latest deterministic scan.",
                category="summary",
                priority="high",
            )
        ]

        if "Terraform" in skill_names:
            actions.append(
                SuggestedAction(
                    id="analyze_terraform",
                    title="Analyze Terraform",
                    description="Review Terraform structure and infrastructure files.",
                    category="devops",
                    priority="high",
                )
            )

        if "Terragrunt" in skill_names:
            actions.append(
                SuggestedAction(
                    id="analyze_terragrunt",
                    title="Analyze Terragrunt",
                    description="Review Terragrunt configuration and environment structure.",
                    category="devops",
                    priority="high",
                )
            )

        if "GitLab CI" in skill_names or "GitHub Actions" in skill_names:
            actions.append(
                SuggestedAction(
                    id="analyze_cicd",
                    title="Analyze CI/CD",
                    description="Review detected pipeline and automation configuration.",
                    category="devops",
                    priority="high",
                )
            )

        if "Kubernetes" in skill_names or "Helm" in skill_names:
            actions.append(
                SuggestedAction(
                    id="analyze_kubernetes",
                    title="Analyze Kubernetes",
                    description="Review Kubernetes and Helm deployment configuration.",
                    category="devops",
                    priority="medium",
                )
            )

        if "Python" in skill_names:
            actions.append(
                SuggestedAction(
                    id="analyze_python",
                    title="Analyze Python",
                    description="Review Python source files and project structure.",
                    category="developer",
                    priority="medium",
                )
            )

        if "Documentation" in skill_names:
            actions.append(
                SuggestedAction(
                    id="review_documentation",
                    title="Review documentation",
                    description="Review Markdown documentation found in the workspace.",
                    category="documentation",
                    priority="medium",
                )
            )

        if "Docker" in skill_names:
            actions.append(
                SuggestedAction(
                    id="analyze_containers",
                    title="Analyze containers",
                    description="Review Dockerfiles and container configuration.",
                    category="devops",
                    priority="medium",
                )
            )

        return actions[:6]
