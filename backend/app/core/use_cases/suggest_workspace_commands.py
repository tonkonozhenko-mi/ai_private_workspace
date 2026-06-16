from dataclasses import dataclass

from app.core.domain.command_risk import classify_command_risk
from app.core.domain.command_suggestion import CommandSuggestion
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.command_errors import CommandWorkspaceNotFoundError

MAX_COMMAND_SUGGESTIONS = 12


@dataclass(frozen=True)
class SuggestWorkspaceCommandsInput:
    workspace_id: str


@dataclass(frozen=True)
class CommandSuggestionTemplate:
    id: str
    title: str
    command: str
    reason: str
    category: str


class SuggestWorkspaceCommandsUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository

    def execute(self, request: SuggestWorkspaceCommandsInput) -> list[CommandSuggestion]:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            return []

        detected_types = {project_file.detected_type for project_file in latest_scan.files}
        templates = self._suggestion_templates(detected_types)
        suggestions: list[CommandSuggestion] = []
        seen_commands: set[str] = set()

        for template in templates:
            if template.command in seen_commands:
                continue
            seen_commands.add(template.command)
            suggestions.append(self._to_suggestion(template, workspace.project_path))

            if len(suggestions) == MAX_COMMAND_SUGGESTIONS:
                break

        return suggestions

    def _suggestion_templates(
        self,
        detected_types: set[str],
    ) -> list[CommandSuggestionTemplate]:
        templates = [
            CommandSuggestionTemplate(
                id="git_status",
                title="Check Git status",
                command="git status",
                reason="Check current repository state before making changes.",
                category="git",
            ),
            CommandSuggestionTemplate(
                id="git_diff",
                title="Review Git diff",
                command="git diff",
                reason="Review local changes in the workspace.",
                category="git",
            ),
            CommandSuggestionTemplate(
                id="git_log_recent",
                title="Review recent commits",
                command="git log --oneline -n 10",
                reason="Inspect recent project history.",
                category="git",
            ),
        ]

        primary_templates = [
            ("terraform", self._terraform_validate()),
            ("terragrunt", self._terragrunt_validate()),
            ("helm", self._helm_lint()),
            ("kubernetes", self._kubectl_kustomize()),
            ("gitlab_ci", self._gitlab_ci_stages()),
            ("github_actions", self._github_actions_uses()),
            ("python", self._python_pytest()),
            ("docker", self._docker_build_dry_run()),
        ]
        secondary_templates = [
            ("terraform", self._terraform_plan()),
            ("terragrunt", self._terragrunt_plan()),
            ("helm", self._helm_template()),
            ("python", self._python_compileall()),
        ]

        templates.extend(
            template
            for detected_type, template in primary_templates
            if detected_type in detected_types
        )
        templates.extend(
            template
            for detected_type, template in secondary_templates
            if detected_type in detected_types
        )
        return templates

    @staticmethod
    def _to_suggestion(
        template: CommandSuggestionTemplate,
        cwd: str,
    ) -> CommandSuggestion:
        return CommandSuggestion(
            id=template.id,
            title=template.title,
            command=template.command,
            cwd=cwd,
            reason=template.reason,
            risk=classify_command_risk(template.command),
            category=template.category,
            requires_approval=True,
        )

    @staticmethod
    def _terraform_validate() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="terraform_validate",
            title="Validate Terraform",
            command="terraform validate",
            reason="Validate Terraform configuration syntax and internal consistency.",
            category="terraform",
        )

    @staticmethod
    def _terraform_plan() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="terraform_plan",
            title="Plan Terraform changes",
            command="terraform plan",
            reason="Preview Terraform infrastructure changes without applying them.",
            category="terraform",
        )

    @staticmethod
    def _terragrunt_validate() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="terragrunt_validate",
            title="Validate Terragrunt",
            command="terragrunt validate",
            reason="Validate Terragrunt-managed Terraform configuration.",
            category="terragrunt",
        )

    @staticmethod
    def _terragrunt_plan() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="terragrunt_plan",
            title="Plan Terragrunt changes",
            command="terragrunt plan",
            reason="Preview Terragrunt-managed infrastructure changes without applying them.",
            category="terragrunt",
        )

    @staticmethod
    def _helm_lint() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="helm_lint",
            title="Lint Helm chart",
            command="helm lint .",
            reason="Check Helm chart structure and templates for common issues.",
            category="helm",
        )

    @staticmethod
    def _helm_template() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="helm_template",
            title="Render Helm templates",
            command="helm template .",
            reason="Render Helm manifests locally without installing them.",
            category="helm",
        )

    @staticmethod
    def _kubectl_kustomize() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="kubectl_kustomize",
            title="Render Kubernetes kustomize output",
            command="kubectl kustomize .",
            reason="Render Kubernetes manifests locally when kustomize configuration exists.",
            category="kubernetes",
        )

    @staticmethod
    def _gitlab_ci_stages() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="gitlab_ci_stages",
            title="Inspect GitLab CI stages",
            command='grep -n "stage:" .gitlab-ci.yml',
            reason="Inspect stage declarations in the GitLab CI pipeline.",
            category="cicd",
        )

    @staticmethod
    def _github_actions_uses() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="github_actions_uses",
            title="Inspect GitHub Actions dependencies",
            command='grep -R "uses:" .github/workflows',
            reason="Inspect actions and reusable workflows referenced by GitHub Actions.",
            category="cicd",
        )

    @staticmethod
    def _python_pytest() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="python_pytest",
            title="Run Python tests",
            command="python -m pytest",
            reason="Run the Python test suite if the project is configured for pytest.",
            category="python",
        )

    @staticmethod
    def _python_compileall() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="python_compileall",
            title="Compile Python files",
            command="python -m compileall .",
            reason="Check Python files for syntax errors without running application code.",
            category="python",
        )

    @staticmethod
    def _docker_build_dry_run() -> CommandSuggestionTemplate:
        return CommandSuggestionTemplate(
            id="docker_build_dry_run",
            title="Check Docker build",
            command="docker build --dry-run .",
            reason="Check Docker build configuration without producing an image when supported.",
            category="docker",
        )
