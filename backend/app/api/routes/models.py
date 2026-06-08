from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    embedding_provider,
    index_status_repository,
    llm_provider_factory,
    model_catalog_registry,
    model_experiment_repository,
    model_experiment_rating_repository,
    timeline_repository,
    vector_store,
    workspace_repository,
)
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
from app.api.schemas.model_experiment_schemas import (
    CreateModelExperimentPlanRequest,
    ModelExperimentPlanResponse,
    to_model_experiment_plan_response,
)
from app.api.schemas.model_experiment_run_schemas import (
    ModelExperimentRunResponse,
    RunModelExperimentRequest,
    to_model_experiment_run_response,
)
from app.api.schemas.model_experiment_comparison_schemas import (
    ModelExperimentComparisonSummaryResponse,
    to_model_experiment_comparison_summary_response,
)
from app.api.schemas.model_experiment_rating_schemas import (
    ModelExperimentCandidateRatingResponse,
    RateModelExperimentCandidateRequest,
    to_model_experiment_candidate_rating_response,
)
from app.api.schemas.model_switching_schemas import (
    CreateModelSwitchingPlanRequest,
    ModelSwitchingPlanResponse,
    to_model_switching_plan_response,
)
from app.core.use_cases.create_model_switching_plan import (
    CreateModelSwitchingPlanInput,
    CreateModelSwitchingPlanUseCase,
    ModelSwitchingPlanValidationError,
    ModelSwitchingPlanWorkspaceNotFoundError,
)
from app.core.use_cases.create_model_experiment_plan import (
    CreateModelExperimentPlanInput,
    CreateModelExperimentPlanUseCase,
    ModelExperimentCandidateInput,
    ModelExperimentPlanValidationError,
    ModelExperimentPlanWorkspaceNotFoundError,
)
from app.core.use_cases.get_model_experiment_run import (
    GetModelExperimentRunUseCase,
    ModelExperimentRunNotFoundError,
)
from app.core.use_cases.get_model_experiment_comparison import (
    GetModelExperimentComparisonUseCase,
    ModelExperimentComparisonNotFoundError,
)
from app.core.use_cases.list_model_experiment_ratings import (
    ListModelExperimentRatingsUseCase,
    ModelExperimentRatingsNotFoundError,
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
from app.core.use_cases.rate_model_experiment_candidate import (
    ModelExperimentRatingNotFoundError,
    ModelExperimentRatingValidationError,
    RateModelExperimentCandidateInput,
    RateModelExperimentCandidateUseCase,
)
from app.core.use_cases.run_model_experiment import (
    RunModelExperimentIndexRequiredError,
    RunModelExperimentInput,
    RunModelExperimentUseCase,
    RunModelExperimentValidationError,
    RunModelExperimentWorkspaceNotFoundError,
)
from app.core.domain.model_experiment_run import ModelExperimentCandidateRequest


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


@router.post("/switching-plan", response_model=ModelSwitchingPlanResponse)
def create_model_switching_plan(
    request: CreateModelSwitchingPlanRequest,
) -> ModelSwitchingPlanResponse:
    try:
        plan = CreateModelSwitchingPlanUseCase(
            model_catalog_registry=model_catalog_registry,
            workspace_repository=workspace_repository,
            index_status_repository=index_status_repository,
        ).execute(
            CreateModelSwitchingPlanInput(
                model_type=request.model_type,
                current_provider=request.current_provider,
                current_model=request.current_model,
                target_provider=request.target_provider,
                target_model=request.target_model,
                workspace_id=request.workspace_id,
            )
        )
    except ModelSwitchingPlanWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelSwitchingPlanValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_model_switching_plan_response(plan)


@router.post("/experiments/plan", response_model=ModelExperimentPlanResponse)
def create_model_experiment_plan(
    request: CreateModelExperimentPlanRequest,
) -> ModelExperimentPlanResponse:
    try:
        plan = CreateModelExperimentPlanUseCase(
            workspace_repository=workspace_repository,
            index_status_repository=index_status_repository,
            model_catalog_registry=model_catalog_registry,
        ).execute(
            CreateModelExperimentPlanInput(
                workspace_id=request.workspace_id,
                question=request.question,
                experiment_type=request.experiment_type,
                candidates=[
                    ModelExperimentCandidateInput(
                        provider=candidate.provider,
                        model=candidate.model,
                    )
                    for candidate in request.candidates
                ],
            )
        )
    except ModelExperimentPlanWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelExperimentPlanValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_model_experiment_plan_response(plan)


@router.post("/experiments/run", response_model=ModelExperimentRunResponse)
def run_model_experiment(
    request: RunModelExperimentRequest,
) -> ModelExperimentRunResponse:
    try:
        run = RunModelExperimentUseCase(
            workspace_repository=workspace_repository,
            index_status_repository=index_status_repository,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
            llm_provider_factory=llm_provider_factory,
            model_experiment_repository=model_experiment_repository,
            timeline_repository=timeline_repository,
        ).execute(
            RunModelExperimentInput(
                workspace_id=request.workspace_id,
                question=request.question,
                experiment_type=request.experiment_type,
                limit=request.limit,
                candidates=[
                    ModelExperimentCandidateRequest(
                        provider=candidate.provider,
                        model=candidate.model,
                    )
                    for candidate in request.candidates
                ],
            )
        )
    except RunModelExperimentWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        RunModelExperimentValidationError,
        RunModelExperimentIndexRequiredError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_model_experiment_run_response(run)


@router.get(
    "/experiments/{experiment_id}",
    response_model=ModelExperimentRunResponse,
)
def get_model_experiment(experiment_id: str) -> ModelExperimentRunResponse:
    try:
        run = GetModelExperimentRunUseCase(model_experiment_repository).execute(
            experiment_id
        )
    except ModelExperimentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_model_experiment_run_response(run)


@router.get(
    "/experiments/{experiment_id}/comparison",
    response_model=ModelExperimentComparisonSummaryResponse,
)
def get_model_experiment_comparison(
    experiment_id: str,
) -> ModelExperimentComparisonSummaryResponse:
    try:
        summary = GetModelExperimentComparisonUseCase(
            model_experiment_repository,
            model_experiment_rating_repository,
        ).execute(experiment_id)
    except ModelExperimentComparisonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_model_experiment_comparison_summary_response(summary)


@router.post(
    "/experiments/{experiment_id}/ratings",
    response_model=ModelExperimentCandidateRatingResponse,
    status_code=status.HTTP_201_CREATED,
)
def rate_model_experiment_candidate(
    experiment_id: str,
    request: RateModelExperimentCandidateRequest,
) -> ModelExperimentCandidateRatingResponse:
    try:
        rating = RateModelExperimentCandidateUseCase(
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
            timeline_repository=timeline_repository,
        ).execute(
            RateModelExperimentCandidateInput(
                experiment_id=experiment_id,
                provider=request.provider,
                model=request.model,
                rating=request.rating,
                is_preferred=request.is_preferred,
                tags=request.tags,
                comment=request.comment,
            )
        )
    except ModelExperimentRatingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelExperimentRatingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_model_experiment_candidate_rating_response(rating)


@router.get(
    "/experiments/{experiment_id}/ratings",
    response_model=list[ModelExperimentCandidateRatingResponse],
)
def list_model_experiment_ratings(
    experiment_id: str,
) -> list[ModelExperimentCandidateRatingResponse]:
    try:
        ratings = ListModelExperimentRatingsUseCase(
            model_experiment_repository=model_experiment_repository,
            rating_repository=model_experiment_rating_repository,
        ).execute(experiment_id)
    except ModelExperimentRatingsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [
        to_model_experiment_candidate_rating_response(rating)
        for rating in ratings
    ]
