from fastapi import APIRouter, HTTPException, status

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
