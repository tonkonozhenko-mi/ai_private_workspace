"""Incremental (changed-files-only) re-index by content hash."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_index_manifest_repository import (
    InMemoryIndexManifestRepository,
)
from app.adapters.memory.in_memory_index_status_repository import (
    InMemoryIndexStatusRepository,
)
from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.use_cases.index_workspace import IndexWorkspaceInput, IndexWorkspaceUseCase


class _WSRepo:
    def get(self, wid):
        return SimpleNamespace(id=wid, project_path="/p") if wid == "w1" else None


class _ScanRepo:
    def __init__(self, files):
        self._files = files

    def set_files(self, files):
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
        self.contents = contents  # {path: text}

    def read_text_file(self, root_path, relative_path):
        return self.contents.get(relative_path, "")


class _Embed:
    provider_name = "fake"
    model_name = "fake-embed"
    embedding_dimension = 3

    def embed_text(self, text):
        # Deterministic tiny vector; content-dependent so different files differ.
        return [float(len(text) % 7), float(len(text) % 5), 1.0]


def _file(path):
    return ProjectFile(path=path, extension=".md", size_bytes=10, detected_type="markdown")


def _use_case(scan_repo, fs, vector, status, manifest):
    return IndexWorkspaceUseCase(
        workspace_repository=_WSRepo(),
        project_scan_repository=scan_repo,
        file_system=fs,
        embedding_provider=_Embed(),
        vector_store=vector,
        index_status_repository=status,
        manifest_repository=manifest,
    )


def _paths_in_store(vector, wid):
    return sorted({c.source_path for c, _ in vector._chunks.get(wid, [])})


def test_full_then_incremental_reindexes_only_changed():
    files = [_file("a.md"), _file("b.md"), _file("c.md")]
    contents = {"a.md": "alpha content", "b.md": "beta content", "c.md": "gamma content"}
    scan = _ScanRepo(files)
    fs = _FS(contents)
    vector = InMemoryVectorStore()
    status = InMemoryIndexStatusRepository()
    manifest = InMemoryIndexManifestRepository()
    uc = _use_case(scan, fs, vector, status, manifest)

    # 1) Full index populates the manifest and the vector store.
    uc.execute(IndexWorkspaceInput(workspace_id="w1"))
    assert _paths_in_store(vector, "w1") == ["a.md", "b.md", "c.md"]
    assert set(manifest.get("w1")) == {"a.md", "b.md", "c.md"}
    a_hash_before = manifest.get("w1")["a.md"]["hash"]

    # 2) Change only b.md; incremental should re-embed just b.md.
    fs.contents["b.md"] = "beta content CHANGED with new words"
    result = uc.execute_changed(IndexWorkspaceInput(workspace_id="w1"))
    assert result.reindexed_files == 1
    assert result.unchanged_files == 2
    assert result.removed_files == 0
    assert [d.source_path for d in result.documents] == ["b.md"]
    # a.md's hash untouched; b.md's hash refreshed.
    assert manifest.get("w1")["a.md"]["hash"] == a_hash_before
    assert manifest.get("w1")["b.md"]["hash"] != a_hash_before
    # All three still present in the store.
    assert _paths_in_store(vector, "w1") == ["a.md", "b.md", "c.md"]


def test_incremental_removes_deleted_file_chunks():
    files = [_file("a.md"), _file("b.md")]
    contents = {"a.md": "alpha", "b.md": "beta"}
    scan = _ScanRepo(files)
    fs = _FS(contents)
    vector = InMemoryVectorStore()
    status = InMemoryIndexStatusRepository()
    manifest = InMemoryIndexManifestRepository()
    uc = _use_case(scan, fs, vector, status, manifest)
    uc.execute(IndexWorkspaceInput(workspace_id="w1"))

    # b.md disappears from the project.
    scan.set_files([_file("a.md")])
    result = uc.execute_changed(IndexWorkspaceInput(workspace_id="w1"))
    assert result.removed_files == 1
    assert _paths_in_store(vector, "w1") == ["a.md"]
    assert set(manifest.get("w1")) == {"a.md"}


def test_incremental_falls_back_to_full_without_manifest():
    files = [_file("a.md")]
    scan = _ScanRepo(files)
    fs = _FS({"a.md": "alpha"})
    vector = InMemoryVectorStore()
    status = InMemoryIndexStatusRepository()
    manifest = InMemoryIndexManifestRepository()
    uc = _use_case(scan, fs, vector, status, manifest)

    # No prior index → manifest empty → execute_changed does a full index.
    result = uc.execute_changed(IndexWorkspaceInput(workspace_id="w1"))
    assert result.reindexed_files == 1
    assert _paths_in_store(vector, "w1") == ["a.md"]
    assert set(manifest.get("w1")) == {"a.md"}


def test_unchanged_project_reindexes_nothing():
    files = [_file("a.md"), _file("b.md")]
    scan = _ScanRepo(files)
    fs = _FS({"a.md": "alpha", "b.md": "beta"})
    vector = InMemoryVectorStore()
    uc = _use_case(
        scan, fs, vector, InMemoryIndexStatusRepository(), InMemoryIndexManifestRepository()
    )
    uc.execute(IndexWorkspaceInput(workspace_id="w1"))
    result = uc.execute_changed(IndexWorkspaceInput(workspace_id="w1"))
    assert result.reindexed_files == 0
    assert result.unchanged_files == 2
    assert result.chunks_indexed == 0
