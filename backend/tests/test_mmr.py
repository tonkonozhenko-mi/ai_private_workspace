from app.core.domain.indexing import ContextSearchResult
from app.core.domain.mmr import EMBEDDING_KEY, mmr_select


def _c(chunk_id: str, vec):
    return ContextSearchResult(
        chunk_id=chunk_id,
        source_path=f"{chunk_id}.py",
        content=chunk_id,
        score=1.0,
        metadata={EMBEDDING_KEY: vec},
    )


def test_mmr_picks_diverse_over_near_duplicate():
    # a and b are near-identical; c is different. Query closest to a.
    cands = [_c("a", [1.0, 0.0]), _c("b", [0.99, 0.01]), _c("c", [0.0, 1.0])]
    chosen = mmr_select([1.0, 0.0], cands, k=2, lambda_=0.3)
    ids = [r.chunk_id for r in chosen]
    assert ids[0] == "a"  # most relevant first
    assert ids[1] == "c"  # diversity beats the near-duplicate b


def test_mmr_falls_back_without_embeddings():
    cands = [
        ContextSearchResult(chunk_id=str(i), source_path="f", content="x", score=1.0, metadata={})
        for i in range(4)
    ]
    chosen = mmr_select([1.0], cands, k=2)
    assert [r.chunk_id for r in chosen] == ["0", "1"]


def test_mmr_empty_and_zero_k():
    assert mmr_select([1.0], [], k=3) == []
    assert mmr_select([1.0], [_c("a", [1.0])], k=0) == []


def test_mmr_caps_at_k():
    cands = [_c(str(i), [float(i), 1.0]) for i in range(6)]
    chosen = mmr_select([1.0, 0.0], cands, k=3)
    assert len(chosen) == 3
