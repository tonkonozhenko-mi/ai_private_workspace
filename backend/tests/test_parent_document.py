from app.core.domain.indexing import ContextSearchResult, SourceChunk
from app.core.domain.parent_document import expand_to_parents

WS = "ws"


def _result(path: str, idx: int, content: str, score: float) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=f"{WS}:{path}:{idx}",
        source_path=path,
        content=content,
        score=score,
        metadata={"source_path": path},
    )


def _file(path: str, bodies: list[str]) -> list[SourceChunk]:
    return [
        SourceChunk(chunk_index=i, chunk_id=f"{WS}:{path}:{i}", content=body)
        for i, body in enumerate(bodies)
    ]


def _fetcher(files: dict[str, list[SourceChunk]]):
    return lambda path: files.get(path, [])


def test_expands_with_neighbours_same_file():
    files = {"a.py": _file("a.py", ["c0", "c1-hit", "c2"])}
    results = [_result("a.py", 1, "c1-hit", 0.9)]
    out = expand_to_parents(results, _fetcher(files))
    assert len(out) == 1
    # neighbours ±1 joined around the hit
    assert "c0" in out[0].content
    assert "c1-hit" in out[0].content
    assert "c2" in out[0].content
    # citation identity anchors on the first chunk of the span
    assert out[0].chunk_id == "ws:a.py:0"
    assert out[0].score == 0.9


def test_overlapping_seeds_merge_into_one_span():
    files = {"a.py": _file("a.py", ["c0", "c1", "c2", "c3"])}
    # two hits whose ±1 windows overlap (1 and 2) → single merged span 0..3
    results = [_result("a.py", 1, "c1", 0.5), _result("a.py", 2, "c2", 0.9)]
    out = expand_to_parents(results, _fetcher(files))
    assert len(out) == 1
    assert out[0].score == 0.9  # span takes the max seed score
    for body in ("c0", "c1", "c2", "c3"):
        assert body in out[0].content


def test_separate_files_stay_separate_and_score_ordered():
    files = {
        "a.py": _file("a.py", ["a0", "a1", "a2"]),
        "b.py": _file("b.py", ["b0", "b1", "b2"]),
    }
    results = [_result("b.py", 1, "b1", 0.3), _result("a.py", 1, "a1", 0.8)]
    out = expand_to_parents(results, _fetcher(files))
    assert [r.source_path for r in out] == ["a.py", "b.py"]  # score desc


def test_missing_file_passes_result_through_unchanged():
    results = [_result("gone.py", 1, "orig", 0.7)]
    out = expand_to_parents(results, _fetcher({}))
    assert out == results


def test_fetch_error_is_fail_open():
    def boom(_path: str):
        raise RuntimeError("store down")

    results = [_result("a.py", 1, "orig", 0.7)]
    out = expand_to_parents(results, boom)
    assert out == results


def test_first_chunk_header_kept_neighbours_stripped():
    header = "[source: a.py › fn · part 2/3]"
    files = {
        "a.py": _file(
            "a.py",
            [
                f"{header}\nbody0",
                f"{header}\nbody1",
                f"{header}\nbody2",
            ],
        )
    }
    results = [_result("a.py", 1, f"{header}\nbody1", 0.9)]
    out = expand_to_parents(results, _fetcher(files))
    content = out[0].content
    # header appears once (first chunk keeps it; neighbours stripped)
    assert content.count("[source:") == 1
    for body in ("body0", "body1", "body2"):
        assert body in content


def test_max_chars_stops_growth_but_keeps_seed():
    files = {"a.py": _file("a.py", ["x" * 100, "SEED", "y" * 100])}
    results = [_result("a.py", 1, "SEED", 0.9)]
    out = expand_to_parents(results, _fetcher(files), radius=1, max_chars=10)
    # seed always present; oversized neighbours skipped by the char cap
    assert "SEED" in out[0].content
    assert len(out[0].content) <= 120


def test_radius_zero_is_no_expansion():
    files = {"a.py": _file("a.py", ["c0", "c1", "c2"])}
    results = [_result("a.py", 1, "c1", 0.9)]
    out = expand_to_parents(results, _fetcher(files), radius=0)
    assert out[0].content == "c1"
    assert out[0].chunk_id == "ws:a.py:1"


def test_empty_input():
    assert expand_to_parents([], _fetcher({})) == []
