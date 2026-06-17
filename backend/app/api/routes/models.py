import os

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    command_repository,
    command_runner,
    embedding_provider,
    gguf_download_job_runner,
    index_status_repository,
    llama_runtime_manager,
    llm_provider_factory,
    local_model_download_job_repository,
    model_catalog_registry,
    model_experiment_rating_repository,
    model_experiment_repository,
    readiness_configuration,
    timeline_repository,
    vector_store,
    workspace_model_selection_repository,
    workspace_repository,
)
from app.api.schemas.agent_schemas import (
    AgentCapabilityCatalogResponse,
    AgentPlanningPreviewRequest,
    AgentPlanningPreviewResponse,
    to_agent_capability_catalog_response,
    to_agent_planning_preview_response,
)
from app.api.schemas.local_model_download_execution_schemas import (
    LocalModelDownloadExecutionCapabilityResponse,
    LocalModelDownloadExecutionResultResponse,
    to_local_model_download_execution_capability_response,
    to_local_model_download_execution_result_response,
)
from app.api.schemas.local_model_download_job_schemas import (
    LocalModelDownloadJobListResponse,
    LocalModelDownloadJobResponse,
    to_local_model_download_job_list_response,
    to_local_model_download_job_response,
)
from app.api.schemas.local_model_download_worker_plan_schemas import (
    LocalModelDownloadWorkerPlanResponse,
    to_local_model_download_worker_plan_response,
)
from app.api.schemas.local_model_install_draft_schemas import (
    CreateLocalModelInstallDraftRequest,
    LocalModelInstallDraftResponse,
    to_local_model_install_draft_response,
)
from app.api.schemas.local_model_install_guide_schemas import (
    LocalModelInstallGuideResponse,
    to_local_model_install_guide_response,
)
from app.api.schemas.local_model_install_status_schemas import (
    LocalModelInstallStatusResponse,
    to_local_model_install_status_response,
)
from app.api.schemas.model_catalog_schemas import (
    LocalModelDefinitionResponse,
    ModelCatalogDetailsResponse,
    ModelCatalogReloadResponse,
    ModelRecommendationResultResponse,
    RecommendModelsRequest,
    to_local_model_definition_response,
    to_model_catalog_details_response,
    to_model_catalog_reload_response,
    to_model_recommendation_result_response,
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
from app.api.schemas.model_experiment_run_schemas import (
    ModelExperimentRunResponse,
    RunModelExperimentRequest,
    to_model_experiment_run_response,
)
from app.api.schemas.model_experiment_schemas import (
    CreateModelExperimentPlanRequest,
    ModelExperimentPlanResponse,
    to_model_experiment_plan_response,
)
from app.api.schemas.model_switching_schemas import (
    CreateModelSwitchingPlanRequest,
    ModelSwitchingPlanResponse,
    to_model_switching_plan_response,
)
from app.api.schemas.ollama_model_recommendation_schemas import (
    OllamaModelRecommendationGuideResponse,
    to_ollama_model_recommendation_guide_response,
)
from app.config.settings import get_settings
from app.core.domain.agent_capability import (
    build_agent_capability,
    build_agent_capability_catalog,
    build_agent_planning_preview,
)
from app.core.domain.attached_documents import AttachedDocument
from app.core.domain.local_model_download_execution import (
    build_local_model_download_execution_capability,
)
from app.core.domain.local_model_download_worker_plan import (
    build_local_model_download_worker_plan,
)
from app.core.domain.local_model_install_guide import build_local_model_install_guide
from app.core.domain.local_model_install_status import (
    build_local_model_install_status,
    parse_ollama_installed_models,
)
from app.core.domain.model_catalog_registry import build_custom_ollama_model_definition
from app.core.domain.model_experiment_run import ModelExperimentCandidateRequest
from app.core.domain.ollama_model_recommendations import (
    build_ollama_model_recommendation_guide,
)
from app.core.use_cases.command_errors import (
    CommandInvalidStatusError,
    CommandNotFoundError,
    CommandWorkspaceNotFoundError,
)
from app.core.use_cases.create_local_model_install_draft import (
    CreateLocalModelInstallDraftInput,
    CreateLocalModelInstallDraftUseCase,
    LocalModelInstallDraftValidationError,
    LocalModelInstallDraftWorkspaceNotFoundError,
)
from app.core.use_cases.create_model_experiment_plan import (
    CreateModelExperimentPlanInput,
    CreateModelExperimentPlanUseCase,
    ModelExperimentCandidateInput,
    ModelExperimentPlanValidationError,
    ModelExperimentPlanWorkspaceNotFoundError,
)
from app.core.use_cases.create_model_switching_plan import (
    CreateModelSwitchingPlanInput,
    CreateModelSwitchingPlanUseCase,
    ModelSwitchingPlanValidationError,
    ModelSwitchingPlanWorkspaceNotFoundError,
)
from app.core.use_cases.get_model_experiment_comparison import (
    GetModelExperimentComparisonUseCase,
    ModelExperimentComparisonNotFoundError,
)
from app.core.use_cases.get_model_experiment_run import (
    GetModelExperimentRunUseCase,
    ModelExperimentRunNotFoundError,
)
from app.core.use_cases.list_model_catalog import (
    ListModelCatalogInput,
    ListModelCatalogUseCase,
)
from app.core.use_cases.list_model_experiment_ratings import (
    ListModelExperimentRatingsUseCase,
    ModelExperimentRatingsNotFoundError,
)
from app.core.use_cases.rate_model_experiment_candidate import (
    ModelExperimentRatingNotFoundError,
    ModelExperimentRatingValidationError,
    RateModelExperimentCandidateInput,
    RateModelExperimentCandidateUseCase,
)
from app.core.use_cases.recommend_models import (
    ModelRecommendationValidationError,
    RecommendModelsInput,
    RecommendModelsUseCase,
)
from app.core.use_cases.reload_model_catalog import ReloadModelCatalogUseCase
from app.core.use_cases.run_local_model_download import (
    LocalModelDownloadExecutionDisabledError,
    RunLocalModelDownloadInput,
    RunLocalModelDownloadUseCase,
)
from app.core.use_cases.run_local_model_download_job import (
    LocalModelDownloadJobNotCancellableError,
    LocalModelDownloadJobNotFoundError,
    RunLocalModelDownloadJobUseCase,
)
from app.core.use_cases.run_model_experiment import (
    RunModelExperimentIndexRequiredError,
    RunModelExperimentInput,
    RunModelExperimentUseCase,
    RunModelExperimentValidationError,
    RunModelExperimentWorkspaceNotFoundError,
)

router = APIRouter(prefix="/models", tags=["models"])


class GgufCatalogItemResponse(BaseModel):
    id: str
    name: str
    model_type: str
    repo_id: str
    filename: str
    quantization: str
    size_bytes: int
    recommended: bool
    min_ram_gb: int | None = None
    ollama_tag: str | None = None
    download_url: str


@router.get("/gguf-catalog", response_model=list[GgufCatalogItemResponse])
def list_gguf_catalog(model_type: str | None = None) -> list[GgufCatalogItemResponse]:
    """Curated GGUF models for the llama.cpp (Ollama-free) backend."""
    from app.core.domain.gguf_catalog import list_gguf_models

    return [
        GgufCatalogItemResponse(
            id=model.id,
            name=model.name,
            model_type=model.model_type,
            repo_id=model.repo_id,
            filename=model.filename,
            quantization=model.quantization,
            size_bytes=model.size_bytes,
            recommended=model.recommended,
            min_ram_gb=model.min_ram_gb,
            ollama_tag=model.ollama_tag,
            download_url=model.download_url,
        )
        for model in list_gguf_models(model_type)
    ]


class StartGgufDownloadRequest(BaseModel):
    model_id: str | None = None
    repo_id: str | None = None
    filename: str | None = None


class GgufDownloadJobResponse(BaseModel):
    id: str
    model_id: str
    name: str
    model_type: str
    status: str
    downloaded_bytes: int
    total_bytes: int | None = None
    progress_percent: int | None = None
    destination_path: str | None = None
    error: str | None = None


def _to_gguf_job_response(job) -> "GgufDownloadJobResponse":
    return GgufDownloadJobResponse(
        id=job.id,
        model_id=job.model_id,
        name=job.name,
        model_type=job.model_type,
        status=job.status,
        downloaded_bytes=job.downloaded_bytes,
        total_bytes=job.total_bytes,
        progress_percent=job.progress_percent,
        destination_path=job.destination_path,
        error=job.error,
    )


@router.post("/gguf-downloads", response_model=GgufDownloadJobResponse)
def start_gguf_download(request: StartGgufDownloadRequest) -> GgufDownloadJobResponse:
    """Start a background GGUF model download (llama.cpp backend)."""
    from app.core.use_cases.download_gguf_model import GgufModelNotResolvedError, GgufModelRef

    try:
        job = gguf_download_job_runner.start(
            GgufModelRef(
                model_id=request.model_id,
                repo_id=request.repo_id,
                filename=request.filename,
            )
        )
    except GgufModelNotResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _to_gguf_job_response(job)


@router.get("/gguf-downloads/{job_id}", response_model=GgufDownloadJobResponse)
def get_gguf_download(job_id: str) -> GgufDownloadJobResponse:
    job = gguf_download_job_runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download job not found")
    return _to_gguf_job_response(job)


@router.post("/gguf-downloads/{job_id}/cancel", response_model=GgufDownloadJobResponse)
def cancel_gguf_download(job_id: str) -> GgufDownloadJobResponse:
    job = gguf_download_job_runner.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download job not found")
    return _to_gguf_job_response(job)


class LlamaRuntimeStatusResponse(BaseModel):
    binary_available: bool
    binary_path: str | None = None
    models_ready: bool
    running: bool
    llm_url: str | None = None
    embed_url: str | None = None


@router.get("/llama-runtime/status", response_model=LlamaRuntimeStatusResponse)
def llama_runtime_status() -> LlamaRuntimeStatusResponse:
    return LlamaRuntimeStatusResponse(**llama_runtime_manager.status())


@router.post("/llama-runtime/start", response_model=LlamaRuntimeStatusResponse)
def llama_runtime_start() -> LlamaRuntimeStatusResponse:
    from app.adapters.system.llama_runtime_manager import LlamaRuntimeError
    from app.adapters.system.llama_server_process_manager import LlamaServerStartError

    try:
        return LlamaRuntimeStatusResponse(**llama_runtime_manager.start())
    except (LlamaRuntimeError, LlamaServerStartError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.post("/llama-runtime/stop", response_model=LlamaRuntimeStatusResponse)
def llama_runtime_stop() -> LlamaRuntimeStatusResponse:
    return LlamaRuntimeStatusResponse(**llama_runtime_manager.stop())


class SetActiveBackendRequest(BaseModel):
    backend: str  # "ollama" | "llamacpp"


class ActiveBackendResponse(BaseModel):
    active_backend: str


@router.post("/active-backend", response_model=ActiveBackendResponse)
def set_active_backend(request: SetActiveBackendRequest) -> ActiveBackendResponse:
    """Switch the app-wide embedding engine so search uses the chosen backend.

    Indexing should follow this switch so the index and later search use the
    same vectorizer (the setup flow chooses the backend before building context).
    """
    from app.api.dependencies import build_embedding_for_backend

    backend = request.backend.strip().lower()
    if backend not in {"ollama", "llamacpp"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="backend must be 'ollama' or 'llamacpp'",
        )
    if hasattr(embedding_provider, "set_delegate"):
        embedding_provider.set_delegate(build_embedding_for_backend(backend))
    return ActiveBackendResponse(active_backend=backend)


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


@router.get("/local-install-guide", response_model=LocalModelInstallGuideResponse)
def get_local_model_install_guide() -> LocalModelInstallGuideResponse:
    guide = build_local_model_install_guide(model_catalog_registry.list_models())
    return to_local_model_install_guide_response(guide)


@router.get(
    "/ollama-recommendations",
    response_model=OllamaModelRecommendationGuideResponse,
)
def get_ollama_model_recommendations() -> OllamaModelRecommendationGuideResponse:
    guide = build_ollama_model_recommendation_guide(model_catalog_registry.list_models())
    return to_ollama_model_recommendation_guide_response(guide)


@router.get("/local-install-status", response_model=LocalModelInstallStatusResponse)
def get_local_model_install_status() -> LocalModelInstallStatusResponse:
    settings = get_settings()
    runtime_url = settings.ollama_base_url.rstrip("/")
    try:
        response = httpx.get(
            f"{runtime_url}/api/tags",
            timeout=settings.runtime_health_timeout_seconds,
        )
        response.raise_for_status()
        installed_models = parse_ollama_installed_models(response.json())
        _register_discovered_ollama_models(installed_models)
        status_result = build_local_model_install_status(
            catalog_models=model_catalog_registry.list_models(),
            installed_models=installed_models,
            runtime_reachable=True,
            runtime_url=runtime_url,
        )
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError, ValueError) as exc:
        status_result = build_local_model_install_status(
            catalog_models=model_catalog_registry.list_models(),
            installed_models=[],
            runtime_reachable=False,
            runtime_url=runtime_url,
            error=f"Ollama model list is unavailable at {runtime_url}: {exc}",
        )

    return to_local_model_install_status_response(status_result)


class RuntimeMemoryModelInfo(BaseModel):
    name: str
    size_bytes: int
    size_vram_bytes: int


class RuntimeMemoryResponse(BaseModel):
    runtime_reachable: bool
    total_ram_bytes: int
    loaded_bytes: int
    models: list[RuntimeMemoryModelInfo]


def _total_physical_ram_bytes() -> int:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        return 0


@router.get("/runtime-memory", response_model=RuntimeMemoryResponse)
def get_runtime_memory() -> RuntimeMemoryResponse:
    """Report the memory footprint of currently loaded local models.

    Reads Ollama's ``/api/ps`` (running models with their memory size) and the
    machine's total physical RAM. Read-only; it never loads or unloads models.
    """
    settings = get_settings()
    runtime_url = settings.ollama_base_url.rstrip("/")
    models: list[RuntimeMemoryModelInfo] = []
    reachable = False
    try:
        response = httpx.get(
            f"{runtime_url}/api/ps",
            timeout=settings.runtime_health_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        reachable = True
        raw_models = payload.get("models", []) if isinstance(payload, dict) else []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("model") or "model"
            try:
                size = int(item.get("size") or 0)
                vram = int(item.get("size_vram") or 0)
            except (TypeError, ValueError):
                size, vram = 0, 0
            models.append(
                RuntimeMemoryModelInfo(name=str(name), size_bytes=size, size_vram_bytes=vram)
            )
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError, ValueError):
        reachable = False

    return RuntimeMemoryResponse(
        runtime_reachable=reachable,
        total_ram_bytes=_total_physical_ram_bytes(),
        loaded_bytes=sum(model.size_bytes for model in models),
        models=models,
    )


class DeleteInstalledModelRequest(BaseModel):
    name: str = Field(..., min_length=1)


class DeleteInstalledModelResponse(BaseModel):
    deleted: str
    runtime_url: str


@router.post("/local-install/delete", response_model=DeleteInstalledModelResponse)
def delete_installed_model(
    request: DeleteInstalledModelRequest,
) -> DeleteInstalledModelResponse:
    """Remove a locally installed Ollama model to reclaim disk space.

    Gated behind the same model-management execution flag as downloads. This
    only removes the model from the local Ollama runtime; it never touches the
    user's project files.
    """
    settings = get_settings()
    if not settings.model_download_execution_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Model management execution is disabled in this runtime.",
        )
    name = request.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model name is required.",
        )
    runtime_url = settings.ollama_base_url.rstrip("/")
    try:
        response = httpx.request(
            "DELETE",
            f"{runtime_url}/api/delete",
            json={"name": name},
            timeout=settings.runtime_health_timeout_seconds,
        )
        response.raise_for_status()
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not delete {name} via Ollama at {runtime_url}: {exc}",
        ) from exc
    return DeleteInstalledModelResponse(deleted=name, runtime_url=runtime_url)


def _register_discovered_ollama_models(installed_models) -> None:
    for installed in installed_models:
        normalized_name = installed.name.removesuffix(":latest")
        known = next(
            (
                model
                for model in model_catalog_registry.list_models()
                if model.provider == "ollama"
                and model.model_name.removesuffix(":latest").lower() == normalized_name.lower()
            ),
            None,
        )
        model_type = (
            known.model_type
            if known is not None
            else (
                "embedding"
                if "embedding" in installed.capabilities
                and "completion" not in installed.capabilities
                else "llm"
            )
        )
        size = (
            f"{installed.size_bytes / (1024**3):.1f} GB"
            if installed.size_bytes is not None
            else None
        )
        notes = [
            "Discovered from the local Ollama installation.",
            *([f"Parameter size: {installed.parameter_size}."] if installed.parameter_size else []),
            *(
                [f"Quantization: {installed.quantization_level}."]
                if installed.quantization_level
                else []
            ),
        ]
        model_catalog_registry.upsert_user_model(
            build_custom_ollama_model_definition(
                normalized_name,
                model_type,
                display_name=normalized_name,
                capabilities=list(installed.capabilities),
                estimated_size=size,
                context_window=installed.context_length,
                embedding_dimension=installed.embedding_length
                if model_type == "embedding"
                else None,
                notes=notes,
            )
        )


@router.get(
    "/local-download-worker-plan",
    response_model=LocalModelDownloadWorkerPlanResponse,
)
def get_local_model_download_worker_plan() -> LocalModelDownloadWorkerPlanResponse:
    plan = build_local_model_download_worker_plan()
    return to_local_model_download_worker_plan_response(plan)


@router.get(
    "/local-download-execution-capability",
    response_model=LocalModelDownloadExecutionCapabilityResponse,
)
def get_local_model_download_execution_capability() -> (
    LocalModelDownloadExecutionCapabilityResponse
):
    settings = get_settings()
    capability = build_local_model_download_execution_capability(
        execution_enabled=settings.model_download_execution_enabled,
        command_runner=settings.command_runner,
    )
    return to_local_model_download_execution_capability_response(capability)


@router.post(
    "/local-install-drafts/{command_id}/run",
    response_model=LocalModelDownloadExecutionResultResponse,
)
def run_local_model_install_draft(command_id: str) -> LocalModelDownloadExecutionResultResponse:
    settings = get_settings()
    try:
        result = RunLocalModelDownloadUseCase(
            command_repository=command_repository,
            command_runner=command_runner,
            workspace_repository=workspace_repository,
            model_catalog_registry=model_catalog_registry,
            timeline_repository=timeline_repository,
        ).execute(
            RunLocalModelDownloadInput(
                command_id=command_id,
                execution_enabled=settings.model_download_execution_enabled,
                command_runner_name=settings.command_runner,
            )
        )
    except CommandNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (
        LocalModelDownloadExecutionDisabledError,
        CommandInvalidStatusError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CommandWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return to_local_model_download_execution_result_response(result)


@router.post(
    "/local-install-drafts/{command_id}/jobs",
    response_model=LocalModelDownloadJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_local_model_download_job(command_id: str) -> LocalModelDownloadJobResponse:
    settings = get_settings()
    try:
        job = RunLocalModelDownloadJobUseCase(
            command_repository=command_repository,
            command_runner=command_runner,
            workspace_repository=workspace_repository,
            model_catalog_registry=model_catalog_registry,
            job_repository=local_model_download_job_repository,
            timeline_repository=timeline_repository,
            selection_repository=workspace_model_selection_repository,
            configuration=readiness_configuration,
            ollama_base_url=settings.ollama_base_url,
        ).start(
            command_id=command_id,
            execution_enabled=settings.model_download_execution_enabled,
            command_runner_name=settings.command_runner,
        )
    except CommandNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (
        LocalModelDownloadExecutionDisabledError,
        CommandInvalidStatusError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CommandWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return to_local_model_download_job_response(job)


@router.get(
    "/local-download-jobs",
    response_model=LocalModelDownloadJobListResponse,
)
def list_local_model_download_jobs(
    workspace_id: str | None = None,
) -> LocalModelDownloadJobListResponse:
    jobs = RunLocalModelDownloadJobUseCase(
        command_repository=command_repository,
        command_runner=command_runner,
        workspace_repository=workspace_repository,
        model_catalog_registry=model_catalog_registry,
        job_repository=local_model_download_job_repository,
        timeline_repository=timeline_repository,
    ).list(workspace_id=workspace_id)
    return to_local_model_download_job_list_response(jobs)


@router.post(
    "/local-download-jobs/{job_id}/cancel",
    response_model=LocalModelDownloadJobResponse,
)
def cancel_local_model_download_job(job_id: str) -> LocalModelDownloadJobResponse:
    try:
        job = RunLocalModelDownloadJobUseCase(
            command_repository=command_repository,
            command_runner=command_runner,
            workspace_repository=workspace_repository,
            model_catalog_registry=model_catalog_registry,
            job_repository=local_model_download_job_repository,
            timeline_repository=timeline_repository,
        ).request_cancel(job_id)
    except LocalModelDownloadJobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LocalModelDownloadJobNotCancellableError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return to_local_model_download_job_response(job)


@router.get(
    "/local-download-jobs/{job_id}",
    response_model=LocalModelDownloadJobResponse,
)
def get_local_model_download_job(job_id: str) -> LocalModelDownloadJobResponse:
    try:
        job = RunLocalModelDownloadJobUseCase(
            command_repository=command_repository,
            command_runner=command_runner,
            workspace_repository=workspace_repository,
            model_catalog_registry=model_catalog_registry,
            job_repository=local_model_download_job_repository,
            timeline_repository=timeline_repository,
        ).get(job_id)
    except LocalModelDownloadJobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return to_local_model_download_job_response(job)


@router.post(
    "/local-install-drafts",
    response_model=LocalModelInstallDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_local_model_install_draft(
    request: CreateLocalModelInstallDraftRequest,
) -> LocalModelInstallDraftResponse:
    try:
        draft = CreateLocalModelInstallDraftUseCase(
            workspace_repository=workspace_repository,
            command_repository=command_repository,
            model_catalog_registry=model_catalog_registry,
            timeline_repository=timeline_repository,
        ).execute(
            CreateLocalModelInstallDraftInput(
                workspace_id=request.workspace_id,
                provider=request.provider,
                model=request.model,
                model_type=request.model_type,
            )
        )
    except LocalModelInstallDraftWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LocalModelInstallDraftValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return to_local_model_install_draft_response(draft)


@router.get("/agent-capabilities", response_model=AgentCapabilityCatalogResponse)
def get_agent_capabilities() -> AgentCapabilityCatalogResponse:
    catalog = build_agent_capability_catalog(model_catalog_registry.list_models())
    return to_agent_capability_catalog_response(catalog)


@router.post("/agent-planning-preview", response_model=AgentPlanningPreviewResponse)
def create_agent_planning_preview(
    request: AgentPlanningPreviewRequest,
) -> AgentPlanningPreviewResponse:
    selected_capability = None
    if request.provider and request.model:
        for catalog_model in model_catalog_registry.list_models():
            if (
                catalog_model.provider == request.provider
                and catalog_model.model_name == request.model
            ):
                selected_capability = build_agent_capability(catalog_model)
                break

    preview = build_agent_planning_preview(
        goal=request.goal,
        provider=request.provider,
        model=request.model,
        capability=selected_capability,
    )
    return to_agent_planning_preview_response(preview)


@router.post("/recommend", response_model=ModelRecommendationResultResponse)
def recommend_models(
    request: RecommendModelsRequest,
) -> ModelRecommendationResultResponse:
    try:
        result = RecommendModelsUseCase(model_catalog_registry=model_catalog_registry).execute(
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
                attached_documents=[
                    AttachedDocument(name=document.name, content=document.content)
                    for document in request.attached_documents
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
        run = GetModelExperimentRunUseCase(model_experiment_repository).execute(experiment_id)
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

    return [to_model_experiment_candidate_rating_response(rating) for rating in ratings]
