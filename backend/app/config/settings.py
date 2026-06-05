from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Private Project AI Workbench"


@lru_cache
def get_settings() -> Settings:
    return Settings()
