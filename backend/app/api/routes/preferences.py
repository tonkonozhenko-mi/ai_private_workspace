"""App preferences HTTP API.

The user's app-level settings (theme, default Ask options, branding, …) stored
locally on the backend so they survive a browser-cache clear and are the single
source of truth. The frontend keeps a localStorage copy only for instant first
paint. Fully local — nothing here leaves the machine.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import app_preferences_repository
from app.core.use_cases.manage_app_preferences import (
    AppPreferencesValidationError,
    ManageAppPreferencesUseCase,
)

router = APIRouter(prefix="/preferences", tags=["preferences"])


def _manage() -> ManageAppPreferencesUseCase:
    return ManageAppPreferencesUseCase(app_preferences_repository)


class PreferencesResponse(BaseModel):
    values: dict


class UpdatePreferencesRequest(BaseModel):
    values: dict = Field(default_factory=dict)


@router.get("", response_model=PreferencesResponse)
def get_preferences() -> PreferencesResponse:
    return PreferencesResponse(values=_manage().get())


@router.put("", response_model=PreferencesResponse)
def update_preferences(request: UpdatePreferencesRequest) -> PreferencesResponse:
    try:
        merged = _manage().update(request.values)
    except AppPreferencesValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return PreferencesResponse(values=merged)
