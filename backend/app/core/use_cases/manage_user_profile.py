"""Create, list, edit and delete the user's profile facts.

A thin coordinator over the repository and the pure helpers in the domain. The
profile is global (one per install) and entirely user-controlled.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.user_profile import (
    CATEGORIES,
    UserProfileCategory,
    UserProfileItem,
    is_duplicate,
)
from app.core.ports.user_profile_repository import UserProfileRepositoryPort


class UserProfileValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AddUserProfileFactInput:
    text: str
    category: str = UserProfileCategory.FACT
    pinned: bool = False


class ManageUserProfileUseCase:
    def __init__(self, repository: UserProfileRepositoryPort) -> None:
        self.repository = repository

    def add(self, request: AddUserProfileFactInput) -> UserProfileItem:
        text = (request.text or "").strip()
        if not text:
            raise UserProfileValidationError("A profile fact needs some text.")
        if len(text) > 600:
            raise UserProfileValidationError("Keep a profile fact under 600 characters.")
        category = request.category if request.category in CATEGORIES else UserProfileCategory.FACT

        existing = self.repository.list()
        # Adding the same fact twice quietly returns the existing one.
        if is_duplicate(existing, text):
            norm = " ".join(text.lower().split())
            for item in existing:
                if " ".join(item.text.lower().split()) == norm:
                    return item

        item = UserProfileItem(
            id=uuid.uuid4().hex,
            category=category,
            text=text,
            created_at=_now_iso(),
            pinned=request.pinned,
        )
        return self.repository.add(item)

    def list(self) -> list[UserProfileItem]:
        return self.repository.list()

    def delete(self, item_id: str) -> None:
        self.repository.delete(item_id)

    def set_pinned(self, item_id: str, pinned: bool) -> None:
        self.repository.set_pinned(item_id, pinned)

    def clear(self) -> None:
        self.repository.clear()
