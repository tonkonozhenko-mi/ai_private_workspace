import os
import platform
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

PRODUCT_NAME = "AI Private Workspace"
# Keep in sync with frontend/src-tauri/tauri.conf.json on every release bump.
APP_VERSION = "0.1.140"
# Keep the legacy hidden runtime directory for backward compatibility with
# existing local installations. It is not a product-facing name.
DEFAULT_APP_DATA_DIR = Path(".ai-workbench")
DEFAULT_QDRANT_COLLECTION = "ai_workbench_chunks"


def _first_non_empty_env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _prepare_runtime_path(path_value: str, *, label: str, create_parent: bool) -> Path:
    try:
        path = Path(path_value).expanduser()
        directory = path.parent if create_parent else path
        directory.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Could not prepare {label} at {path_value!r}: {exc}") from exc
    return path


def _llama_arch_dir() -> str:
    """Map the running machine to our bundled llama.cpp arch folder name."""
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    return "x64"  # x86_64 / amd64 / Intel


def llama_server_binary_candidates() -> list[Path]:
    """Every place we look for the bundled ``llama-server`` binary, in order.

    Covers: an explicit env path (set by the desktop shell), a source checkout
    (``<repo>/build/desktop/llama-runtime/<arch>/``), the current dir and its
    ancestors (launcher run from the repo), and — for the packaged ``.app`` —
    locations relative to the frozen backend executable, including
    ``…/Contents/Resources/llama-runtime/<arch>/``.
    """
    import sys

    arch = _llama_arch_dir()
    # The bundled binary is `llama-server` on macOS/Linux and `llama-server.exe`
    # on Windows; without the suffix the packaged Windows app can't find it.
    binary_name = "llama-server.exe" if os.name == "nt" else "llama-server"
    build_rel = Path("build") / "desktop" / "llama-runtime" / arch / binary_name
    res_rel = Path("llama-runtime") / arch / binary_name

    candidates: list[Path] = []

    override = os.getenv("LLAMA_SERVER_BINARY_PATH", "").strip()
    if override:
        candidates.append(Path(override).expanduser())

    # Source checkout: settings.py is backend/app/config/settings.py.
    candidates.append(Path(__file__).resolve().parents[3] / build_rel)

    # Current working dir and a few ancestors (launcher started from the repo).
    cwd = Path.cwd()
    for base in [cwd, *list(cwd.parents)[:6]]:
        candidates.append(base / build_rel)

    # Packaged app: relative to the frozen backend executable and its ancestors,
    # including the macOS .app `Contents/Resources` layout.
    try:
        exe_dir = Path(sys.executable).resolve().parent
        for base in [exe_dir, *list(exe_dir.parents)[:8]]:
            candidates.append(base / res_rel)
            candidates.append(base / "Resources" / res_rel)
            candidates.append(base / build_rel)
    except (OSError, ValueError):
        pass

    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def resolve_llama_server_binary_path() -> Path | None:
    """Return the first existing ``llama-server`` binary, or ``None``.

    ``None`` means the app degrades to Ollama instead of crashing.
    """
    for candidate in llama_server_binary_candidates():
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


class Settings(BaseModel):
    app_name: str = PRODUCT_NAME
    app_version: str = APP_VERSION
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    APP_DATA_DIR: Path = DEFAULT_APP_DATA_DIR
    WORKSPACE_DB_PATH: Path = DEFAULT_APP_DATA_DIR / "workspaces.db"
    WORKSPACE_REPOSITORY: str = "sqlite"
    COMMAND_RUNNER: str = "fake"
    COMMAND_TIMEOUT_SECONDS: int = 30
    COMMAND_OUTPUT_LIMIT_CHARS: int = 20000
    VECTOR_STORE: str = "sqlite"
    VECTOR_STORE_PATH: Path = DEFAULT_APP_DATA_DIR / "data" / "vector_store.db"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = DEFAULT_QDRANT_COLLECTION
    EMBEDDING_PROVIDER: str = "fake"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: int = 30
    LLM_PROVIDER: str = "fake"
    OLLAMA_LLM_MODEL: str = "llama3.2"
    OLLAMA_LLM_TIMEOUT_SECONDS: int = 120
    # llama.cpp (Ollama-free) backend: the bundled llama-server listens here.
    LLAMA_SERVER_HOST: str = "127.0.0.1"
    LLAMA_SERVER_LLM_PORT: int = 8080
    LLAMA_SERVER_EMBED_PORT: int = 8081
    LLAMA_SERVER_RERANK_PORT: int = 8082
    RUNTIME_HEALTH_TIMEOUT_SECONDS: int = 3
    USER_MODEL_CATALOG_PATH: str = ""
    USER_MODEL_CATALOG_URL: str = ""
    USER_MODEL_CATALOG_CACHE_PATH: Path = DEFAULT_APP_DATA_DIR / "data" / "model_catalog_cache.json"
    USER_MODEL_CATALOG_FETCH_TIMEOUT_SECONDS: int = 5
    MODEL_DOWNLOAD_EXECUTION_ENABLED: bool = False

    @property
    def app_data_dir(self) -> Path:
        return self.APP_DATA_DIR

    @property
    def cors_allowed_origins(self) -> list[str]:
        return self.CORS_ALLOWED_ORIGINS

    @property
    def workspace_db_path(self) -> Path:
        return self.WORKSPACE_DB_PATH

    @property
    def workspace_repository(self) -> str:
        return self.WORKSPACE_REPOSITORY

    @property
    def command_runner(self) -> str:
        return self.COMMAND_RUNNER

    @property
    def command_timeout_seconds(self) -> int:
        return self.COMMAND_TIMEOUT_SECONDS

    @property
    def command_output_limit_chars(self) -> int:
        return self.COMMAND_OUTPUT_LIMIT_CHARS

    @property
    def vector_store(self) -> str:
        return self.VECTOR_STORE

    @property
    def vector_store_path(self) -> Path:
        return self.VECTOR_STORE_PATH

    @property
    def qdrant_url(self) -> str:
        return self.QDRANT_URL

    @property
    def qdrant_collection(self) -> str:
        return self.QDRANT_COLLECTION

    @property
    def embedding_provider(self) -> str:
        return self.EMBEDDING_PROVIDER

    @property
    def ollama_base_url(self) -> str:
        return self.OLLAMA_BASE_URL

    @property
    def ollama_embedding_model(self) -> str:
        return self.OLLAMA_EMBEDDING_MODEL

    @property
    def ollama_timeout_seconds(self) -> int:
        return self.OLLAMA_TIMEOUT_SECONDS

    @property
    def llm_provider(self) -> str:
        return self.LLM_PROVIDER

    @property
    def ollama_llm_model(self) -> str:
        return self.OLLAMA_LLM_MODEL

    @property
    def ollama_llm_timeout_seconds(self) -> int:
        return self.OLLAMA_LLM_TIMEOUT_SECONDS

    @property
    def runtime_health_timeout_seconds(self) -> int:
        return self.RUNTIME_HEALTH_TIMEOUT_SECONDS

    @property
    def user_model_catalog_path(self) -> str:
        return self.USER_MODEL_CATALOG_PATH

    @property
    def user_model_catalog_url(self) -> str:
        return self.USER_MODEL_CATALOG_URL

    @property
    def user_model_catalog_cache_path(self) -> Path:
        return self.USER_MODEL_CATALOG_CACHE_PATH

    @property
    def user_model_catalog_fetch_timeout_seconds(self) -> int:
        return self.USER_MODEL_CATALOG_FETCH_TIMEOUT_SECONDS

    @property
    def model_download_execution_enabled(self) -> bool:
        return self.MODEL_DOWNLOAD_EXECUTION_ENABLED


@lru_cache
def get_settings() -> Settings:
    app_data_dir_value = _first_non_empty_env(
        "APP_DATA_DIR",
        "AI_WORKSPACE_APP_DATA_DIR",
        default=str(DEFAULT_APP_DATA_DIR),
    )
    app_data_dir = _prepare_runtime_path(
        app_data_dir_value,
        label="application data directory",
        create_parent=False,
    )
    workspace_db_path_value = _first_non_empty_env(
        "WORKSPACE_DB_PATH",
        "AI_WORKBENCH_DB_PATH",
        default=str(app_data_dir / "workspaces.db"),
    )
    workspace_db_path = _prepare_runtime_path(
        workspace_db_path_value,
        label="workspace database parent directory",
        create_parent=True,
    )
    default_cors_origins = ",".join(
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "tauri://localhost",
            "null",
        ]
    )
    cors_allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            default_cors_origins,
        ).split(",")
        if origin.strip()
    ]

    vector_store_path_value = _first_non_empty_env(
        "VECTOR_STORE_PATH",
        "AI_WORKSPACE_VECTOR_STORE_PATH",
        default=str(app_data_dir / "data" / "vector_store.db"),
    )
    vector_store_path = _prepare_runtime_path(
        vector_store_path_value,
        label="vector store database parent directory",
        create_parent=True,
    )

    settings = Settings(
        CORS_ALLOWED_ORIGINS=cors_allowed_origins,
        APP_DATA_DIR=app_data_dir,
        WORKSPACE_DB_PATH=workspace_db_path,
        WORKSPACE_REPOSITORY=os.getenv("WORKSPACE_REPOSITORY", "sqlite"),
        COMMAND_RUNNER=os.getenv("COMMAND_RUNNER", "fake"),
        COMMAND_TIMEOUT_SECONDS=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "30")),
        COMMAND_OUTPUT_LIMIT_CHARS=int(os.getenv("COMMAND_OUTPUT_LIMIT_CHARS", "20000")),
        # Persist the search index by default so it survives backend restarts.
        # In-memory is wiped on restart (→ "no chunks" after a reindex). Tests
        # force "memory" via conftest; the packaged app sets "sqlite" explicitly.
        VECTOR_STORE=os.getenv("VECTOR_STORE", "sqlite"),
        VECTOR_STORE_PATH=vector_store_path,
        QDRANT_URL=os.getenv("QDRANT_URL", "http://localhost:6333"),
        QDRANT_COLLECTION=os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION),
        EMBEDDING_PROVIDER=os.getenv("EMBEDDING_PROVIDER", "fake"),
        OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        OLLAMA_EMBEDDING_MODEL=os.getenv(
            "OLLAMA_EMBEDDING_MODEL",
            "nomic-embed-text",
        ),
        OLLAMA_TIMEOUT_SECONDS=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30")),
        LLM_PROVIDER=os.getenv("LLM_PROVIDER", "fake"),
        OLLAMA_LLM_MODEL=os.getenv("OLLAMA_LLM_MODEL", "llama3.2"),
        OLLAMA_LLM_TIMEOUT_SECONDS=int(os.getenv("OLLAMA_LLM_TIMEOUT_SECONDS", "120")),
        RUNTIME_HEALTH_TIMEOUT_SECONDS=int(os.getenv("RUNTIME_HEALTH_TIMEOUT_SECONDS", "3")),
        USER_MODEL_CATALOG_PATH=os.getenv("USER_MODEL_CATALOG_PATH", ""),
        USER_MODEL_CATALOG_URL=os.getenv("USER_MODEL_CATALOG_URL", ""),
        MODEL_DOWNLOAD_EXECUTION_ENABLED=os.getenv(
            "MODEL_DOWNLOAD_EXECUTION_ENABLED", "false"
        ).lower()
        in {"1", "true", "yes", "on"},
    )
    return settings
