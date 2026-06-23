"""In-memory User Profile store (tests / memory mode)."""

from dataclasses import replace

from app.core.domain.user_profile import UserProfileItem


class InMemoryUserProfileRepository:
    def __init__(self) -> None:
        self._items: list[UserProfileItem] = []

    def add(self, item: UserProfileItem) -> UserProfileItem:
        self._items.append(item)
        return item

    def list(self) -> list[UserProfileItem]:
        return sorted(self._items, key=lambda i: i.created_at, reverse=True)

    def delete(self, item_id: str) -> None:
        self._items = [i for i in self._items if i.id != item_id]

    def set_pinned(self, item_id: str, pinned: bool) -> None:
        self._items = [
            replace(i, pinned=pinned) if i.id == item_id else i for i in self._items
        ]

    def clear(self) -> None:
        self._items = []
