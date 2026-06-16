from dataclasses import dataclass

from app.core.domain.assistant_profile import WorkspaceAssistantRecommendation
from app.core.domain.assistant_profile_registry import AssistantProfileRegistry
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceAssistantRecommendationInput:
    workspace_id: str


class WorkspaceAssistantRecommendationNotFoundError(ValueError):
    pass


class GetWorkspaceAssistantRecommendationUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        configuration: dict[str, str],
        profile_registry: AssistantProfileRegistry | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.configuration = configuration
        self.profile_registry = profile_registry or AssistantProfileRegistry()

    def execute(
        self,
        request: GetWorkspaceAssistantRecommendationInput,
    ) -> WorkspaceAssistantRecommendation:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceAssistantRecommendationNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        index_status = self.index_status_repository.get(request.workspace_id)
        profile = self.profile_registry.get_profile(workspace.assistant_mode)
        matched_skills = (
            [skill.name for skill in latest_scan.detected_skills] if latest_scan is not None else []
        )
        is_indexed = index_status is not None and index_status.status == "indexed"

        return WorkspaceAssistantRecommendation(
            workspace_id=workspace.id,
            assistant_mode=workspace.assistant_mode,
            profile=profile,
            matched_skills=matched_skills,
            recommended_actions=self._recommended_actions(
                profile_id=profile.id,
                profile_actions=profile.recommended_actions,
                matched_skills=set(matched_skills),
                has_scan=latest_scan is not None,
                is_indexed=is_indexed,
            ),
            missing_capabilities=self._missing_capabilities(is_indexed),
        )

    def _recommended_actions(
        self,
        profile_id: str,
        profile_actions: list[str],
        matched_skills: set[str],
        has_scan: bool,
        is_indexed: bool,
    ) -> list[str]:
        actions: list[str] = []

        if not has_scan:
            actions.append("scan_project")

        conditional_actions = {
            "scan_project",
            "index_workspace",
            "ask_workspace_question",
            "analyze_terraform",
            "analyze_terragrunt",
            "analyze_cicd",
            "analyze_python",
        }
        actions.extend(action for action in profile_actions if action not in conditional_actions)

        if has_scan:
            if profile_id == "devops" and "Terraform" in matched_skills:
                actions.append("analyze_terraform")
            if profile_id == "devops" and "Terragrunt" in matched_skills:
                actions.append("analyze_terragrunt")
            if profile_id == "devops" and matched_skills.intersection(
                {"GitLab CI", "GitHub Actions"}
            ):
                actions.append("analyze_cicd")
            if profile_id == "developer" and "Python" in matched_skills:
                actions.append("analyze_python")

            if not is_indexed:
                actions.append("index_workspace")
            elif "ask_workspace_question" in profile_actions:
                actions.append("ask_workspace_question")

        return self._deduplicate(actions)

    def _missing_capabilities(self, is_indexed: bool) -> list[str]:
        missing_capabilities: list[str] = []
        if not is_indexed:
            missing_capabilities.append("workspace_ask")
        if self.configuration.get("LLM_PROVIDER") == "fake":
            missing_capabilities.append("real_llm_answers")
        if self.configuration.get("VECTOR_STORE") == "memory":
            missing_capabilities.append("persistent_vector_search")
        return missing_capabilities

    @staticmethod
    def _deduplicate(items: list[str]) -> list[str]:
        return list(dict.fromkeys(items))
