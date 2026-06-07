from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    command_repository,
    index_status_repository,
    project_scan_repository,
    readiness_configuration,
    runtime_health_checkers,
    runtime_health_configuration,
    timeline_repository,
    workspace_repository,
)
from app.api.schemas.onboarding_bootstrap_schemas import (
    BootstrapWorkspaceRequest,
    OnboardingBootstrapResponse,
    to_onboarding_bootstrap_response,
)
from app.api.schemas.onboarding_schemas import (
    CreateOnboardingPlanRequest,
    OnboardingPlanResponse,
    to_onboarding_plan_response,
)
from app.api.schemas.onboarding_setup_schemas import (
    GetOnboardingSetupCommandsRequest,
    OnboardingSetupCommandsResponse,
    to_onboarding_setup_commands_response,
)
from app.core.use_cases.bootstrap_workspace import (
    BootstrapWorkspaceInput,
    BootstrapWorkspaceUseCase,
    BootstrapWorkspaceValidationError,
)
from app.core.use_cases.create_onboarding_plan import (
    CreateOnboardingPlanInput,
    CreateOnboardingPlanUseCase,
    OnboardingPlanValidationError,
)
from app.core.use_cases.get_onboarding_setup_commands import (
    GetOnboardingSetupCommandsInput,
    GetOnboardingSetupCommandsUseCase,
    OnboardingSetupCommandsValidationError,
)
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.core.use_cases.get_runtime_setup_guide import GetRuntimeSetupGuideUseCase


router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/plan", response_model=OnboardingPlanResponse)
def create_onboarding_plan(
    request: CreateOnboardingPlanRequest,
) -> OnboardingPlanResponse:
    try:
        plan = CreateOnboardingPlanUseCase().execute(
            CreateOnboardingPlanInput(
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                privacy_mode=request.privacy_mode,
            )
        )
    except OnboardingPlanValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_onboarding_plan_response(plan)


@router.post("/setup-commands", response_model=OnboardingSetupCommandsResponse)
def get_onboarding_setup_commands(
    request: GetOnboardingSetupCommandsRequest,
) -> OnboardingSetupCommandsResponse:
    try:
        setup_commands = GetOnboardingSetupCommandsUseCase().execute(
            GetOnboardingSetupCommandsInput(
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                privacy_mode=request.privacy_mode,
                container_runtime=request.container_runtime,
            )
        )
    except OnboardingSetupCommandsValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_onboarding_setup_commands_response(setup_commands)


@router.post(
    "/bootstrap-workspace",
    response_model=OnboardingBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
def bootstrap_workspace(
    request: BootstrapWorkspaceRequest,
) -> OnboardingBootstrapResponse:
    use_case = BootstrapWorkspaceUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        command_repository=command_repository,
        timeline_repository=timeline_repository,
        readiness_configuration=readiness_configuration,
        runtime_setup_guide_use_case=GetRuntimeSetupGuideUseCase(
            runtime_health_use_case=GetRuntimeHealthUseCase(
                health_checkers=runtime_health_checkers,
                configuration=runtime_health_configuration,
            )
        ),
    )

    try:
        result = use_case.execute(
            BootstrapWorkspaceInput(
                name=request.name,
                project_path=request.project_path,
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                privacy_mode=request.privacy_mode,
                container_runtime=request.container_runtime,
            )
        )
    except BootstrapWorkspaceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_onboarding_bootstrap_response(result)
