from fastapi import APIRouter, HTTPException, status

from app.api.schemas.onboarding_schemas import (
    CreateOnboardingPlanRequest,
    OnboardingPlanResponse,
    to_onboarding_plan_response,
)
from app.core.use_cases.create_onboarding_plan import (
    CreateOnboardingPlanInput,
    CreateOnboardingPlanUseCase,
    OnboardingPlanValidationError,
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
