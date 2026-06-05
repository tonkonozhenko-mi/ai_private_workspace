from app.core.ports.vector_store import VectorDocument


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._documents: dict[str, list[VectorDocument]] = {}

    def upsert(self, workspace_id: str, documents: list[VectorDocument]) -> None:
        self._documents.setdefault(workspace_id, []).extend(documents)

    def list_documents(self, workspace_id: str) -> list[VectorDocument]:
        return list(self._documents.get(workspace_id, []))
