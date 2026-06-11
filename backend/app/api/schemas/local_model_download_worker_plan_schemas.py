from pydantic import BaseModel

from app.core.domain.local_model_download_worker_plan import (
    LocalModelDownloadWorkerGuardrail,
    LocalModelDownloadWorkerPlan,
    LocalModelDownloadWorkerStep,
)


class LocalModelDownloadWorkerStepResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str


class LocalModelDownloadWorkerGuardrailResponse(BaseModel):
    id: str
    label: str
    detail: str


class LocalModelDownloadWorkerPlanResponse(BaseModel):
    title: str
    summary: str
    status: str
    worker_enabled: bool
    execution_mode: str
    approved_command_pattern: str
    allowed_provider: str
    steps: list[LocalModelDownloadWorkerStepResponse]
    guardrails: list[LocalModelDownloadWorkerGuardrailResponse]
    future_endpoints: list[str]
    user_flow: list[str]


def to_local_model_download_worker_step_response(
    step: LocalModelDownloadWorkerStep,
) -> LocalModelDownloadWorkerStepResponse:
    return LocalModelDownloadWorkerStepResponse(
        id=step.id,
        title=step.title,
        description=step.description,
        status=step.status,
    )


def to_local_model_download_worker_guardrail_response(
    guardrail: LocalModelDownloadWorkerGuardrail,
) -> LocalModelDownloadWorkerGuardrailResponse:
    return LocalModelDownloadWorkerGuardrailResponse(
        id=guardrail.id,
        label=guardrail.label,
        detail=guardrail.detail,
    )


def to_local_model_download_worker_plan_response(
    plan: LocalModelDownloadWorkerPlan,
) -> LocalModelDownloadWorkerPlanResponse:
    return LocalModelDownloadWorkerPlanResponse(
        title=plan.title,
        summary=plan.summary,
        status=plan.status,
        worker_enabled=plan.worker_enabled,
        execution_mode=plan.execution_mode,
        approved_command_pattern=plan.approved_command_pattern,
        allowed_provider=plan.allowed_provider,
        steps=[to_local_model_download_worker_step_response(step) for step in plan.steps],
        guardrails=[
            to_local_model_download_worker_guardrail_response(guardrail)
            for guardrail in plan.guardrails
        ],
        future_endpoints=plan.future_endpoints,
        user_flow=plan.user_flow,
    )
