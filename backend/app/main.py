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

from app.api.local_api_token import LocalApiTokenMiddleware
from app.api.routes.agent_workflows import router as agent_workflows_router
from app.api.routes.answer_ratings import router as answer_ratings_router
from app.api.routes.assistant_profiles import router as assistant_profiles_router
from app.api.routes.attachments import router as attachments_router
from app.api.routes.commands import router as commands_router
from app.api.routes.health import router as health_router
from app.api.routes.local_data_safety import router as local_data_safety_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.models import router as models_router
from app.api.routes.onboarding import router as onboarding_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.project_groups import router as project_groups_router
from app.api.routes.project_intelligence import router as project_intelligence_router
from app.api.routes.projects import router as projects_router
from app.api.routes.runtime_health import router as runtime_health_router
from app.api.routes.user_profile import router as user_profile_router
from app.api.routes.workspaces import router as workspaces_router
from app.config.logging_setup import configure_app_logging
from app.config.settings import get_settings

# Attach a handler to the "app" logger so the application's own INFO logs (scan
# phase timings, etc.) actually reach stdout / backend.log. Without this, uvicorn
# only wires up its own loggers and every app.* message is dropped.
configure_app_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Re-activate the last-used local engine (e.g. llama.cpp) without blocking
    boot. Runs in a background thread because starting the engine waits on a
    health check; the API stays responsive meanwhile."""
    import threading

    from app.api.dependencies import restore_active_backend
    from app.config.fd_limit import raise_fd_limit

    # macOS gives GUI-launched processes only 256 file descriptors; a long
    # index build under frontend polling exhausts that and kills SQLite for
    # the whole process (live incident — see app/config/fd_limit.py).
    raise_fd_limit()

    threading.Thread(target=restore_active_backend, daemon=True).start()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

# Added before CORS on purpose. Starlette runs the last-added middleware
# outermost, so this ordering puts CORS outside the token check — which is what
# makes a 401 come back with CORS headers on it. The other way round, the app's
# own webview would see an opaque network failure instead of the reason.
app.add_middleware(LocalApiTokenMiddleware, token=settings.API_AUTH_TOKEN)

# The origin list stays as it is, including "null" and every localhost port.
# With the token required it no longer decides anything: an allowed origin
# without the token gets a 401, and the only route it can still reach is
# /health. Tightening it would mean guessing which origin each platform's
# webview actually sends, and getting that wrong locks the person out of their
# own app — a real risk in exchange for no additional protection.
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
app.include_router(attachments_router)
app.include_router(agent_workflows_router)
app.include_router(models_router)
app.include_router(mcp_router)
app.include_router(onboarding_router)
app.include_router(preferences_router)
app.include_router(projects_router)
app.include_router(workspaces_router)
app.include_router(project_intelligence_router)
app.include_router(project_groups_router)
app.include_router(answer_ratings_router)
app.include_router(user_profile_router)
app.include_router(commands_router)
