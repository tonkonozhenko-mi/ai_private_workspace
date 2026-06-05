from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.workspaces import router as workspaces_router
from app.config.settings import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(workspaces_router)
