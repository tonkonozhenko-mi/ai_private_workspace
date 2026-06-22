import sys

from dotenv import load_dotenv

# Load backend/.env (if present) before reading any settings, so local dev can
# point at the desktop app's data directory without exporting variables by hand.
# Never load it under pytest: tests must run against clean defaults, not the
# developer's local data paths or overrides.
if "pytest" not in sys.modules:
    load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent_workflows import router as agent_workflows_router
from app.api.routes.assistant_profiles import router as assistant_profiles_router
from app.api.routes.commands import router as commands_router
from app.api.routes.health import router as health_router
from app.api.routes.local_data_safety import router as local_data_safety_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.models import router as models_router
from app.api.routes.onboarding import router as onboarding_router
from app.api.routes.answer_ratings import router as answer_ratings_router
from app.api.routes.project_groups import router as project_groups_router
from app.api.routes.project_intelligence import router as project_intelligence_router
from app.api.routes.projects import router as projects_router
from app.api.routes.runtime_health import router as runtime_health_router
from app.api.routes.workspaces import router as workspaces_router
from app.config.settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Re-activate the last-used local engine (e.g. llama.cpp) without blocking
    boot. Runs in a background thread because starting the engine waits on a
    health check; the API stays responsive meanwhile."""
    import threading

    from app.api.dependencies import restore_active_backend

    threading.Thread(target=restore_active_backend, daemon=True).start()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|tauri\.localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(runtime_health_router)
app.include_router(local_data_safety_router)
app.include_router(assistant_profiles_router)
app.include_router(agent_workflows_router)
app.include_router(models_router)
app.include_router(mcp_router)
app.include_router(onboarding_router)
app.include_router(projects_router)
app.include_router(workspaces_router)
app.include_router(project_intelligence_router)
app.include_router(project_groups_router)
app.include_router(answer_ratings_router)
app.include_router(commands_router)
