from dataclasses import dataclass

from app.core.domain.onboarding import OnboardingPlan
from app.core.domain.onboarding_bootstrap import OnboardingBootstrapResult
from app.core.domain.onboarding_setup import OnboardingSetupCommands
from app.core.domain.runtime_setup_guide import RuntimeSetupGuide
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.create_onboarding_plan import (
    CreateOnboardingPlanInput,
    CreateOnboardingPlanUseCase,
    OnboardingPlanValidationError,
)
from app.core.use_cases.create_workspace import (
    CreateWorkspaceInput,
    CreateWorkspaceUseCase,
)
from app.core.use_cases.get_onboarding_setup_commands import (
    GetOnboardingSetupCommandsInput,
    GetOnboardingSetupCommandsUseCase,
    OnboardingSetupCommandsValidationError,
)
from app.core.use_cases.get_runtime_setup_guide import (
    GetRuntimeSetupGuideInput,
    GetRuntimeSetupGuideUseCase,
    RuntimeSetupGuideValidationError,
)
from app.core.use_cases.get_workspace_readiness import (
    GetWorkspaceReadinessInput,
    GetWorkspaceReadinessUseCase,
)


@dataclass(frozen=True)
class BootstrapWorkspaceInput:
    name: str
    project_path: str
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str = "local_only"
    container_runtime: str = "podman"


class BootstrapWorkspaceValidationError(ValueError):
    pass


class BootstrapWorkspaceUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        command_repository: CommandRepositoryPort,
        readiness_configuration: dict[str, str],
        runtime_setup_guide_use_case: GetRuntimeSetupGuideUseCase,
        timeline_repository: TimelineRepositoryPort | None = None,
        onboarding_plan_use_case: CreateOnboardingPlanUseCase | None = None,
        setup_commands_use_case: GetOnboardingSetupCommandsUseCase | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.command_repository = command_repository
        self.timeline_repository = timeline_repository
        self.readiness_configuration = readiness_configuration
        self.runtime_setup_guide_use_case = runtime_setup_guide_use_case
        self.onboarding_plan_use_case = (
            onboarding_plan_use_case or CreateOnboardingPlanUseCase()
        )
        self.setup_commands_use_case = (
            setup_commands_use_case
            or GetOnboardingSetupCommandsUseCase(self.onboarding_plan_use_case)
        )

    def execute(self, request: BootstrapWorkspaceInput) -> OnboardingBootstrapResult:
        self._validate_workspace_fields(request)
        onboarding_plan = self._create_onboarding_plan(request)
        setup_commands = self._get_setup_commands(request)
        runtime_setup_guide = self._get_runtime_setup_guide(request)

        workspace = CreateWorkspaceUseCase(
            workspace_repository=self.workspace_repository,
            timeline_repository=self.timeline_repository,
        ).execute(
            CreateWorkspaceInput(
                name=request.name,
                project_path=request.project_path,
                assistant_mode=request.assistant_profile_id,
                privacy_mode=request.privacy_mode,
            )
        )
        readiness = GetWorkspaceReadinessUseCase(
            workspace_repository=self.workspace_repository,
            project_scan_repository=self.project_scan_repository,
            index_status_repository=self.index_status_repository,
            command_repository=self.command_repository,
            configuration=self.readiness_configuration,
        ).execute(GetWorkspaceReadinessInput(workspace_id=workspace.id))

        return OnboardingBootstrapResult(
            workspace=workspace,
            onboarding_plan=onboarding_plan,
            setup_commands=setup_commands,
            runtime_setup_guide=runtime_setup_guide,
            readiness=readiness,
            next_steps=[
                "Review runtime setup guide.",
                "Start required local runtimes if needed.",
                "Run project scan.",
                "Review detected skills.",
                "Index workspace context.",
                "Ask first workspace question.",
            ],
        )

    @staticmethod
    def _validate_workspace_fields(request: BootstrapWorkspaceInput) -> None:
        if not request.name.strip():
            raise BootstrapWorkspaceValidationError("Workspace name is required")
        if not request.project_path.strip():
            raise BootstrapWorkspaceValidationError("Project path is required")

    def _create_onboarding_plan(
        self,
        request: BootstrapWorkspaceInput,
    ) -> OnboardingPlan:
        try:
            return self.onboarding_plan_use_case.execute(
                CreateOnboardingPlanInput(
                    assistant_profile_id=request.assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                    privacy_mode=request.privacy_mode,
                )
            )
        except OnboardingPlanValidationError as exc:
            raise BootstrapWorkspaceValidationError(str(exc)) from exc

    def _get_setup_commands(
        self,
        request: BootstrapWorkspaceInput,
    ) -> OnboardingSetupCommands:
        try:
            return self.setup_commands_use_case.execute(
                GetOnboardingSetupCommandsInput(
                    assistant_profile_id=request.assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                    privacy_mode=request.privacy_mode,
                    container_runtime=request.container_runtime,
                )
            )
        except OnboardingSetupCommandsValidationError as exc:
            raise BootstrapWorkspaceValidationError(str(exc)) from exc

    def _get_runtime_setup_guide(
        self,
        request: BootstrapWorkspaceInput,
    ) -> RuntimeSetupGuide:
        try:
            return self.runtime_setup_guide_use_case.execute(
                GetRuntimeSetupGuideInput(
                    assistant_profile_id=request.assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                    privacy_mode=request.privacy_mode,
                    container_runtime=request.container_runtime,
                )
            )
        except RuntimeSetupGuideValidationError as exc:
            raise BootstrapWorkspaceValidationError(str(exc)) from exc
