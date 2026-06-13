from dataclasses import dataclass
from typing import Callable
from datetime import UTC, datetime

from app.core.domain.chunking import chunk_document, estimate_tokens
from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.indexing import (
    IndexedDocumentSummary,
    TextChunk,
    WorkspaceIndexResult,
)
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.file_system import FileSystemPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


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
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.index_status_repository = index_status_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: IndexWorkspaceInput) -> WorkspaceIndexResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise IndexWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise IndexWorkspaceScanRequiredError(
                "Project scan required before indexing workspace"
            )

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
        skipped_files_count = latest_scan.skipped_files

        total_files = len(latest_scan.files) or 1
        for file_index, project_file in enumerate(latest_scan.files, start=1):
            self._checkpoint(cancellation_check)
            if progress_callback is not None:
                progress_callback(file_index, total_files, f"Reading files: {file_index}/{total_files}")
            if project_file.detected_type not in INDEXABLE_FILE_TYPES:
                skipped_files_count += 1
                continue

            file_chunks = self._chunks_for_file(
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

        embeddings = []
        total_chunks = len(chunks) or 1
        for chunk_index, chunk in enumerate(chunks, start=1):
            self._checkpoint(cancellation_check)
            if progress_callback is not None:
                progress_callback(chunk_index, total_chunks, f"Embedding chunks: {chunk_index}/{total_chunks}")
            embeddings.append(self.embedding_provider.embed_text(chunk.content))
        self._checkpoint(cancellation_check)
        embedding_dimension = self._embedding_dimension(embeddings)
        if progress_callback is not None:
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

        return WorkspaceIndexResult(
            workspace_id=workspace_id,
            indexed_files_count=len(documents),
            chunks_count=len(chunks),
            skipped_files_count=skipped_files_count,
            documents=documents,
        )

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

    def _chunks_for_file(
        self,
        workspace_id: str,
        project_path: str,
        project_file: ProjectFile,
    ) -> list[TextChunk]:
        content = self.file_system.read_text_file(project_path, project_file.path)
        raw_chunks = chunk_document(content, file_type=project_file.detected_type)

        return [
            TextChunk(
                id=f"{workspace_id}:{project_file.path}:{chunk_index}",
                workspace_id=workspace_id,
                source_path=project_file.path,
                chunk_index=chunk_index,
                content=chunk_content,
                token_estimate=estimate_tokens(chunk_content),
                metadata={
                    "detected_type": project_file.detected_type,
                    "extension": project_file.extension or "",
                },
            )
            for chunk_index, chunk_content in enumerate(raw_chunks)
        ]
