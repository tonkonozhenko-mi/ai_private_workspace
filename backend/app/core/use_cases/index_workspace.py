from dataclasses import dataclass

from app.core.domain.chunking import chunk_text, estimate_tokens
from app.core.domain.indexing import (
    IndexedDocumentSummary,
    TextChunk,
    WorkspaceIndexResult,
)
from app.core.domain.project_scan import ProjectFile
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


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


class IndexWorkspaceNotFoundError(ValueError):
    pass


class IndexWorkspaceScanRequiredError(ValueError):
    pass


class IndexWorkspaceUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def execute(self, request: IndexWorkspaceInput) -> WorkspaceIndexResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise IndexWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise IndexWorkspaceScanRequiredError(
                "Project scan required before indexing workspace"
            )

        self.vector_store.clear_workspace(request.workspace_id)

        documents: list[IndexedDocumentSummary] = []
        chunks: list[TextChunk] = []
        skipped_files_count = latest_scan.skipped_files

        for project_file in latest_scan.files:
            if project_file.detected_type not in INDEXABLE_FILE_TYPES:
                skipped_files_count += 1
                continue

            file_chunks = self._chunks_for_file(
                workspace_id=request.workspace_id,
                project_path=workspace.project_path,
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

        embeddings = [
            self.embedding_provider.embed_text(chunk.content) for chunk in chunks
        ]
        if chunks:
            self.vector_store.upsert_chunks(
                workspace_id=request.workspace_id,
                chunks=chunks,
                embeddings=embeddings,
            )

        return WorkspaceIndexResult(
            workspace_id=request.workspace_id,
            indexed_files_count=len(documents),
            chunks_count=len(chunks),
            skipped_files_count=skipped_files_count,
            documents=documents,
        )

    def _chunks_for_file(
        self,
        workspace_id: str,
        project_path: str,
        project_file: ProjectFile,
    ) -> list[TextChunk]:
        content = self.file_system.read_text_file(project_path, project_file.path)
        raw_chunks = chunk_text(content)

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
