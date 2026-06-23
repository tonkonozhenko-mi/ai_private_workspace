"""User profile HTTP API.

The user's cross-project facts and preferences — who they are, how they want
answers — stored locally and applied to every answer (Ask + Investigator). Fully
user-controlled: list, add, pin and delete. Nothing about the user leaves the
machine, and nothing here retrains a model.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import user_profile_repository
from app.core.domain.user_profile import CATEGORIES, UserProfileCategory
from app.core.use_cases.manage_user_profile import (
    AddUserProfileFactInput,
    ManageUserProfileUseCase,
    UserProfileValidationError,
)

router = APIRouter(prefix="/user-profile", tags=["user-profile"])


def _manage() -> ManageUserProfileUseCase:
    return ManageUserProfileUseCase(user_profile_repository)


class ProfileFactResponse(BaseModel):
    id: str
    category: str
    text: str
    created_at: str
    pinned: bool


class ProfileListResponse(BaseModel):
    facts: list[ProfileFactResponse]
    categories: list[str]


class AddProfileFactRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    category: str = UserProfileCategory.FACT
    pinned: bool = False


class PinProfileFactRequest(BaseModel):
    pinned: bool


def _fact_dict(item) -> ProfileFactResponse:
    return ProfileFactResponse(
        id=item.id,
        category=item.category,
        text=item.text,
        created_at=item.created_at,
        pinned=item.pinned,
    )


@router.get("", response_model=ProfileListResponse)
def list_profile() -> ProfileListResponse:
    facts = [_fact_dict(i) for i in _manage().list()]
    return ProfileListResponse(facts=facts, categories=list(CATEGORIES))


@router.post("", response_model=ProfileFactResponse, status_code=status.HTTP_201_CREATED)
def add_profile_fact(request: AddProfileFactRequest) -> ProfileFactResponse:
    try:
        item = _manage().add(
            AddUserProfileFactInput(
                text=request.text, category=request.category, pinned=request.pinned
            )
        )
    except UserProfileValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _fact_dict(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile_fact(item_id: str) -> None:
    _manage().delete(item_id)


@router.post("/{item_id}/pin", response_model=ProfileFactResponse)
def pin_profile_fact(item_id: str, request: PinProfileFactRequest) -> ProfileFactResponse:
    manage = _manage()
    manage.set_pinned(item_id, request.pinned)
    item = next((i for i in manage.list() if i.id == item_id), None)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile fact not found")
    return _fact_dict(item)
