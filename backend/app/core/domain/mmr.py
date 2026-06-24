"""Maximal Marginal Relevance (MMR) selection for retrieved chunks.

Hybrid retrieval ranks chunks purely by relevance, so the top results are often
near-duplicates of each other (the same config echoed across files). MMR instead
picks chunks that are both relevant to the query AND different from what's already
selected, so a fixed context budget covers more of the codebase.

Pure and deterministic: it reuses the embeddings the vector store already computed
(carried on each result's ``metadata['_embedding']``); if those are missing it
falls back to the input order, so it can never fail retrieval.
"""

from __future__ import annotations

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.project_memory import cosine_similarity

# Relevance-vs-diversity trade-off: 1.0 = pure relevance, 0.0 = pure diversity.
DEFAULT_LAMBDA = 0.7
EMBEDDING_KEY = "_embedding"


def mmr_select(
    query_vec: list[float],
    candidates: list[ContextSearchResult],
    k: int,
    lambda_: float = DEFAULT_LAMBDA,
) -> list[ContextSearchResult]:
    """Select up to ``k`` chunks maximizing relevance to ``query_vec`` while
    penalizing similarity to already-selected chunks. Falls back to the first
    ``k`` candidates when embeddings are unavailable."""
    if k <= 0 or not candidates:
        return []
    vecs: list[list[float] | None] = [
        (c.metadata or {}).get(EMBEDDING_KEY) for c in candidates
    ]
    if any(v is None for v in vecs):
        return candidates[:k]
    relevance = [cosine_similarity(query_vec, v) for v in vecs]  # type: ignore[arg-type]

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < k:
        best_index: int | None = None
        best_score: float | None = None
        for i in remaining:
            if not selected:
                score = relevance[i]
            else:
                max_sim = max(cosine_similarity(vecs[i], vecs[j]) for j in selected)  # type: ignore[arg-type]
                score = lambda_ * relevance[i] - (1.0 - lambda_) * max_sim
            if best_score is None or score > best_score:
                best_score = score
                best_index = i
        assert best_index is not None
        selected.append(best_index)
        remaining.remove(best_index)
    return [candidates[i] for i in selected]
