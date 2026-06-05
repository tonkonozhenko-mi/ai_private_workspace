from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Private Project AI Workbench"
    APP_DATA_DIR: Path = Path(".ai-workbench")
    WORKSPACE_DB_PATH: Path = Path(".ai-workbench/workspaces.db")
    WORKSPACE_REPOSITORY: str = "sqlite"

    @property
    def app_data_dir(self) -> Path:
        return self.APP_DATA_DIR

    @property
    def workspace_db_path(self) -> Path:
        return self.WORKSPACE_DB_PATH

    @property
    def workspace_repository(self) -> str:
        return self.WORKSPACE_REPOSITORY


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
    )
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
