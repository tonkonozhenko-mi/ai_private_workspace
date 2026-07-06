import logging
from pathlib import Path

from app.adapters.embeddings.switchable_embedding_provider import (
    SwitchableEmbeddingProvider,
)
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.adapters.llm.llama_server_reranker import LlamaServerReranker
from app.adapters.system.gguf_download_job_runner import GgufDownloadJobRunner
from app.adapters.system.huggingface_gguf_downloader import HuggingFaceGgufDownloader
from app.adapters.system.llama_runtime_manager import LlamaRuntimeManager
from app.adapters.system.local_git_history import LocalGitHistory
from app.adapters.system.runtime_state_store import RuntimeStateStore
from app.api._container_factories import (
    build_agent_workflow_repository,
    build_answer_rating_repository,
    build_app_preferences_repository,
    build_command_repository,
    build_command_runner,
    build_conversation_repository,
    build_embedding_provider,
    build_index_manifest_repository,
    build_index_status_repository,
    build_indexing_rules_repository,
    build_llm_provider_factory,
    build_local_model_download_job_repository,
    build_mcp_repository,
    build_model_catalog_registry,
    build_model_experiment_rating_repository,
    build_model_experiment_repository,
    build_project_graph_repository,
    build_project_group_repository,
    build_project_memory_repository,
    build_project_scan_repository,
    build_project_understanding_repository,
    build_project_watch_repository,
    build_readiness_configuration,
    build_report_repository,
    build_runtime_health_checkers,
    build_runtime_health_configuration,
    build_skill_profile_repository,
    build_timeline_repository,
    build_user_profile_repository,
    build_vector_store,
    build_workspace_model_selection_repository,
    build_workspace_repository,
    build_workspace_storage_gateway,
)
from app.config.settings import get_settings
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase
from app.core.use_cases.download_gguf_model import DownloadGgufModelUseCase


def build_embedding_for_backend(backend: str) -> EmbeddingProviderPort:
    """Build an embedding provider for an explicit backend ('ollama'|'llamacpp')."""
    settings = get_settings()
    name = backend.strip().lower()
    if name == "llamacpp":
        from app.adapters.embeddings.llama_server_embedding_provider import (
            LlamaServerEmbeddingProvider,
        )

        # Report the model the engine is actually serving (the saved/switched
        # search model), not the static env default — otherwise the readiness
        # check sees a false "runtime does not match" after switching the built-in
        # embedder and on every relaunch.
        model = settings.ollama_embedding_model
        try:
            model = llama_runtime_manager.active_embed_model_id or model
        except Exception:  # noqa: BLE001 - manager not ready yet → fall back to default
            pass
        return LlamaServerEmbeddingProvider(
            base_url=f"http://{settings.LLAMA_SERVER_HOST}:{settings.LLAMA_SERVER_EMBED_PORT}",
            model=model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    from app.adapters.embeddings.ollama_embedding_provider import OllamaEmbeddingProvider

    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )


workspace_repository = build_workspace_repository()
project_scan_repository = build_project_scan_repository()
report_repository = build_report_repository()
project_understanding_repository = build_project_understanding_repository()
agent_workflow_repository = build_agent_workflow_repository()
mcp_repository = build_mcp_repository()
command_repository = build_command_repository()
local_model_download_job_repository = build_local_model_download_job_repository()
index_status_repository = build_index_status_repository()
index_manifest_repository = build_index_manifest_repository()
indexing_rules_repository = build_indexing_rules_repository()
skill_profile_repository = build_skill_profile_repository()
timeline_repository = build_timeline_repository()
conversation_repository = build_conversation_repository()
project_graph_repository = build_project_graph_repository()
project_watch_repository = build_project_watch_repository()
project_memory_repository = build_project_memory_repository()
user_profile_repository = build_user_profile_repository()
app_preferences_repository = build_app_preferences_repository()
project_group_repository = build_project_group_repository()
answer_rating_repository = build_answer_rating_repository()
# Shared project-context provider injected into Ask + the Investigator. It also
# applies the user's cross-project profile (about the person, not the project).
project_context_composer = ComposeProjectContextUseCase(
    project_memory_repository,
    project_graph_repository,
    user_profile_repository,
    watch_repository=project_watch_repository,
)


def handbook_text_provider(workspace_id: str) -> str | None:
    """Deterministic project handbook text for indexing as a pseudo-document.

    Built fresh from the latest project map (same builder as the Handbook memory
    item), so "what is this project about" questions can retrieve the summary.
    Returns None when no map exists yet or the build fails — indexing then simply
    skips the pseudo-document."""
    graph = project_graph_repository.get_latest_graph(workspace_id)
    if graph is None:
        return None
    try:
        from app.core.domain.project_handbook import build_handbook

        return build_handbook(graph)
    except Exception:  # noqa: BLE001 — optional enrichment, never break indexing
        return None


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
    llm_context_size=get_settings().LLAMA_SERVER_LLM_CONTEXT_SIZE,
)
command_runner = build_command_runner()
embedding_provider = SwitchableEmbeddingProvider(build_embedding_provider())
# Semantic memory re-ranking uses the live (switchable) embedder, so it tracks
# engine/model switches. Attached here because the composer is built above, before
# the embedder exists.
project_context_composer.embedding_provider = embedding_provider
runtime_state_store = RuntimeStateStore(Path(get_settings().app_data_dir) / "runtime_state.json")
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
        # Restore the previously chosen search/embedding model too.
        saved_embedding = runtime_state_store.get_llamacpp_embedding()
        if saved_embedding:
            from app.core.use_cases.download_gguf_model import GgufModelRef

            llama_runtime_manager.set_embed_ref(
                GgufModelRef(
                    model_id=saved_embedding.get("model_id"),
                    repo_id=saved_embedding.get("repo_id"),
                    filename=saved_embedding.get("filename"),
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
