from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Private Project AI Workbench"
    APP_DATA_DIR: Path = Path(".ai-workbench")
    WORKSPACE_DB_PATH: Path = Path(".ai-workbench/workspaces.db")
    WORKSPACE_REPOSITORY: str = "sqlite"
    COMMAND_RUNNER: str = "fake"
    COMMAND_TIMEOUT_SECONDS: int = 30
    COMMAND_OUTPUT_LIMIT_CHARS: int = 20000
    VECTOR_STORE: str = "memory"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "ai_workbench_chunks"

    @property
    def app_data_dir(self) -> Path:
        return self.APP_DATA_DIR

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


@lru_cache
def get_settings() -> Settings:
    app_data_dir = Path(os.getenv("APP_DATA_DIR", ".ai-workbench"))
    workspace_db_path = Path(
        os.getenv("WORKSPACE_DB_PATH", str(app_data_dir / "workspaces.db"))
    )

    settings = Settings(
        APP_DATA_DIR=app_data_dir,
        WORKSPACE_DB_PATH=workspace_db_path,
        WORKSPACE_REPOSITORY=os.getenv("WORKSPACE_REPOSITORY", "sqlite"),
        COMMAND_RUNNER=os.getenv("COMMAND_RUNNER", "fake"),
        COMMAND_TIMEOUT_SECONDS=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "30")),
        COMMAND_OUTPUT_LIMIT_CHARS=int(os.getenv("COMMAND_OUTPUT_LIMIT_CHARS", "20000")),
        VECTOR_STORE=os.getenv("VECTOR_STORE", "memory"),
        QDRANT_URL=os.getenv("QDRANT_URL", "http://localhost:6333"),
        QDRANT_COLLECTION=os.getenv("QDRANT_COLLECTION", "ai_workbench_chunks"),
    )
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
