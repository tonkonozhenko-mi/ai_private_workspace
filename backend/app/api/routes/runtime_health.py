from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    runtime_health_checkers,
    runtime_health_configuration,
)
from app.api.schemas.runtime_health_schemas import (
    RuntimeHealthResponse,
    to_runtime_health_response,
)
from app.api.schemas.runtime_setup_guide_schemas import (
    GetRuntimeSetupGuideRequest,
    RuntimeSetupGuideResponse,
    to_runtime_setup_guide_response,
)
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.core.use_cases.get_runtime_setup_guide import (
    GetRuntimeSetupGuideInput,
    GetRuntimeSetupGuideUseCase,
    RuntimeSetupGuideValidationError,
)


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/health", response_model=RuntimeHealthResponse)
def get_runtime_health() -> RuntimeHealthResponse:
    health = GetRuntimeHealthUseCase(
        health_checkers=runtime_health_checkers,
        configuration=runtime_health_configuration,
    ).execute()
    return to_runtime_health_response(health)


@router.post("/setup-guide", response_model=RuntimeSetupGuideResponse)
def get_runtime_setup_guide(
    request: GetRuntimeSetupGuideRequest,
) -> RuntimeSetupGuideResponse:
    try:
        guide = GetRuntimeSetupGuideUseCase(
            runtime_health_use_case=GetRuntimeHealthUseCase(
                health_checkers=runtime_health_checkers,
                configuration=runtime_health_configuration,
            )
        ).execute(
            GetRuntimeSetupGuideInput(
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                privacy_mode=request.privacy_mode,
                container_runtime=request.container_runtime,
            )
        )
    except RuntimeSetupGuideValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_runtime_setup_guide_response(guide)
