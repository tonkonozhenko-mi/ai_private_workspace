"""Per-file cap keeps retrieved context from being dominated by one file."""

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.retrieval_diversity import limit_per_source


def _r(path: str, i: int) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=f"{path}:{i}", source_path=path, content=f"c{i}", score=1.0 - i * 0.01, metadata={}
    )


def test_caps_chunks_per_source_preserving_order():
    results = [_r("a.md", 0), _r("a.md", 1), _r("a.md", 2), _r("a.md", 3), _r("b.tf", 0)]
    kept = limit_per_source(results, max_per_source=3)
    paths = [r.source_path for r in kept]
    assert paths.count("a.md") == 3  # 4th a.md dropped
    assert "b.tf" in paths
    # Order preserved and best (highest-scored) chunks of a.md kept.
    assert [r.chunk_id for r in kept if r.source_path == "a.md"] == ["a.md:0", "a.md:1", "a.md:2"]


def test_all_same_file_is_capped():
    results = [_r("only.md", i) for i in range(6)]
    assert len(limit_per_source(results, max_per_source=3)) == 3


def test_cap_of_zero_disables():
    results = [_r("a.md", 0), _r("a.md", 1)]
    assert limit_per_source(results, max_per_source=0) == results


def test_mixed_files_under_cap_unchanged():
    results = [_r("a", 0), _r("b", 0), _r("c", 0)]
    assert limit_per_source(results, max_per_source=3) == results
