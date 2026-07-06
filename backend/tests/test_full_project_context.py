from app.adapters.memory.in_memory_index_manifest_repository import (
    InMemoryIndexManifestRepository,
)
from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.core.domain.context_budget import project_fits_whole_context
from app.core.domain.indexing import TextChunk
from app.core.use_cases.ask_workspace_question import (
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionUseCase,
)

WS = "ws"


class _Status:
    def __init__(self, chunks_count: int) -> None:
        self.chunks_count = chunks_count


class _StatusRepo:
    def __init__(self, chunks_count: int, *, boom: bool = False) -> None:
        self._status = _Status(chunks_count)
        self._boom = boom

    def get(self, workspace_id: str):
        if self._boom:
            raise RuntimeError("status unavailable")
        return self._status


class _LLM:
    context_window = 8192


def _use_case(store, manifest, status_repo) -> AskWorkspaceQuestionUseCase:
    return AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=None,
        vector_store=store,
        llm_provider_factory=None,
        index_status_repository=status_repo,
        index_manifest_repository=manifest,
    )


def _seed(store, manifest, files: dict[str, list[str]]) -> None:
    chunks = []
    entries = {}
    for path, bodies in files.items():
        for i, body in enumerate(bodies):
            chunks.append(
                TextChunk(
                    id=f"{WS}:{path}:{i}",
                    workspace_id=WS,
                    source_path=path,
                    chunk_index=i,
                    content=body,
                    token_estimate=1,
                    metadata={},
                )
            )
        entries[path] = {"hash": "h", "chunks": len(bodies)}
    store.upsert_chunks(WS, chunks, [[0.1]] * len(chunks))
    manifest.replace_all(WS, entries)


# --- pure decision -------------------------------------------------------


def test_fits_whole_true_for_small_project():
    assert project_fits_whole_context(3, 8192) is True


def test_fits_whole_false_for_large_project():
    assert project_fits_whole_context(500, 8192) is False


def test_fits_whole_false_for_empty_index():
    assert project_fits_whole_context(0, 8192) is False


def test_bigger_window_admits_more_chunks():
    # a chunk count that overflows 8k fits a 128k window
    assert project_fits_whole_context(100, 8192) is False
    assert project_fits_whole_context(100, 131072) is True


# --- enumeration + trigger ----------------------------------------------


def test_full_context_returns_all_chunks_ordered_with_citations():
    store, manifest = InMemoryVectorStore(), InMemoryIndexManifestRepository()
    _seed(store, manifest, {"b.py": ["b0", "b1"], "a.py": ["a0", "a1"]})
    uc = _use_case(store, manifest, _StatusRepo(4))
    results = uc._full_project_context(WS)
    # ordered by file then chunk index
    assert [(r.source_path, r.content) for r in results] == [
        ("a.py", "a0"),
        ("a.py", "a1"),
        ("b.py", "b0"),
        ("b.py", "b1"),
    ]
    # citations preserved
    assert all(r.source_path and r.chunk_id for r in results)


def test_maybe_full_context_fires_on_small_project():
    store, manifest = InMemoryVectorStore(), InMemoryIndexManifestRepository()
    _seed(store, manifest, {"a.py": ["a0", "a1"]})
    uc = _use_case(store, manifest, _StatusRepo(2))
    out = uc._maybe_full_project_context(_input(), _LLM())
    assert out is not None
    assert len(out) == 2


def test_maybe_full_context_none_on_large_project():
    store, manifest = InMemoryVectorStore(), InMemoryIndexManifestRepository()
    _seed(store, manifest, {"a.py": ["x"]})
    uc = _use_case(store, manifest, _StatusRepo(9999))
    assert uc._maybe_full_project_context(_input(), _LLM()) is None


def test_maybe_full_context_disabled_without_manifest():
    store = InMemoryVectorStore()
    uc = AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=None,
        vector_store=store,
        llm_provider_factory=None,
        index_status_repository=_StatusRepo(2),
        index_manifest_repository=None,
    )
    assert uc._maybe_full_project_context(_input(), _LLM()) is None


def test_maybe_full_context_fail_open_on_status_error():
    store, manifest = InMemoryVectorStore(), InMemoryIndexManifestRepository()
    _seed(store, manifest, {"a.py": ["a0"]})
    uc = _use_case(store, manifest, _StatusRepo(2, boom=True))
    assert uc._maybe_full_project_context(_input(), _LLM()) is None


def _input() -> AskWorkspaceQuestionInput:
    return AskWorkspaceQuestionInput(workspace_id=WS, question="what is this project?")
