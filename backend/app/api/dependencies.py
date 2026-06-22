import logging
from pathlib import Path

from app.adapters.commands.fake_command_runner import FakeCommandRunner
from app.adapters.commands.local_command_runner import LocalCommandRunner
from app.adapters.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from app.adapters.embeddings.switchable_embedding_provider import (
    SwitchableEmbeddingProvider,
)
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.adapters.llm.fake_llm_provider import FakeLLMProvider
from app.adapters.llm.llm_provider_factory import LLMProviderFactory
from app.adapters.memory.in_memory_agent_workflow_repository import InMemoryAgentWorkflowRepository
from app.adapters.memory.in_memory_command_repository import InMemoryCommandRepository
from app.adapters.memory.in_memory_conversation_repository import InMemoryConversationRepository
from app.adapters.memory.in_memory_project_graph_repository import InMemoryProjectGraphRepository
from app.adapters.memory.in_memory_project_watch_repository import (
    InMemoryProjectWatchRepository,
)
from app.adapters.memory.in_memory_project_memory_repository import (
    InMemoryProjectMemoryRepository,
)
from app.adapters.memory.sqlite_project_memory_repository import (
    SQLiteProjectMemoryRepository,
)
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort
from app.adapters.memory.in_memory_project_group_repository import (
    InMemoryProjectGroupRepository,
)
from app.adapters.memory.sqlite_project_group_repository import (
    SQLiteProjectGroupRepository,
)
from app.core.ports.project_group_repository import ProjectGroupRepositoryPort
from app.adapters.memory.in_memory_answer_rating_repository import (
    InMemoryAnswerRatingRepository,
)
from app.adapters.memory.sqlite_answer_rating_repository import (
    SQLiteAnswerRatingRepository,
)
from app.core.ports.answer_rating_repository import AnswerRatingRepositoryPort
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase
from app.adapters.project_graph.sqlite_project_graph_repository import (
    SQLiteProjectGraphRepository,
)
from app.adapters.project_graph.sqlite_project_watch_repository import (
    SQLiteProjectWatchRepository,
)
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_watch_repository import ProjectWatchRepositoryPort
from app.adapters.memory.in_memory_index_status_repository import (
    InMemoryIndexStatusRepository,
)
from app.adapters.memory.in_memory_indexing_rules_repository import (
    InMemoryIndexingRulesRepository,
)
from app.adapters.memory.in_memory_local_model_download_job_repository import (
    InMemoryLocalModelDownloadJobRepository,
)
from app.adapters.memory.in_memory_mcp_repository import InMemoryMCPRepository
from app.adapters.memory.in_memory_model_experiment_rating_repository import (
    InMemoryModelExperimentRatingRepository,
)
from app.adapters.memory.in_memory_model_experiment_repository import (
    InMemoryModelExperimentRepository,
)
from app.adapters.memory.in_memory_project_scan_repository import (
    InMemoryProjectScanRepository,
)
from app.adapters.memory.in_memory_project_understanding_repository import (
    InMemoryProjectUnderstandingRepository,
)
from app.adapters.memory.in_memory_report_repository import InMemoryReportRepository
from app.adapters.memory.in_memory_skill_profile_repository import InMemorySkillProfileRepository
from app.adapters.memory.in_memory_timeline_repository import InMemoryTimelineRepository
from app.adapters.memory.in_memory_workspace_model_selection_repository import (
    InMemoryWorkspaceModelSelectionRepository,
)
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.adapters.memory.in_memory_workspace_storage_gateway import (
    InMemoryWorkspaceStorageGateway,
)
from app.adapters.memory.sqlite_agent_workflow_repository import SQLiteAgentWorkflowRepository
from app.adapters.memory.sqlite_command_repository import SQLiteCommandRepository
from app.adapters.memory.sqlite_conversation_repository import SQLiteConversationRepository
from app.adapters.memory.sqlite_index_status_repository import SQLiteIndexStatusRepository
from app.adapters.memory.sqlite_indexing_rules_repository import SQLiteIndexingRulesRepository
from app.adapters.memory.sqlite_local_model_download_job_repository import (
    SQLiteLocalModelDownloadJobRepository,
)
from app.adapters.memory.sqlite_mcp_repository import SQLiteMCPRepository
from app.adapters.memory.sqlite_model_experiment_rating_repository import (
    SQLiteModelExperimentRatingRepository,
)
from app.adapters.memory.sqlite_model_experiment_repository import (
    SQLiteModelExperimentRepository,
)
from app.adapters.memory.sqlite_project_scan_repository import SQLiteProjectScanRepository
from app.adapters.memory.sqlite_project_understanding_repository import (
    SQLiteProjectUnderstandingRepository,
)
from app.adapters.memory.sqlite_report_repository import SQLiteReportRepository
from app.adapters.memory.sqlite_skill_profile_repository import SQLiteSkillProfileRepository
from app.adapters.memory.sqlite_timeline_repository import SQLiteTimelineRepository
from app.adapters.memory.sqlite_workspace_model_selection_repository import (
    SQLiteWorkspaceModelSelectionRepository,
)
from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.adapters.memory.sqlite_workspace_storage_gateway import (
    SQLiteWorkspaceStorageGateway,
)
from app.adapters.model_catalog.user_model_catalog_loader import UserModelCatalogLoader
from app.adapters.runtime_health.command_runner_health_checker import (
    CommandRunnerHealthChecker,
)
from app.adapters.runtime_health.ollama_runtime_health_checker import (
    OllamaRuntimeHealthChecker,
)
from app.adapters.runtime_health.qdrant_runtime_health_checker import (
    QdrantRuntimeHealthChecker,
)
from app.adapters.system.gguf_download_job_runner import GgufDownloadJobRunner
from app.adapters.system.huggingface_gguf_downloader import HuggingFaceGgufDownloader
from app.adapters.llm.llama_server_reranker import LlamaServerReranker
from app.adapters.system.llama_runtime_manager import LlamaRuntimeManager
from app.adapters.system.local_git_history import LocalGitHistory
from app.adapters.system.runtime_state_store import RuntimeStateStore
from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore
from app.config.settings import get_settings
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.ports.agent_workflow_repository import AgentWorkflowRepositoryPort
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.ports.conversation_repository import ConversationRepositoryPort
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.indexing_rules_repository import IndexingRulesRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import LLMProviderFactoryPort
from app.core.ports.local_model_download_job_repository import (
    LocalModelDownloadJobRepositoryPort,
)
from app.core.ports.mcp_repository import MCPRepositoryPort
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.project_understanding_repository import (
    ProjectUnderstandingRepositoryPort,
)
from app.core.ports.report_repository import ReportRepositoryPort
from app.core.ports.runtime_health_checker import RuntimeHealthCheckerPort
from app.core.ports.skill_profile_repository import SkillProfileRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.ports.workspace_storage_gateway import WorkspaceStorageGatewayPort
from app.core.use_cases.download_gguf_model import DownloadGgufModelUseCase


def build_workspace_repository() -> WorkspaceRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryWorkspaceRepository()
    if repository_type == "sqlite":
        return SQLiteWorkspaceRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_scan_repository() -> ProjectScanRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectScanRepository()
    if repository_type == "sqlite":
        return SQLiteProjectScanRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_report_repository() -> ReportRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryReportRepository()
    if repository_type == "sqlite":
        return SQLiteReportRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_understanding_repository() -> ProjectUnderstandingRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectUnderstandingRepository()
    if repository_type == "sqlite":
        return SQLiteProjectUnderstandingRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_mcp_repository() -> MCPRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryMCPRepository()
    if repository_type == "sqlite":
        return SQLiteMCPRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_agent_workflow_repository() -> AgentWorkflowRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryAgentWorkflowRepository()
    if repository_type == "sqlite":
        return SQLiteAgentWorkflowRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_command_repository() -> CommandRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryCommandRepository()
    if repository_type == "sqlite":
        return SQLiteCommandRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_local_model_download_job_repository() -> LocalModelDownloadJobRepositoryPort:
    settings = get_settings()
    if settings.workspace_repository.lower() == "memory":
        return InMemoryLocalModelDownloadJobRepository()
    return SQLiteLocalModelDownloadJobRepository(settings.workspace_db_path)


def build_index_status_repository() -> IndexStatusRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryIndexStatusRepository()
    if repository_type == "sqlite":
        return SQLiteIndexStatusRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_indexing_rules_repository() -> IndexingRulesRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryIndexingRulesRepository()
    if repository_type == "sqlite":
        return SQLiteIndexingRulesRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_skill_profile_repository() -> SkillProfileRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemorySkillProfileRepository()
    if repository_type == "sqlite":
        return SQLiteSkillProfileRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_timeline_repository() -> TimelineRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryTimelineRepository()
    if repository_type == "sqlite":
        return SQLiteTimelineRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_conversation_repository() -> ConversationRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryConversationRepository()
    if repository_type == "sqlite":
        return SQLiteConversationRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_graph_repository() -> ProjectGraphRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectGraphRepository()
    if repository_type == "sqlite":
        return SQLiteProjectGraphRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_watch_repository() -> ProjectWatchRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectWatchRepository()
    if repository_type == "sqlite":
        return SQLiteProjectWatchRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_memory_repository() -> ProjectMemoryRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectMemoryRepository()
    if repository_type == "sqlite":
        return SQLiteProjectMemoryRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_group_repository() -> ProjectGroupRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectGroupRepository()
    if repository_type == "sqlite":
        return SQLiteProjectGroupRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_answer_rating_repository() -> AnswerRatingRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryAnswerRatingRepository()
    if repository_type == "sqlite":
        return SQLiteAnswerRatingRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_model_experiment_repository() -> ModelExperimentRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryModelExperimentRepository()
    if repository_type == "sqlite":
        return SQLiteModelExperimentRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_model_experiment_rating_repository() -> ModelExperimentRatingRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryModelExperimentRatingRepository()
    if repository_type == "sqlite":
        return SQLiteModelExperimentRatingRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_workspace_model_selection_repository() -> WorkspaceModelSelectionRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryWorkspaceModelSelectionRepository()
    if repository_type == "sqlite":
        return SQLiteWorkspaceModelSelectionRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_workspace_storage_gateway() -> WorkspaceStorageGatewayPort:
    settings = get_settings()
    if settings.workspace_repository.lower() == "memory":
        return InMemoryWorkspaceStorageGateway()
    vector_store_path = (
        settings.vector_store_path if settings.vector_store.lower() == "sqlite" else None
    )
    return SQLiteWorkspaceStorageGateway(
        workspace_db_path=settings.workspace_db_path,
        vector_store_path=vector_store_path,
    )


def build_command_runner() -> CommandRunnerPort:
    settings = get_settings()
    runner_type = settings.command_runner.lower()

    if runner_type == "local":
        return LocalCommandRunner(
            timeout_seconds=settings.command_timeout_seconds,
            output_limit_chars=settings.command_output_limit_chars,
        )
    if runner_type == "fake":
        return FakeCommandRunner()

    raise ValueError(f"Unsupported command runner: {settings.command_runner}")


def build_vector_store() -> VectorStorePort:
    settings = get_settings()
    vector_store_type = settings.vector_store.lower()

    if vector_store_type == "memory":
        return InMemoryVectorStore()
    if vector_store_type == "sqlite":
        return SQLiteVectorStore(settings.vector_store_path)
    if vector_store_type == "qdrant":
        try:
            from app.adapters.vector_store.qdrant_vector_store import QdrantVectorStore
        except ModuleNotFoundError as exc:
            raise ValueError(
                "VECTOR_STORE=qdrant requires the optional 'qdrant-client' package, "
                "which is not installed. The default SQLite vector store needs no "
                "extra packages. To use Qdrant, install it with: "
                "pip install -r requirements-qdrant.txt"
            ) from exc

        return QdrantVectorStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
        )

    raise ValueError(f"Unsupported vector store: {settings.vector_store}")


def build_embedding_provider() -> EmbeddingProviderPort:
    settings = get_settings()
    provider_type = settings.embedding_provider.lower()

    if provider_type == "fake":
        return FakeEmbeddingProvider()
    if provider_type == "ollama":
        from app.adapters.embeddings.ollama_embedding_provider import (
            OllamaEmbeddingProvider,
        )

        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    if provider_type == "llamacpp":
        from app.adapters.embeddings.llama_server_embedding_provider import (
            LlamaServerEmbeddingProvider,
        )

        return LlamaServerEmbeddingProvider(
            base_url=f"http://{settings.LLAMA_SERVER_HOST}:{settings.LLAMA_SERVER_EMBED_PORT}",
            model=settings.ollama_embedding_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


def build_embedding_for_backend(backend: str) -> EmbeddingProviderPort:
    """Build an embedding provider for an explicit backend ('ollama'|'llamacpp')."""
    settings = get_settings()
    name = backend.strip().lower()
    if name == "llamacpp":
        from app.adapters.embeddings.llama_server_embedding_provider import (
            LlamaServerEmbeddingProvider,
        )

        return LlamaServerEmbeddingProvider(
            base_url=f"http://{settings.LLAMA_SERVER_HOST}:{settings.LLAMA_SERVER_EMBED_PORT}",
            model=settings.ollama_embedding_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    from app.adapters.embeddings.ollama_embedding_provider import OllamaEmbeddingProvider

    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )


def build_llm_provider() -> LLMProviderPort:
    settings = get_settings()
    provider_type = settings.llm_provider.lower()

    if provider_type == "fake":
        return FakeLLMProvider()
    if provider_type == "ollama":
        from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider

        return OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_llm_model,
            timeout_seconds=settings.ollama_llm_timeout_seconds,
        )
    if provider_type == "llamacpp":
        from app.adapters.llm.llama_server_llm_provider import LlamaServerLLMProvider

        return LlamaServerLLMProvider(
            base_url=f"http://{settings.LLAMA_SERVER_HOST}:{settings.LLAMA_SERVER_LLM_PORT}",
            model=settings.ollama_llm_model,
            timeout_seconds=settings.ollama_llm_timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def build_llm_provider_factory() -> LLMProviderFactoryPort:
    settings = get_settings()
    return LLMProviderFactory(
        default_provider=settings.llm_provider,
        ollama_base_url=settings.ollama_base_url,
        ollama_default_model=settings.ollama_llm_model,
        ollama_timeout_seconds=settings.ollama_llm_timeout_seconds,
    )


def build_readiness_configuration() -> dict[str, str]:
    settings = get_settings()
    return {
        "VECTOR_STORE": settings.vector_store,
        "VECTOR_STORE_PATH": str(settings.vector_store_path),
        "EMBEDDING_PROVIDER": settings.embedding_provider,
        "LLM_PROVIDER": settings.llm_provider,
        "COMMAND_RUNNER": settings.command_runner,
        "QDRANT_COLLECTION": settings.qdrant_collection,
        "OLLAMA_EMBEDDING_MODEL": settings.ollama_embedding_model,
        "OLLAMA_LLM_MODEL": settings.ollama_llm_model,
    }


def build_runtime_health_configuration() -> dict[str, str]:
    settings = get_settings()
    return {
        "VECTOR_STORE": settings.vector_store,
        "VECTOR_STORE_PATH": str(settings.vector_store_path),
        "EMBEDDING_PROVIDER": settings.embedding_provider,
        "LLM_PROVIDER": settings.llm_provider,
        "COMMAND_RUNNER": settings.command_runner,
        "QDRANT_URL": settings.qdrant_url,
        "OLLAMA_BASE_URL": settings.ollama_base_url,
        "OLLAMA_EMBEDDING_MODEL": settings.ollama_embedding_model,
        "OLLAMA_LLM_MODEL": settings.ollama_llm_model,
    }


def build_runtime_health_checkers() -> list[RuntimeHealthCheckerPort]:
    settings = get_settings()
    timeout_seconds = settings.runtime_health_timeout_seconds
    return [
        QdrantRuntimeHealthChecker(
            vector_store=settings.vector_store,
            qdrant_url=settings.qdrant_url,
            timeout_seconds=timeout_seconds,
        ),
        OllamaRuntimeHealthChecker(
            embedding_provider=settings.embedding_provider,
            llm_provider=settings.llm_provider,
            base_url=settings.ollama_base_url,
            embedding_model=settings.ollama_embedding_model,
            llm_model=settings.ollama_llm_model,
            timeout_seconds=timeout_seconds,
        ),
        CommandRunnerHealthChecker(command_runner=settings.command_runner),
    ]


def build_model_catalog_registry() -> ModelCatalogRegistry:
    settings = get_settings()
    if settings.user_model_catalog_url.strip():
        from app.adapters.model_catalog.remote_model_catalog_loader import (
            RemoteModelCatalogLoader,
        )

        loader = RemoteModelCatalogLoader(
            url=settings.user_model_catalog_url,
            cache_path=str(settings.user_model_catalog_cache_path),
            timeout_seconds=settings.user_model_catalog_fetch_timeout_seconds,
        )
    else:
        loader = UserModelCatalogLoader(settings.user_model_catalog_path)
    registry = ModelCatalogRegistry(loader=loader)
    registry.reload()
    return registry


workspace_repository = build_workspace_repository()
project_scan_repository = build_project_scan_repository()
report_repository = build_report_repository()
project_understanding_repository = build_project_understanding_repository()
agent_workflow_repository = build_agent_workflow_repository()
mcp_repository = build_mcp_repository()
command_repository = build_command_repository()
local_model_download_job_repository = build_local_model_download_job_repository()
index_status_repository = build_index_status_repository()
indexing_rules_repository = build_indexing_rules_repository()
skill_profile_repository = build_skill_profile_repository()
timeline_repository = build_timeline_repository()
conversation_repository = build_conversation_repository()
project_graph_repository = build_project_graph_repository()
project_watch_repository = build_project_watch_repository()
project_memory_repository = build_project_memory_repository()
project_group_repository = build_project_group_repository()
answer_rating_repository = build_answer_rating_repository()
# Shared project-context provider injected into Ask + the Investigator.
project_context_composer = ComposeProjectContextUseCase(
    project_memory_repository, project_graph_repository
)
model_experiment_repository = build_model_experiment_repository()
model_experiment_rating_repository = build_model_experiment_rating_repository()
workspace_model_selection_repository = build_workspace_model_selection_repository()
workspace_storage_gateway = build_workspace_storage_gateway()
file_system = LocalFileSystem()
git_history = LocalGitHistory()
_gguf_download_use_case = DownloadGgufModelUseCase(
    HuggingFaceGgufDownloader(), get_settings().app_data_dir
)
gguf_download_job_runner = GgufDownloadJobRunner(_gguf_download_use_case)
llama_runtime_manager = LlamaRuntimeManager(
    _gguf_download_use_case,
    host=get_settings().LLAMA_SERVER_HOST,
    llm_port=get_settings().LLAMA_SERVER_LLM_PORT,
    embed_port=get_settings().LLAMA_SERVER_EMBED_PORT,
    rerank_port=get_settings().LLAMA_SERVER_RERANK_PORT,
)
command_runner = build_command_runner()
embedding_provider = SwitchableEmbeddingProvider(build_embedding_provider())
runtime_state_store = RuntimeStateStore(
    Path(get_settings().app_data_dir) / "runtime_state.json"
)
llm_provider_factory = build_llm_provider_factory()
vector_store = build_vector_store()
readiness_configuration = build_readiness_configuration()
runtime_health_configuration = build_runtime_health_configuration()
runtime_health_checkers = build_runtime_health_checkers()
model_catalog_registry = build_model_catalog_registry()

from app.api.workspace_job_runner import WorkspaceJobRunner

workspace_job_runner = WorkspaceJobRunner()


def build_active_model_configuration() -> dict[str, str]:
    """Readiness config whose *active* embedding reflects the LIVE provider.

    The static ``readiness_configuration`` reports ``EMBEDDING_PROVIDER`` from the
    environment, which never changes even after the user switches to llama.cpp at
    runtime. For the model-selection dashboard we want the real, currently-active
    embedding engine so the "matches active runtime" check is truthful (and does
    not raise a false mismatch when llama.cpp is in fact active).
    """
    config = dict(readiness_configuration)
    try:
        live_provider = embedding_provider.provider_name
        live_model = getattr(embedding_provider, "model_name", "") or ""
        if live_provider:
            config["EMBEDDING_PROVIDER"] = live_provider
        if live_model:
            config["OLLAMA_EMBEDDING_MODEL"] = live_model
    except Exception:  # noqa: BLE001 - never let status reporting break a request
        pass
    return config


def build_reranker() -> LlamaServerReranker | None:
    """A reranker bound to the live runtime: enabled only when the reranker
    server is actually running (llama.cpp "sharper search"). Returns None
    otherwise, so Ask falls back to plain hybrid retrieval."""
    try:
        status = llama_runtime_manager.status()
    except Exception:  # noqa: BLE001 - never let this break a normal ask
        return None
    if not status.get("rerank_running") or not status.get("rerank_url"):
        return None
    return LlamaServerReranker(
        base_url=status["rerank_url"],
        model=status.get("rerank_model_id", ""),
        enabled=True,
    )


logger = logging.getLogger("ai_private_workspace.startup")

# Structured, non-fatal startup problems. Best-effort startup steps (like
# re-activating the persisted engine) degrade gracefully instead of crashing the
# app — but we now record *why* so a silent runtime mismatch is visible in the
# logs and via get_startup_diagnostics(), rather than being swallowed.
_startup_diagnostics: list[dict[str, str]] = []


def _record_startup_diagnostic(component: str, message: str) -> None:
    _startup_diagnostics.append({"component": component, "message": message})
    logger.warning("startup diagnostic [%s]: %s", component, message)


def get_startup_diagnostics() -> list[dict[str, str]]:
    """Non-fatal problems recorded during startup (e.g. the persisted llama.cpp
    engine could not be re-activated and the app fell back to Ollama). Empty when
    startup was clean. Surfaceable in a status/health response."""
    return list(_startup_diagnostics)


def restore_active_backend() -> None:
    """Re-activate the persisted engine on startup so index and search agree.

    If the user last activated llama.cpp, bring the engine up and point the live
    embedding provider at it. Fully best-effort: any failure (binary missing,
    models not downloaded, engine won't start) silently leaves the default
    (Ollama) active, so the app still boots.
    """
    backend = runtime_state_store.get_active_backend()
    if backend != "llamacpp":
        return
    try:
        # Restore the previously chosen answer model before starting the engine.
        saved_llm = runtime_state_store.get_llamacpp_llm()
        if saved_llm:
            from app.core.use_cases.download_gguf_model import GgufModelRef

            llama_runtime_manager.set_llm_ref(
                GgufModelRef(
                    model_id=saved_llm.get("model_id"),
                    repo_id=saved_llm.get("repo_id"),
                    filename=saved_llm.get("filename"),
                )
            )
        status = llama_runtime_manager.start()
        if status.get("running") and hasattr(embedding_provider, "set_delegate"):
            embedding_provider.set_delegate(build_embedding_for_backend("llamacpp"))
        # Restore the optional "sharper search" reranker if it was on.
        if runtime_state_store.get_rerank_enabled():
            try:
                llama_runtime_manager.enable_rerank()
            except Exception as exc:  # noqa: BLE001 - reranker is optional, never block boot
                _record_startup_diagnostic(
                    "reranker",
                    f"Could not restore the 'sharper search' reranker: {exc}",
                )
    except Exception as exc:  # noqa: BLE001 - degrade to Ollama default on any failure
        _record_startup_diagnostic(
            "engine",
            "Could not re-activate the saved llama.cpp engine; fell back to the "
            f"Ollama default. Answers/search use Ollama until you re-select the "
            f"engine. Reason: {exc}",
        )
