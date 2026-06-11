from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel


PRODUCT_NAME = "AI Private Workspace"
# Keep the legacy hidden runtime directory for backward compatibility with
# existing local installations. It is not a product-facing name.
DEFAULT_APP_DATA_DIR = Path(".ai-workbench")
DEFAULT_QDRANT_COLLECTION = "ai_workbench_chunks"


class Settings(BaseModel):
    app_name: str = PRODUCT_NAME
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
    VECTOR_STORE: str = "memory"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = DEFAULT_QDRANT_COLLECTION
    EMBEDDING_PROVIDER: str = "fake"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: int = 30
    LLM_PROVIDER: str = "fake"
    OLLAMA_LLM_MODEL: str = "llama3.2"
    OLLAMA_LLM_TIMEOUT_SECONDS: int = 120
    RUNTIME_HEALTH_TIMEOUT_SECONDS: int = 3
    USER_MODEL_CATALOG_PATH: str = ""
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
    def model_download_execution_enabled(self) -> bool:
        return self.MODEL_DOWNLOAD_EXECUTION_ENABLED


@lru_cache
def get_settings() -> Settings:
    app_data_dir = Path(os.getenv("APP_DATA_DIR", str(DEFAULT_APP_DATA_DIR)))
    workspace_db_path = Path(
        os.getenv("WORKSPACE_DB_PATH", str(app_data_dir / "workspaces.db"))
    )
    cors_allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    settings = Settings(
        CORS_ALLOWED_ORIGINS=cors_allowed_origins,
        APP_DATA_DIR=app_data_dir,
        WORKSPACE_DB_PATH=workspace_db_path,
        WORKSPACE_REPOSITORY=os.getenv("WORKSPACE_REPOSITORY", "sqlite"),
        COMMAND_RUNNER=os.getenv("COMMAND_RUNNER", "fake"),
        COMMAND_TIMEOUT_SECONDS=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "30")),
        COMMAND_OUTPUT_LIMIT_CHARS=int(os.getenv("COMMAND_OUTPUT_LIMIT_CHARS", "20000")),
        VECTOR_STORE=os.getenv("VECTOR_STORE", "memory"),
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
        OLLAMA_LLM_TIMEOUT_SECONDS=int(
            os.getenv("OLLAMA_LLM_TIMEOUT_SECONDS", "120")
        ),
        RUNTIME_HEALTH_TIMEOUT_SECONDS=int(
            os.getenv("RUNTIME_HEALTH_TIMEOUT_SECONDS", "3")
        ),
        USER_MODEL_CATALOG_PATH=os.getenv("USER_MODEL_CATALOG_PATH", ""),
        MODEL_DOWNLOAD_EXECUTION_ENABLED=os.getenv("MODEL_DOWNLOAD_EXECUTION_ENABLED", "false").lower()
        in {"1", "true", "yes", "on"},
    )
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
