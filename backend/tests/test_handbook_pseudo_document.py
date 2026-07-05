"""Handbook/digest indexed as a pseudo-document (P3)."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_index_manifest_repository import (
    InMemoryIndexManifestRepository,
)
from app.adapters.memory.in_memory_index_status_repository import (
    InMemoryIndexStatusRepository,
)
from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.use_cases.index_workspace import (
    HANDBOOK_PSEUDO_PATH,
    IndexWorkspaceInput,
    IndexWorkspaceUseCase,
)

HANDBOOK = "# Project Foo\n\nFoo is a payments service. It deploys to AWS via Terraform."


class _WSRepo:
    def get(self, wid):
        return SimpleNamespace(id=wid, project_path="/p") if wid == "w1" else None


class _ScanRepo:
    def __init__(self, files):
        self._files = files

    def get_latest_scan(self, wid):
        return ProjectScanResult(
            project_path="/p",
            total_files=len(self._files),
            scanned_files=len(self._files),
            skipped_files=0,
            total_size_bytes=0,
            detected_skills=[],
            files=self._files,
        )


class _FS:
    def __init__(self, contents):
        self.contents = contents

    def read_text_file(self, root_path, relative_path):
        return self.contents.get(relative_path, "")


class _Embed:
    provider_name = "fake"
    model_name = "fake-embed"
    embedding_dimension = 3

    def embed_text(self, text):
        return [float(len(text) % 7), float(len(text) % 5), 1.0]


def _file(path):
    return ProjectFile(path=path, extension=".md", size_bytes=10, detected_type="markdown")


def _use_case(handbook, *, manifest=None):
    return IndexWorkspaceUseCase(
        workspace_repository=_WSRepo(),
        project_scan_repository=_ScanRepo([_file("a.md")]),
        file_system=_FS({"a.md": "alpha content"}),
        embedding_provider=_Embed(),
        vector_store=InMemoryVectorStore(),
        index_status_repository=InMemoryIndexStatusRepository(),
        manifest_repository=manifest or InMemoryIndexManifestRepository(),
        handbook_provider=handbook,
    )


def _paths(vector, wid):
    return sorted({c.source_path for c, _ in vector._chunks.get(wid, [])})


# --- _handbook_pseudo_chunks in isolation -------------------------------


def test_pseudo_chunks_built_from_provider_text():
    uc = _use_case(lambda ws: HANDBOOK)
    chunks, file_hash = uc._handbook_pseudo_chunks("w1")
    assert chunks and file_hash
    assert all(c.source_path == HANDBOOK_PSEUDO_PATH for c in chunks)
    assert chunks[0].id == f"w1:{HANDBOOK_PSEUDO_PATH}:0"
    assert "payments service" in "".join(c.content for c in chunks)
    assert chunks[0].metadata.get("pseudo_document") == "handbook"


def test_pseudo_chunks_none_provider():
    uc = _use_case(None)
    assert uc._handbook_pseudo_chunks("w1") == ([], None)


def test_pseudo_chunks_empty_text():
    uc = _use_case(lambda ws: "   ")
    assert uc._handbook_pseudo_chunks("w1") == ([], None)


def test_pseudo_chunks_provider_error_is_fail_open():
    def boom(ws):
        raise RuntimeError("no graph")

    uc = _use_case(boom)
    assert uc._handbook_pseudo_chunks("w1") == ([], None)


# --- full + incremental index include the pseudo-document ---------------


def test_full_index_includes_handbook_pseudo_document():
    uc = _use_case(lambda ws: HANDBOOK)
    result = uc.execute(IndexWorkspaceInput(workspace_id="w1"))
    assert HANDBOOK_PSEUDO_PATH in _paths(uc.vector_store, "w1")
    assert HANDBOOK_PSEUDO_PATH in uc.manifest_repository.get("w1")
    assert any(d.source_path == HANDBOOK_PSEUDO_PATH for d in result.documents)


def test_full_index_without_provider_has_no_pseudo_document():
    uc = _use_case(None)
    uc.execute(IndexWorkspaceInput(workspace_id="w1"))
    assert HANDBOOK_PSEUDO_PATH not in _paths(uc.vector_store, "w1")


def test_incremental_reembeds_handbook_only_when_text_changes():
    text = {"v": HANDBOOK}
    uc = _use_case(lambda ws: text["v"])
    uc.execute(IndexWorkspaceInput(workspace_id="w1"))

    # Unchanged handbook → not re-embedded.
    r1 = uc.execute_changed(IndexWorkspaceInput(workspace_id="w1"))
    assert HANDBOOK_PSEUDO_PATH not in {d.source_path for d in r1.documents}

    # Changed handbook → re-embedded.
    text["v"] = HANDBOOK + "\n\nAlso uses Redis for caching."
    r2 = uc.execute_changed(IndexWorkspaceInput(workspace_id="w1"))
    assert HANDBOOK_PSEUDO_PATH in {d.source_path for d in r2.documents}
    assert HANDBOOK_PSEUDO_PATH in uc.manifest_repository.get("w1")
