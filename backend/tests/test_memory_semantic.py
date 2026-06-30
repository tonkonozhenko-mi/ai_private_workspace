from app.core.domain.project_memory import (
    MemoryItem,
    cosine_similarity,
    rank_memory_by_similarity,
)
from app.core.use_cases.compose_project_context import ComposeProjectContextUseCase


def _item(item_id: str, text: str, pinned: bool = False) -> MemoryItem:
    return MemoryItem(
        id=item_id,
        workspace_id="w",
        kind="note",
        text=text,
        source="user",
        created_at="2026-06-01T00:00:00Z",
        pinned=pinned,
    )


def test_cosine_basic():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_rank_orders_by_similarity_then_pin():
    items = [_item("a", "a"), _item("b", "b"), _item("c", "c", pinned=True)]
    query = [1.0, 0.0]
    vecs = [[0.1, 1.0], [0.9, 0.1], [0.0, 1.0]]  # b most similar to query
    ranked = rank_memory_by_similarity(items, query, vecs, limit=3)
    # Pinned 'c' first regardless of similarity; then 'b' (more similar) before 'a'.
    assert ranked[0].id == "c"
    assert [i.id for i in ranked[1:]] == ["b", "a"]


def test_rank_falls_back_when_vectors_missing():
    items = [_item("a", "a"), _item("b", "b")]
    ranked = rank_memory_by_similarity(items, [1.0], [[1.0]], limit=5)  # mismatched lengths
    assert [i.id for i in ranked] == ["a", "b"]


class _FakeEmbedder:
    """Embeds text to a 2-D vector keyed off a marker word, so 'production' and a
    memory mentioning 'production' land close, and unrelated text lands far."""

    provider_name = "fake"
    model_name = "fake"

    def embed_text(self, text: str) -> list[float]:
        t = text.lower()
        return [1.0 if "production" in t else 0.0, 1.0 if "billing" in t else 0.0]


class _MemRepo:
    def __init__(self, items):
        self._items = items

    def list(self, workspace_id):
        return self._items


class _GraphRepo:
    def get_latest_graph(self, workspace_id):
        return None


def test_compose_semantic_rerank_surfaces_related_memory():
    # 8 distractors + one production note; keyword recall returns many, semantic
    # rerank must pull the production note to the top for a production question.
    items = [_item(f"d{i}", f"unrelated note number {i} about caching") for i in range(8)]
    items.append(_item("prod", "the production environment runs in us-east-1"))
    uc = ComposeProjectContextUseCase(
        _MemRepo(items), _GraphRepo(), embedding_provider=_FakeEmbedder()
    )
    selected = uc._select_memory(items, "how is production deployed?", limit=3)
    assert any(i.id == "prod" for i in selected)


def test_compose_select_memory_without_embedder_is_keyword():
    items = [_item("a", "production note"), _item("b", "other note")]
    uc = ComposeProjectContextUseCase(_MemRepo(items), _GraphRepo())  # no embedder
    selected = uc._select_memory(items, "production", limit=6)
    # Keyword recall keeps only the item overlapping the query.
    assert {i.id for i in selected} == {"a"}


class _FractionalEmbedder:
    """Returns fixed vectors so we can control exact cosine similarity to the
    query and test the semantic noise floor."""

    provider_name = "fake"
    model_name = "fake"

    def embed_text(self, text: str) -> list[float]:
        t = text.lower()
        if "queryvec" in t:
            return [1.0, 0.0]
        if "target" in t:
            return [0.95, 0.31]  # cosine ~0.95 with query → kept
        if "noise" in t:
            return [0.20, 0.98]  # cosine ~0.20 with query → below 0.25 floor
        return [0.0, 1.0]


def test_semantic_noise_below_floor_is_dropped():
    # A keyword anchor ("deploy") keeps keyword recall from falling back to "all";
    # target/noise enter only via semantic, where the floor must drop the noise.
    items = [
        _item("kw", "deploy pipeline"),  # keyword hit for "deploy"
        _item("target", "target note"),  # semantic ~0.95 → kept
        _item("noise", "noise note"),  # semantic ~0.20 → dropped by the floor
    ]
    uc = ComposeProjectContextUseCase(
        _MemRepo(items), _GraphRepo(), embedding_provider=_FractionalEmbedder()
    )
    selected = uc._select_memory(items, "queryvec deploy", limit=6)
    ids = {i.id for i in selected}
    assert "kw" in ids and "target" in ids  # keyword + high-similarity semantic
    assert "noise" not in ids  # below the floor → not a semantic candidate
