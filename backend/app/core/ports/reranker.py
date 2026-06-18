from typing import Protocol


class RerankerPort(Protocol):
    """Optional precision pass over retrieved candidates.

    A reranker is a cross-encoder: it scores each (query, document) pair together,
    which is more accurate than comparing their separate embeddings. It runs only
    over the top candidates from hybrid retrieval, then we keep the best.

    Implementations must degrade gracefully: when disabled or unavailable they
    return the input order unchanged so retrieval never breaks.
    """

    @property
    def enabled(self) -> bool:
        """True only when a reranker model/runtime is actually available."""

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[int]:
        """Return indices into ``documents``, best-first, length <= ``top_k``.

        Returning ``list(range(len(documents)))[:top_k]`` is the safe identity
        (no reordering), used whenever reranking can't run.
        """
