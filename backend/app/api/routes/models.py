from fastapi import APIRouter, HTTPException, status

from app.api.schemas.model_catalog_schemas import (
    LocalModelDefinitionResponse,
    ModelRecommendationResultResponse,
    RecommendModelsRequest,
    to_local_model_definition_response,
    to_model_recommendation_result_response,
)
from app.core.use_cases.list_model_catalog import (
    ListModelCatalogInput,
    ListModelCatalogUseCase,
)
from app.core.use_cases.recommend_models import (
    ModelRecommendationValidationError,
    RecommendModelsInput,
    RecommendModelsUseCase,
)


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/catalog", response_model=list[LocalModelDefinitionResponse])
def list_model_catalog(
    model_type: str | None = None,
    provider: str | None = None,
    assistant_profile_id: str | None = None,
) -> list[LocalModelDefinitionResponse]:
    models = ListModelCatalogUseCase().execute(
        ListModelCatalogInput(
            model_type=model_type,
            provider=provider,
            assistant_profile_id=assistant_profile_id,
        )
    )
    return [to_local_model_definition_response(model) for model in models]


@router.post("/recommend", response_model=ModelRecommendationResultResponse)
def recommend_models(
    request: RecommendModelsRequest,
) -> ModelRecommendationResultResponse:
    try:
        result = RecommendModelsUseCase().execute(
            RecommendModelsInput(
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                task_type=request.task_type,
                model_type=request.model_type,
            )
        )
    except ModelRecommendationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_model_recommendation_result_response(result)
