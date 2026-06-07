from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import model_catalog_registry
from app.api.schemas.model_catalog_schemas import (
    ModelCatalogDetailsResponse,
    LocalModelDefinitionResponse,
    ModelCatalogReloadResponse,
    ModelRecommendationResultResponse,
    RecommendModelsRequest,
    to_model_catalog_details_response,
    to_model_catalog_reload_response,
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
from app.core.use_cases.reload_model_catalog import ReloadModelCatalogUseCase


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/catalog", response_model=list[LocalModelDefinitionResponse])
def list_model_catalog(
    model_type: str | None = None,
    provider: str | None = None,
    assistant_profile_id: str | None = None,
) -> list[LocalModelDefinitionResponse]:
    models = ListModelCatalogUseCase(model_catalog_registry).execute(
        ListModelCatalogInput(
            model_type=model_type,
            provider=provider,
            assistant_profile_id=assistant_profile_id,
        )
    )
    return [to_local_model_definition_response(model) for model in models]


@router.get("/catalog/details", response_model=ModelCatalogDetailsResponse)
def get_model_catalog_details(
    model_type: str | None = None,
    provider: str | None = None,
    assistant_profile_id: str | None = None,
) -> ModelCatalogDetailsResponse:
    result = ListModelCatalogUseCase(model_catalog_registry).execute_details(
        ListModelCatalogInput(
            model_type=model_type,
            provider=provider,
            assistant_profile_id=assistant_profile_id,
        )
    )
    return to_model_catalog_details_response(result)


@router.post("/catalog/reload", response_model=ModelCatalogReloadResponse)
def reload_model_catalog() -> ModelCatalogReloadResponse:
    result = ReloadModelCatalogUseCase(model_catalog_registry).execute()
    return to_model_catalog_reload_response(result)


@router.post("/recommend", response_model=ModelRecommendationResultResponse)
def recommend_models(
    request: RecommendModelsRequest,
) -> ModelRecommendationResultResponse:
    try:
        result = RecommendModelsUseCase(
            model_catalog_registry=model_catalog_registry
        ).execute(
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
