from app.adapters.commands.fake_command_runner import FakeCommandRunner
from app.adapters.commands.local_command_runner import LocalCommandRunner
from app.adapters.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.adapters.llm.fake_llm_provider import FakeLLMProvider
from app.adapters.memory.in_memory_command_repository import InMemoryCommandRepository
from app.adapters.memory.in_memory_index_status_repository import (
    InMemoryIndexStatusRepository,
)
from app.adapters.memory.in_memory_project_scan_repository import (
    InMemoryProjectScanRepository,
)
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.adapters.memory.sqlite_command_repository import SQLiteCommandRepository
from app.adapters.memory.sqlite_index_status_repository import SQLiteIndexStatusRepository
from app.adapters.memory.sqlite_project_scan_repository import SQLiteProjectScanRepository
from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.config.settings import get_settings
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


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


def build_command_repository() -> CommandRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryCommandRepository()
    if repository_type == "sqlite":
        return SQLiteCommandRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_index_status_repository() -> IndexStatusRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryIndexStatusRepository()
    if repository_type == "sqlite":
        return SQLiteIndexStatusRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


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
    if vector_store_type == "qdrant":
        from app.adapters.vector_store.qdrant_vector_store import QdrantVectorStore

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

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


def build_llm_provider() -> LLMProviderPort:
    return FakeLLMProvider()


workspace_repository = build_workspace_repository()
project_scan_repository = build_project_scan_repository()
command_repository = build_command_repository()
index_status_repository = build_index_status_repository()
file_system = LocalFileSystem()
command_runner = build_command_runner()
embedding_provider = build_embedding_provider()
llm_provider = build_llm_provider()
vector_store = build_vector_store()
