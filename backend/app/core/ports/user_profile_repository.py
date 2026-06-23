from typing import Protocol

from app.core.domain.user_profile import UserProfileItem


class UserProfileRepositoryPort(Protocol):
    """Durable store of facts about the user. Global — one profile per install,
    shared across every workspace."""

    def add(self, item: UserProfileItem) -> UserProfileItem:
        """Persist a profile fact."""

    def list(self) -> list[UserProfileItem]:
        """All profile facts, newest first."""

    def delete(self, item_id: str) -> None:
        """Remove a fact."""

    def set_pinned(self, item_id: str, pinned: bool) -> None:
        """Pin or unpin a fact."""

    def clear(self) -> None:
        """Remove the whole profile."""
