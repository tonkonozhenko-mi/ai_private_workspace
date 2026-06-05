from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class VectorDocument:
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, str] = field(default_factory=dict)


class VectorStore(Protocol):
    def upsert(self, workspace_id: str, documents: list[VectorDocument]) -> None:
        """Store embedded documents for a workspace."""

    def list_documents(self, workspace_id: str) -> list[VectorDocument]:
        """Return stored documents for a workspace."""
