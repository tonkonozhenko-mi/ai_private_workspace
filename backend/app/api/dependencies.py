import logging
from pathlib import Path

from app.adapters.documents.local_document_extractor import LocalDocumentExtractor
from app.adapters.embeddings.switchable_embedding_provider import (
    SwitchableEmbeddingProvider,
)
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.adapters.llm.llama_server_reranker import LlamaServerReranker
from app.adapters.system.gguf_download_job_runner import GgufDownloadJobRunner
from app.adapters.system.huggingface_gguf_downloader import HuggingFaceGgufDownloader
from app.adapters.system.llama_runtime_manager import LlamaRuntimeManager
from app.adapters.system.ollama_pull_job_runner import OllamaPullJobRunner
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
# Reads Word/Excel/PDF/HTML into locatable text sections, entirely on this
# computer — no document ever leaves the machine.
document_extractor = LocalDocumentExtractor()
_gguf_download_use_case = DownloadGgufModelUseCase(
    HuggingFaceGgufDownloader(), get_settings().app_data_dir
)
gguf_download_job_runner = GgufDownloadJobRunner(_gguf_download_use_case)
# Downloading through the Ollama daemon: an HTTP fetch, deliberately not routed
# through the shell-command machinery. See domain/model_download_boundary.py.
ollama_pull_job_runner = OllamaPullJobRunner(base_url=get_settings().ollama_base_url)
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


def build_workspace_llm_provider(workspace_id: str | None = None):
    """The LLM provider a workspace should generate with — the same engine Ask uses,
    not the static configured default.

    Some features (the Intelligence overview, "ask the map") used to build their
    provider with ``create(provider=None)``, which resolves to the configured default
    (often Ollama/llama3.2) regardless of what the workspace actually runs. On a
    llama.cpp-only setup that meant those features tried to reach an Ollama that isn't
    there. Resolution order now mirrors Ask: the workspace's explicitly selected
    answer model first; then the live active backend (llama.cpp with its running
    model, or Ollama); then the configured default as a last resort.
    """
    if workspace_id:
        try:
            selection = workspace_model_selection_repository.get(workspace_id)
        except Exception:  # noqa: BLE001 - fall through to the active backend
            selection = None
        selected = selection.selected_llm if selection is not None else None
        if selected is not None and llm_provider_factory.supports(selected.provider):
            return llm_provider_factory.create(selected.provider, selected.model)
    backend = runtime_state_store.get_active_backend()
    if backend == "llamacpp":
        return llm_provider_factory.create("llamacpp", None)
    if backend == "ollama":
        return llm_provider_factory.create("ollama", None)
    return llm_provider_factory.create(None, None)


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


def ollama_reachable() -> bool:
    """Quick probe: is an Ollama server actually answering right now? Used to decide
    whether to fall back to llama.cpp when the app would otherwise default to Ollama
    (e.g. the user uninstalled Ollama). Best-effort — any error counts as
    unreachable, so a missing/stopped Ollama never keeps the app pinned to a dead
    endpoint."""
    try:
        import httpx

        response = httpx.get(
            f"{get_settings().ollama_base_url.rstrip('/')}/api/tags",
            timeout=2.0,
        )
        return response.status_code < 500
    except Exception:  # noqa: BLE001 - refused/timeout/DNS all mean "no Ollama"
        return False


def activate_llamacpp_engine(restore_saved: bool = True) -> bool:
    """Bring the llama.cpp engine up and point the live embedding provider + active
    backend at it. When ``restore_saved`` is set, the previously chosen answer/search
    models are restored first (used on startup); otherwise the engine resolves to the
    recommended defaults. Returns True only when the engine is actually running, so a
    caller can fall back to Ollama on False. Best-effort: never raises."""
    try:
        if restore_saved:
            from app.core.use_cases.download_gguf_model import GgufModelRef

            saved_llm = runtime_state_store.get_llamacpp_llm()
            if saved_llm:
                llama_runtime_manager.set_llm_ref(
                    GgufModelRef(
                        model_id=saved_llm.get("model_id"),
                        repo_id=saved_llm.get("repo_id"),
                        filename=saved_llm.get("filename"),
                    )
                )
            saved_embedding = runtime_state_store.get_llamacpp_embedding()
            if saved_embedding:
                llama_runtime_manager.set_embed_ref(
                    GgufModelRef(
                        model_id=saved_embedding.get("model_id"),
                        repo_id=saved_embedding.get("repo_id"),
                        filename=saved_embedding.get("filename"),
                    )
                )
        status = llama_runtime_manager.start()
        if not status.get("running"):
            return False
        if hasattr(embedding_provider, "set_delegate"):
            embedding_provider.set_delegate(build_embedding_for_backend("llamacpp"))
        runtime_state_store.set_active_backend("llamacpp")
        # Restore the optional "sharper search" reranker if it was on.
        if runtime_state_store.get_rerank_enabled():
            try:
                llama_runtime_manager.enable_rerank()
            except Exception as exc:  # noqa: BLE001 - reranker is optional, never block
                _record_startup_diagnostic(
                    "reranker",
                    f"Could not restore the 'sharper search' reranker: {exc}",
                )
        return True
    except Exception:  # noqa: BLE001 - caller decides what to do when the engine won't start
        return False


def restore_active_backend() -> None:
    """Re-activate the right engine on startup so index and search agree.

    If the user last activated llama.cpp, bring it up. If the persisted engine is
    Ollama but Ollama is no longer reachable (e.g. the user uninstalled it), fall
    back to llama.cpp when a local model is available, so the app doesn't boot onto a
    dead engine. Fully best-effort: any failure leaves the Ollama default active so
    the app still boots.
    """
    backend = runtime_state_store.get_active_backend()
    if backend == "llamacpp":
        if not activate_llamacpp_engine(restore_saved=True):
            _record_startup_diagnostic(
                "engine",
                "Could not re-activate the saved llama.cpp engine; fell back to the "
                "Ollama default. Answers/search use Ollama until you re-select the "
                "engine.",
            )
        return

    # Persisted engine is Ollama (or unset). Keep it only if Ollama is actually
    # reachable; if it isn't — removed or stopped — switch to llama.cpp so the app
    # stays usable instead of pointing every answer at a dead endpoint.
    if ollama_reachable():
        return
    if activate_llamacpp_engine(restore_saved=True):
        _record_startup_diagnostic(
            "engine",
            "Ollama was not reachable at startup, so the app switched to the local "
            "llama.cpp engine.",
        )
    else:
        _record_startup_diagnostic(
            "engine",
            "Ollama was not reachable at startup and no local llama.cpp model was "
            "available to fall back to. Download a local model (or start Ollama) to "
            "answer questions.",
        )
