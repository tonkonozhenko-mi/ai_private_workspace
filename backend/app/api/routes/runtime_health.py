from fastapi import APIRouter

from app.api.dependencies import (
    runtime_health_checkers,
    runtime_health_configuration,
)
from app.api.schemas.runtime_health_schemas import (
    RuntimeHealthResponse,
    to_runtime_health_response,
)
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/health", response_model=RuntimeHealthResponse)
def get_runtime_health() -> RuntimeHealthResponse:
    health = GetRuntimeHealthUseCase(
        health_checkers=runtime_health_checkers,
        configuration=runtime_health_configuration,
    ).execute()
    return to_runtime_health_response(health)
