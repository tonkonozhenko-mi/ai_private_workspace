from pydantic import BaseModel, Field

from app.core.domain.onboarding import OnboardingPlan, OnboardingStep


class CreateOnboardingPlanRequest(BaseModel):
    assistant_profile_id: str = Field(..., min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    privacy_mode: str = Field(default="local_only", min_length=1)


class OnboardingStepResponse(BaseModel):
    id: str
    title: str
    description: str
    required: bool
    status: str


class OnboardingPlanResponse(BaseModel):
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str
    recommended_runtime: dict[str, str]
    recommended_models: dict[str, str]
    steps: list[OnboardingStepResponse]
    notes: list[str]


def to_onboarding_step_response(step: OnboardingStep) -> OnboardingStepResponse:
    return OnboardingStepResponse(
        id=step.id,
        title=step.title,
        description=step.description,
        required=step.required,
        status=step.status,
    )


def to_onboarding_plan_response(plan: OnboardingPlan) -> OnboardingPlanResponse:
    return OnboardingPlanResponse(
        assistant_profile_id=plan.assistant_profile_id,
        laptop_profile_id=plan.laptop_profile_id,
        privacy_mode=plan.privacy_mode,
        recommended_runtime=plan.recommended_runtime,
        recommended_models=plan.recommended_models,
        steps=[to_onboarding_step_response(step) for step in plan.steps],
        notes=plan.notes,
    )
