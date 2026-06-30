"""In-memory Project Memory store (tests / memory mode)."""

from dataclasses import replace
from datetime import datetime, timezone

from app.core.domain.project_memory import MemoryItem


class InMemoryProjectMemoryRepository:
    def __init__(self) -> None:
        self._items: dict[str, list[MemoryItem]] = {}

    def add(self, item: MemoryItem) -> MemoryItem:
        self._items.setdefault(item.workspace_id, []).append(item)
        return item

    def list(self, workspace_id: str) -> list[MemoryItem]:
        items = self._items.get(workspace_id, [])
        return sorted(items, key=lambda i: i.created_at, reverse=True)

    def delete(self, workspace_id: str, item_id: str) -> None:
        items = self._items.get(workspace_id)
        if items:
            self._items[workspace_id] = [i for i in items if i.id != item_id]

    def delete_kind(self, workspace_id: str, kind: str) -> None:
        items = self._items.get(workspace_id)
        if items:
            self._items[workspace_id] = [i for i in items if i.kind != kind]

    def set_pinned(self, workspace_id: str, item_id: str, pinned: bool) -> None:
        items = self._items.get(workspace_id, [])
        for idx, item in enumerate(items):
            if item.id == item_id:
                items[idx] = replace(item, pinned=pinned)

    def set_status(self, workspace_id: str, item_id: str, status: str) -> None:
        items = self._items.get(workspace_id, [])
        for idx, item in enumerate(items):
            if item.id == item_id:
                items[idx] = replace(
                    item, status=status, updated_at=datetime.now(timezone.utc).isoformat()
                )

    def clear(self, workspace_id: str) -> None:
        self._items.pop(workspace_id, None)
