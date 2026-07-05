from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.domain.chunking import (
    build_contextual_chunk,
    chunk_document,
    estimate_tokens,
    strip_contextual_header,
)
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.indexing import (
    IncrementalIndexResult,
    IndexChangePreview,
    IndexedDocumentSummary,
    TextChunk,
    WorkspaceIndexResult,
    content_hash,
)
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.domain.relevance_calibration import calibrate_from_embeddings
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.file_system import FileSystemPort
from app.core.ports.index_manifest_repository import IndexManifestRepositoryPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)

# Synthetic "file" holding the deterministic project handbook / deep-analysis
# digest. Indexing it as a pseudo-document lets broad "what is this project about"
# questions find the summary through normal retrieval, instead of relying on the
# right source file happening to rank. Namespaced so it never collides with a real
# path; retrieval treats it like any other source (citation shows this name).
HANDBOOK_PSEUDO_PATH = "__project_handbook__"
HANDBOOK_PSEUDO_TYPE = "markdown"

INDEXABLE_FILE_TYPES = {
    "markdown",
    "yaml",
    "json",
    "terraform",
    "terragrunt",
    "python",
    "docker",
    "gitlab_ci",
    "github_actions",
    "kubernetes",
    "helm",
    "shell",
}


@dataclass(frozen=True)
class IndexWorkspaceInput:
    workspace_id: str
    cancellation_check: Callable[[], bool] | None = None
    progress_callback: Callable[[int, int, str], None] | None = None


class IndexWorkspaceNotFoundError(ValueError):
    pass


class IndexWorkspaceScanRequiredError(ValueError):
    pass


class IndexWorkspaceCancelledError(RuntimeError):
    pass


class IndexWorkspaceUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        index_status_repository: IndexStatusRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
        manifest_repository: IndexManifestRepositoryPort | None = None,
        handbook_provider: Callable[[str], str | None] | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.index_status_repository = index_status_repository
        self.timeline_repository = timeline_repository
        # Optional: records {path: hash} of what is indexed, enabling incremental
        # re-index of only changed files. When absent, indexing stays full.
        self.manifest_repository = manifest_repository
        # Optional (workspace_id) -> handbook/digest text. When it yields non-empty
        # text, that text is indexed as a pseudo-document (HANDBOOK_PSEUDO_PATH) so
        # "about this project" questions retrieve it. None = feature off.
        self.handbook_provider = handbook_provider

    def execute(self, request: IndexWorkspaceInput) -> WorkspaceIndexResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise IndexWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise IndexWorkspaceScanRequiredError("Project scan required before indexing workspace")

        try:
            result = self._index_workspace(
                workspace_id=request.workspace_id,
                project_path=workspace.project_path,
                latest_scan=latest_scan,
                cancellation_check=request.cancellation_check,
                progress_callback=request.progress_callback,
            )
        except IndexWorkspaceCancelledError:
            raise
        except Exception as exc:
            self.index_status_repository.save(
                WorkspaceIndexStatus(
                    workspace_id=request.workspace_id,
                    status="failed",
                    indexed_files_count=0,
                    chunks_count=0,
                    skipped_files_count=0,
                    last_indexed_at=datetime.now(UTC).isoformat(),
                    last_error=str(exc),
                )
            )
            raise

        self.index_status_repository.save(
            WorkspaceIndexStatus(
                workspace_id=request.workspace_id,
                status="indexed",
                indexed_files_count=result.indexed_files_count,
                chunks_count=result.chunks_count,
                skipped_files_count=result.skipped_files_count,
                last_indexed_at=datetime.now(UTC).isoformat(),
                last_error=None,
                embedding_model=getattr(self.embedding_provider, "model_name", None),
                relevance_floor=result.relevance_floor,
            )
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="workspace_indexed",
                    title="Workspace indexed",
                    summary=(
                        f"Indexed {result.indexed_files_count} files into "
                        f"{result.chunks_count} chunks."
                    ),
                    metadata={
                        "chunks_count": str(result.chunks_count),
                        "indexed_files_count": str(result.indexed_files_count),
                    },
                )
            )
        return result

    def execute_changed_preview(self, request: IndexWorkspaceInput) -> IndexChangePreview:
        """Count what an incremental re-index would touch — without embedding or
        writing anything. Reads + hashes the indexable files and diffs against the
        manifest, so the UI can show a 'N files changed' hint cheaply."""
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise IndexWorkspaceNotFoundError("Workspace not found")
        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise IndexWorkspaceScanRequiredError("Project scan required before indexing workspace")

        manifest = (
            self.manifest_repository.get(request.workspace_id)
            if self.manifest_repository is not None
            else {}
        )
        current = {f.path: f for f in latest_scan.files if f.detected_type in INDEXABLE_FILE_TYPES}
        changed = new = 0
        for path in current:
            try:
                content = self.file_system.read_text_file(workspace.project_path, path)
            except Exception:  # noqa: BLE001 - a read failure shouldn't break the preview
                content = ""
            prior = manifest.get(path)
            if prior is None:
                new += 1
            elif str(prior.get("hash")) != content_hash(content):
                changed += 1
        removed = len(set(manifest) - set(current))
        unchanged = max(0, len(current) - changed - new)
        return IndexChangePreview(
            workspace_id=request.workspace_id,
            has_index=bool(manifest),
            changed_files=changed,
            new_files=new,
            removed_files=removed,
            unchanged_files=unchanged,
        )

    def execute_changed(self, request: IndexWorkspaceInput) -> IncrementalIndexResult:
        """Re-index only files whose content changed since the last index.

        Reads each indexable file, hashes it, and compares against the manifest:
        re-embeds new/changed files, drops chunks for changed/removed files, and
        leaves unchanged files untouched. Falls back to a full index when there is
        no manifest yet or the embedding model changed (everything must be
        re-embedded then). Never re-indexes the whole repo unnecessarily.
        """
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise IndexWorkspaceNotFoundError("Workspace not found")
        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise IndexWorkspaceScanRequiredError("Project scan required before indexing workspace")

        manifest = (
            self.manifest_repository.get(request.workspace_id)
            if self.manifest_repository is not None
            else {}
        )
        status = self.index_status_repository.get(request.workspace_id)
        current_model = getattr(self.embedding_provider, "model_name", None)
        model_changed = bool(
            status and status.embedding_model and status.embedding_model != current_model
        )
        if not manifest or model_changed:
            full = self.execute(request)
            return IncrementalIndexResult(
                workspace_id=request.workspace_id,
                reindexed_files=full.indexed_files_count,
                removed_files=0,
                unchanged_files=0,
                chunks_indexed=full.chunks_count,
                indexed_files_count=full.indexed_files_count,
                chunks_count=full.chunks_count,
                documents=full.documents,
            )

        result = self._index_changed(
            workspace_id=request.workspace_id,
            project_path=workspace.project_path,
            latest_scan=latest_scan,
            manifest=manifest,
        )
        self.index_status_repository.save(
            WorkspaceIndexStatus(
                workspace_id=request.workspace_id,
                status="indexed",
                indexed_files_count=result.indexed_files_count,
                chunks_count=result.chunks_count,
                skipped_files_count=status.skipped_files_count if status else 0,
                last_indexed_at=datetime.now(UTC).isoformat(),
                last_error=None,
                embedding_model=current_model,
                # Keep the previously-calibrated floor when too few chunks changed
                # to resample a trustworthy one.
                relevance_floor=(
                    result.relevance_floor
                    if result.relevance_floor is not None
                    else (status.relevance_floor if status else None)
                ),
            )
        )
        if self.timeline_repository is not None and (
            result.reindexed_files or result.removed_files
        ):
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="workspace_reindexed",
                    title="Updated the AI's knowledge",
                    summary=(
                        f"Re-indexed {result.reindexed_files} changed file(s); "
                        f"{result.removed_files} removed."
                    ),
                    metadata={
                        "reindexed_files": str(result.reindexed_files),
                        "removed_files": str(result.removed_files),
                    },
                )
            )
        return result

    def _index_changed(
        self,
        workspace_id: str,
        project_path: str,
        latest_scan: ProjectScanResult,
        manifest: dict[str, dict],
    ) -> IncrementalIndexResult:
        current_indexable = {
            f.path: f for f in latest_scan.files if f.detected_type in INDEXABLE_FILE_TYPES
        }
        new_manifest: dict[str, dict] = {}
        reindexed_docs: list[IndexedDocumentSummary] = []
        chunks_to_embed: list[TextChunk] = []
        unchanged = 0

        for path, project_file in current_indexable.items():
            file_chunks, file_hash = self._chunks_for_file(
                workspace_id=workspace_id,
                project_path=project_path,
                project_file=project_file,
            )
            prior = manifest.get(path)
            if not file_chunks:
                # No longer chunkable — leave it out of the manifest so its old
                # chunks (if any) get deleted below.
                continue
            if prior and prior.get("hash") == file_hash:
                unchanged += 1
                new_manifest[path] = dict(prior)
                continue
            reindexed_docs.append(
                IndexedDocumentSummary(source_path=path, chunks_count=len(file_chunks))
            )
            chunks_to_embed.extend(file_chunks)
            new_manifest[path] = {"hash": file_hash, "chunks": len(file_chunks)}

        # Refresh the handbook pseudo-document too: re-embed it only when its text
        # changed (it tracks the map/memory, not any one file).
        handbook_chunks, handbook_hash = self._handbook_pseudo_chunks(workspace_id)
        if handbook_chunks:
            prior = manifest.get(HANDBOOK_PSEUDO_PATH)
            if prior and prior.get("hash") == handbook_hash:
                unchanged += 1
                new_manifest[HANDBOOK_PSEUDO_PATH] = dict(prior)
            else:
                reindexed_docs.append(
                    IndexedDocumentSummary(
                        source_path=HANDBOOK_PSEUDO_PATH,
                        chunks_count=len(handbook_chunks),
                    )
                )
                chunks_to_embed.extend(handbook_chunks)
                new_manifest[HANDBOOK_PSEUDO_PATH] = {
                    "hash": handbook_hash,
                    "chunks": len(handbook_chunks),
                }

        reindexed_paths = {doc.source_path for doc in reindexed_docs}
        removed_or_emptied = set(manifest) - set(new_manifest)
        to_delete = sorted(removed_or_emptied | (reindexed_paths & set(manifest)))
        if to_delete:
            self.vector_store.delete_chunks_by_source_path(workspace_id, to_delete)

        relevance_floor: float | None = None
        if chunks_to_embed:
            embeddings = self._embed_texts(
                [strip_contextual_header(chunk.content) for chunk in chunks_to_embed]
            )
            embedding_dimension = self._embedding_dimension(embeddings)
            self.vector_store.upsert_chunks(
                workspace_id=workspace_id,
                chunks=chunks_to_embed,
                embeddings=embeddings,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=embedding_dimension,
            )
            # Recalibrate only when enough chunks changed to sample a trustworthy
            # background; otherwise None → the caller keeps the previous floor.
            relevance_floor = calibrate_from_embeddings(embeddings)

        if self.manifest_repository is not None:
            self.manifest_repository.replace_all(workspace_id, new_manifest)

        chunks_count = sum(int(entry.get("chunks", 0)) for entry in new_manifest.values())
        return IncrementalIndexResult(
            workspace_id=workspace_id,
            reindexed_files=len(reindexed_docs),
            removed_files=len(removed_or_emptied),
            unchanged_files=unchanged,
            chunks_indexed=len(chunks_to_embed),
            indexed_files_count=len(new_manifest),
            chunks_count=chunks_count,
            documents=reindexed_docs,
            relevance_floor=relevance_floor,
        )

    def _index_workspace(
        self,
        workspace_id: str,
        project_path: str,
        latest_scan: ProjectScanResult,
        cancellation_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> WorkspaceIndexResult:
        documents: list[IndexedDocumentSummary] = []
        chunks: list[TextChunk] = []
        manifest: dict[str, dict] = {}
        skipped_files_count = latest_scan.skipped_files

        total_files = len(latest_scan.files) or 1
        for file_index, project_file in enumerate(latest_scan.files, start=1):
            self._checkpoint(cancellation_check)
            if progress_callback is not None:
                progress_callback(
                    file_index, total_files, f"Reading files: {file_index}/{total_files}"
                )
            if project_file.detected_type not in INDEXABLE_FILE_TYPES:
                skipped_files_count += 1
                continue

            file_chunks, file_hash = self._chunks_for_file(
                workspace_id=workspace_id,
                project_path=project_path,
                project_file=project_file,
            )
            if not file_chunks:
                skipped_files_count += 1
                continue

            documents.append(
                IndexedDocumentSummary(
                    source_path=project_file.path,
                    chunks_count=len(file_chunks),
                )
            )
            chunks.extend(file_chunks)
            manifest[project_file.path] = {"hash": file_hash, "chunks": len(file_chunks)}

        # Index the project handbook/digest as a pseudo-document so broad
        # "what is this project" questions find it through retrieval.
        handbook_chunks, handbook_hash = self._handbook_pseudo_chunks(workspace_id)
        if handbook_chunks:
            documents.append(
                IndexedDocumentSummary(
                    source_path=HANDBOOK_PSEUDO_PATH,
                    chunks_count=len(handbook_chunks),
                )
            )
            chunks.extend(handbook_chunks)
            manifest[HANDBOOK_PSEUDO_PATH] = {
                "hash": handbook_hash,
                "chunks": len(handbook_chunks),
            }

        # Embed the clean chunk bodies (not the provenance headers), so the dense
        # vectors reflect real content; the stored chunks keep their headers.
        embeddings = self._embed_texts(
            [strip_contextual_header(chunk.content) for chunk in chunks],
            cancellation_check=cancellation_check,
            progress_callback=progress_callback,
        )
        self._checkpoint(cancellation_check)
        embedding_dimension = self._embedding_dimension(embeddings)
        if progress_callback is not None:
            total_chunks = len(chunks) or 1
            progress_callback(total_chunks, total_chunks, "Writing vector store...")
        self.vector_store.clear_workspace(
            workspace_id=workspace_id,
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name,
            embedding_dimension=embedding_dimension,
        )
        if chunks:
            self._checkpoint(cancellation_check)
            self.vector_store.upsert_chunks(
                workspace_id=workspace_id,
                chunks=chunks,
                embeddings=embeddings,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=embedding_dimension,
            )

        # The manifest mirrors exactly what we just (re)wrote, so a later
        # incremental re-index can diff against it by content hash.
        if self.manifest_repository is not None:
            self.manifest_repository.replace_all(workspace_id, manifest)

        # Calibrate the abstention floor to this embedding model's own score scale
        # (noise floor of random chunk pairs). None on a tiny index → default is kept.
        relevance_floor = calibrate_from_embeddings(embeddings)

        return WorkspaceIndexResult(
            workspace_id=workspace_id,
            indexed_files_count=len(documents),
            chunks_count=len(chunks),
            skipped_files_count=skipped_files_count,
            documents=documents,
            relevance_floor=relevance_floor,
        )

    # How many chunk bodies to embed per request when the provider supports
    # batch embedding. One round-trip per batch instead of per chunk.
    _EMBED_BATCH = 64

    def _embed_texts(
        self,
        texts: list[str],
        cancellation_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[list[float]]:
        """Embed many texts, using the provider's batch API when available
        (far fewer round-trips), else one call per text. Order is preserved."""
        total = len(texts) or 1
        batch_fn = getattr(self.embedding_provider, "embed_texts", None)
        embeddings: list[list[float]] = []
        if callable(batch_fn):
            for start in range(0, len(texts), self._EMBED_BATCH):
                self._checkpoint(cancellation_check)
                group = texts[start : start + self._EMBED_BATCH]
                embeddings.extend(batch_fn(group))
                done = min(start + len(group), total)
                if progress_callback is not None:
                    progress_callback(done, total, f"Embedding chunks: {done}/{total}")
        else:
            for index, text in enumerate(texts, start=1):
                self._checkpoint(cancellation_check)
                embeddings.append(self.embedding_provider.embed_text(text))
                if progress_callback is not None:
                    progress_callback(index, total, f"Embedding chunks: {index}/{total}")
        return embeddings

    @staticmethod
    def _checkpoint(cancellation_check: Callable[[], bool] | None) -> None:
        if cancellation_check is not None and cancellation_check():
            raise IndexWorkspaceCancelledError("Workspace indexing cancelled")

    def _embedding_dimension(self, embeddings: list[list[float]]) -> int | None:
        if not embeddings:
            return self.embedding_provider.embedding_dimension

        embedding_dimension = len(embeddings[0])
        if embedding_dimension == 0:
            raise ValueError("Embedding provider returned an empty vector")
        if any(len(embedding) != embedding_dimension for embedding in embeddings):
            raise ValueError("Embedding provider returned inconsistent vector dimensions")
        return embedding_dimension

    def _handbook_pseudo_chunks(self, workspace_id: str) -> tuple[list[TextChunk], str | None]:
        """Chunk the project handbook/digest into a pseudo-document, mirroring how
        real files are chunked (contextual headers, ids). Returns ([], None) when
        there's no provider, no text, or the lookup fails — the feature never
        breaks indexing."""
        provider = self.handbook_provider
        if provider is None:
            return [], None
        try:
            text = provider(workspace_id)
        except Exception:  # noqa: BLE001 — the digest is optional, never fail indexing
            return [], None
        text = (text or "").strip()
        if not text:
            return [], None

        file_hash = content_hash(text)
        raw_chunks = chunk_document(text, file_type=HANDBOOK_PSEUDO_TYPE, extension="md")
        total = len(raw_chunks)
        chunks: list[TextChunk] = []
        for chunk_index, chunk_content in enumerate(raw_chunks):
            contextual_content = build_contextual_chunk(
                chunk_content,
                source_path=HANDBOOK_PSEUDO_PATH,
                position=chunk_index + 1,
                total=total,
                file_type=HANDBOOK_PSEUDO_TYPE,
                extension="md",
            )
            chunks.append(
                TextChunk(
                    id=f"{workspace_id}:{HANDBOOK_PSEUDO_PATH}:{chunk_index}",
                    workspace_id=workspace_id,
                    source_path=HANDBOOK_PSEUDO_PATH,
                    chunk_index=chunk_index,
                    content=contextual_content,
                    token_estimate=estimate_tokens(contextual_content),
                    metadata={
                        "detected_type": HANDBOOK_PSEUDO_TYPE,
                        "extension": "md",
                        "pseudo_document": "handbook",
                    },
                )
            )
        return chunks, file_hash

    def _chunks_for_file(
        self,
        workspace_id: str,
        project_path: str,
        project_file: ProjectFile,
    ) -> tuple[list[TextChunk], str]:
        content = self.file_system.read_text_file(project_path, project_file.path)
        file_hash = content_hash(content)
        raw_chunks = chunk_document(
            content,
            file_type=project_file.detected_type,
            extension=project_file.extension,
        )

        total = len(raw_chunks)
        chunks: list[TextChunk] = []
        for chunk_index, chunk_content in enumerate(raw_chunks):
            # Prepend a deterministic "where this came from" header so retrieval
            # and citation both benefit; it is embedded and shown with the chunk.
            contextual_content = build_contextual_chunk(
                chunk_content,
                source_path=project_file.path,
                position=chunk_index + 1,
                total=total,
                file_type=project_file.detected_type,
                extension=project_file.extension,
            )
            chunks.append(
                TextChunk(
                    id=f"{workspace_id}:{project_file.path}:{chunk_index}",
                    workspace_id=workspace_id,
                    source_path=project_file.path,
                    chunk_index=chunk_index,
                    content=contextual_content,
                    token_estimate=estimate_tokens(contextual_content),
                    metadata={
                        "detected_type": project_file.detected_type,
                        "extension": project_file.extension or "",
                    },
                )
            )
        return chunks, file_hash
