"""Background enrichment orchestration: gated off by default, bounded, idempotent,
and fail-open per chunk. Uses fakes for the vector store, embedder and LLM."""

from types import SimpleNamespace

from app.core.domain.chunking import build_contextual_chunk
from app.core.domain.contextual_enrichment import ENRICHMENT_PREFIX
from app.core.domain.indexing import SourceChunk
from app.core.use_cases.enrich_workspace_context import (
    EnrichWorkspaceContextInput,
    EnrichWorkspaceContextUseCase,
)

_WS = SimpleNamespace(id="w1", project_path="/p")


class _WSRepo:
    def get(self, wid):
        return _WS if wid == "w1" else None


class _ScanRepo:
    def __init__(self, files):
        self._files = files

    def get_latest_scan(self, wid):
        return SimpleNamespace(files=self._files) if self._files is not None else None


class _StatusRepo:
    def __init__(self, chunks_count):
        self._c = chunks_count

    def get(self, wid):
        return SimpleNamespace(chunks_count=self._c)


class _Embed:
    provider_name = "fake"
    model_name = "fake"
    embedding_dimension = 3

    def embed_text(self, text):
        self.last_text = text
        return [0.1, 0.2, 0.3]


class _LLM:
    def __init__(self, replies=None, raise_on=None):
        self._replies = list(replies) if replies else []
        self._raise_on = raise_on or set()
        self.calls = 0

    def generate(self, prompt, **kw):
        self.calls += 1
        if self.calls in self._raise_on:
            raise RuntimeError("model boom")
        return self._replies.pop(0) if self._replies else "situated near the top of the file"


class _Factory:
    def __init__(self, llm):
        self._llm = llm

    def create(self, provider=None, model=None):
        return self._llm


class _VS:
    def __init__(self, chunks_by_path):
        self._chunks = chunks_by_path
        self.upserts = []

    def get_source_chunks(self, wid, path):
        return self._chunks.get(path, [])

    def upsert_chunks(self, workspace_id, chunks, embeddings, **kw):
        self.upserts.append(SimpleNamespace(chunks=chunks, embeddings=embeddings, kw=kw))


def _md_file(path="guide.md", parts=3):
    files = [SimpleNamespace(path=path, detected_type="markdown", extension="md")]
    chunks = [
        SourceChunk(
            chunk_index=i,
            chunk_id=f"w1:{path}:{i}",
            content=build_contextual_chunk(
                f"Some documentation prose paragraph number {i} with detail.",
                source_path=path,
                position=i + 1,
                total=parts,
                file_type="markdown",
                extension="md",
            ),
        )
        for i in range(parts)
    ]
    return files, {path: chunks}


def _use_case(files, chunks_by_path, *, chunks_count, llm, enabled=True):
    return EnrichWorkspaceContextUseCase(
        workspace_repository=_WSRepo(),
        project_scan_repository=_ScanRepo(files),
        index_status_repository=_StatusRepo(chunks_count),
        vector_store=_VS(chunks_by_path),
        embedding_provider=_Embed(),
        llm_provider_factory=_Factory(llm) if llm is not None else None,
        enabled=enabled,
    )


def test_disabled_is_inert():
    files, chunks = _md_file()
    uc = _use_case(files, chunks, chunks_count=100, llm=_LLM(), enabled=False)
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    assert result.enabled is False
    assert (result.examined_chunks, result.enriched_chunks) == (0, 0)
    # Nothing was written.
    assert uc.vector_store.upserts == []


def test_happy_path_enriches_and_reembeds_each_target():
    files, chunks = _md_file(parts=3)
    llm = _LLM()
    # chunks_count=100 → fraction cap 10 → all 3 doc chunks are enriched.
    uc = _use_case(files, chunks, chunks_count=100, llm=llm)
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    assert result.enabled is True
    assert result.enriched_chunks == 3
    assert result.documents_touched == 1
    assert len(uc.vector_store.upserts) == 3
    # Each re-embedded chunk carries the context marker and keeps its id.
    stored = uc.vector_store.upserts[0].chunks[0]
    assert stored.id == "w1:guide.md:0"
    assert f"{ENRICHMENT_PREFIX}" in stored.content
    assert stored.metadata["enriched"] == "1"


def test_already_enriched_chunk_is_not_redone():
    path = "guide.md"
    files = [SimpleNamespace(path=path, detected_type="markdown", extension="md")]
    enriched_body = f"[source: {path} · part 1/2]\n{ENRICHMENT_PREFIX}already]\nbody one"
    chunks = {
        path: [
            SourceChunk(chunk_index=0, chunk_id=f"w1:{path}:0", content=enriched_body),
            SourceChunk(
                chunk_index=1,
                chunk_id=f"w1:{path}:1",
                content=build_contextual_chunk(
                    "second paragraph",
                    source_path=path,
                    position=2,
                    total=2,
                    file_type="markdown",
                    extension="md",
                ),
            ),
        ]
    }
    uc = _use_case(files, chunks, chunks_count=100, llm=_LLM())
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    # Only the not-yet-enriched chunk is touched.
    assert result.enriched_chunks == 1
    assert uc.vector_store.upserts[0].chunks[0].id == "w1:guide.md:1"


def test_empty_note_is_skipped_not_written():
    files, chunks = _md_file(parts=2)
    uc = _use_case(files, chunks, chunks_count=100, llm=_LLM(replies=["   ", "   "]))
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    assert result.enriched_chunks == 0
    assert result.skipped_chunks == 2
    assert uc.vector_store.upserts == []


def test_model_failure_on_one_chunk_is_fail_open():
    files, chunks = _md_file(parts=3)
    # Second generate() raises; the run must continue and enrich the other two.
    uc = _use_case(files, chunks, chunks_count=100, llm=_LLM(raise_on={2}))
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    assert result.enriched_chunks == 2
    assert result.skipped_chunks == 1


def test_cap_limits_the_number_enriched():
    files, chunks = _md_file(parts=8)
    uc = _use_case(files, chunks, chunks_count=1000, llm=_LLM())
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1", max_chunks=2))
    assert result.examined_chunks == 2
    assert result.enriched_chunks == 2


def test_no_scan_returns_enabled_but_empty():
    uc = _use_case(None, {}, chunks_count=0, llm=_LLM())
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    assert result.enabled is True
    assert result.examined_chunks == 0


def test_non_indexable_files_are_ignored():
    files = [SimpleNamespace(path="logo.png", detected_type="binary", extension="png")]
    uc = _use_case(files, {}, chunks_count=0, llm=_LLM())
    result = uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    assert result.examined_chunks == 0
    assert uc.vector_store.upserts == []


def test_embedded_text_leads_with_context_not_provenance_header():
    files, chunks = _md_file(parts=3)
    embed = _Embed()
    uc = EnrichWorkspaceContextUseCase(
        workspace_repository=_WSRepo(),
        project_scan_repository=_ScanRepo(files),
        index_status_repository=_StatusRepo(100),
        vector_store=_VS(chunks),
        embedding_provider=embed,
        llm_provider_factory=_Factory(_LLM()),
        enabled=True,
    )
    uc.execute(EnrichWorkspaceContextInput(workspace_id="w1"))
    # The last text handed to the embedder starts with the context line, no [source:].
    assert embed.last_text.startswith(ENRICHMENT_PREFIX)
    assert "[source: " not in embed.last_text


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
