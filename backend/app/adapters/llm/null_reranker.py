class NullReranker:
    """A reranker that does nothing — keeps retrieval order. Used whenever the
    "sharper search" toggle is off or no reranker runtime is configured."""

    enabled = False

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[int]:
        return list(range(len(documents)))[: max(0, top_k)]
