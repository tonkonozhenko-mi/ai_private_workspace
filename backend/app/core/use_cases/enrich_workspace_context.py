"""Background selective contextual enrichment (off by default).

Walks the already-indexed chunks, picks the small set worth situating (docs cut
mid-section and context-poor code fragments — see
``app.core.domain.contextual_enrichment``), asks the local model for a one-line
"where this sits" note per chunk, and re-embeds just that chunk with the note
prepended. The index keeps working throughout; it only *gets smarter* as chunks
are enriched.

Design guarantees:
- **Off unless enabled.** A disabled use case returns immediately without reading
  or writing anything — the constructor flag gates the whole feature.
- **Bounded.** A cap (fraction of the corpus, and an absolute max) keeps a big repo
  from enriching its way through the whole index in one run.
- **Idempotent.** An already-enriched chunk (carrying the ``[context: …]`` marker)
  is skipped, so re-running continues with the next batch instead of redoing work.
- **Fail-open per chunk.** A model or embedding hiccup on one chunk is counted as
  skipped and never aborts the run or corrupts the index.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain.chunking import estimate_tokens, strip_contextual_header
from app.core.domain.contextual_enrichment import (
    DEFAULT_MAX_CHUNKS,
    EnrichmentCandidate,
    apply_enrichment,
    build_enrichment_prompt,
    sanitize_enrichment,
    select_enrichment_targets,
)
from app.core.domain.indexing import TextChunk
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.index_workspace import INDEXABLE_FILE_TYPES

# How much of a file's first chunk to use as cheap framing in the prompt. Enough to
# tell the model what the file is, without a second retrieval pass.
_DIGEST_CHARS = 400


@dataclass(frozen=True)
class EnrichWorkspaceContextInput:
    workspace_id: str
    max_chunks: int = DEFAULT_MAX_CHUNKS
    cancellation_check: Callable[[], bool] | None = None


@dataclass(frozen=True)
class EnrichWorkspaceContextResult:
    workspace_id: str
    enabled: bool
    examined_chunks: int
    enriched_chunks: int
    skipped_chunks: int
    documents_touched: int


class EnrichWorkspaceContextNotFoundError(ValueError):
    pass


class EnrichWorkspaceContextCancelledError(RuntimeError):
    pass


class EnrichWorkspaceContextUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        vector_store: VectorStorePort,
        embedding_provider: EmbeddingProviderPort,
        llm_provider_factory=None,
        enabled: bool = False,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.llm_provider_factory = llm_provider_factory
        # The master switch: when False, the feature is inert (slow-hardware default).
        self.enabled = enabled

    def execute(self, request: EnrichWorkspaceContextInput) -> EnrichWorkspaceContextResult:
        if not self.enabled or self.llm_provider_factory is None:
            return self._empty(request.workspace_id, enabled=False)

        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise EnrichWorkspaceContextNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            return self._empty(request.workspace_id, enabled=True)

        indexable = {
            f.path: (f.detected_type, f.extension)
            for f in latest_scan.files
            if f.detected_type in INDEXABLE_FILE_TYPES
        }
        if not indexable:
            return self._empty(request.workspace_id, enabled=True)

        candidates, digests = self._collect_candidates(request.workspace_id, indexable)
        if not candidates:
            return self._empty(request.workspace_id, enabled=True)

        status = self.index_status_repository.get(request.workspace_id)
        corpus_size = status.chunks_count if status and status.chunks_count else len(candidates)
        targets = select_enrichment_targets(
            candidates, corpus_size=corpus_size, max_chunks=max(1, request.max_chunks)
        )
        if not targets:
            return self._empty(request.workspace_id, enabled=True)

        llm = self.llm_provider_factory.create()
        if llm is None:
            return self._empty(request.workspace_id, enabled=True)

        enriched = skipped = 0
        touched: set[str] = set()
        for target in targets:
            self._checkpoint(request.cancellation_check)
            digest = digests.get(target.source_path, "")
            if self._enrich_one(request.workspace_id, target, digest, llm):
                enriched += 1
                touched.add(target.source_path)
            else:
                skipped += 1

        return EnrichWorkspaceContextResult(
            workspace_id=request.workspace_id,
            enabled=True,
            examined_chunks=len(targets),
            enriched_chunks=enriched,
            skipped_chunks=skipped,
            documents_touched=len(touched),
        )

    def _collect_candidates(
        self, workspace_id: str, indexable: dict[str, tuple[str, str | None]]
    ) -> tuple[list[EnrichmentCandidate], dict[str, str]]:
        candidates: list[EnrichmentCandidate] = []
        digests: dict[str, str] = {}
        for path, (file_type, extension) in indexable.items():
            chunks = self.vector_store.get_source_chunks(workspace_id, path)
            total = len(chunks)
            if total == 0:
                continue
            # Cheap per-file framing for the prompt: the first chunk's clean body.
            digests[path] = strip_contextual_header(chunks[0].content)[:_DIGEST_CHARS]
            for source_chunk in chunks:
                candidates.append(
                    EnrichmentCandidate(
                        chunk_id=source_chunk.chunk_id,
                        source_path=path,
                        content=source_chunk.content,
                        file_type=file_type,
                        extension=extension,
                        position=source_chunk.chunk_index + 1,
                        total=total,
                    )
                )
        return candidates, digests

    def _enrich_one(self, workspace_id: str, target: EnrichmentCandidate, digest: str, llm) -> bool:
        """Enrich a single chunk end-to-end. Returns True on a successful re-embed,
        False (counted as skipped) on an empty note or any failure — never raises."""
        try:
            body = strip_contextual_header(target.content)
            prompt = build_enrichment_prompt(target.source_path, digest, body)
            raw = llm.generate(prompt, temperature=0.0, think=False)
            note = sanitize_enrichment(raw or "")
            if not note:
                return False
            stored_content, embed_text = apply_enrichment(target.content, note)
            embedding = self.embedding_provider.embed_text(embed_text)
            if not embedding:
                return False
            chunk = TextChunk(
                id=target.chunk_id,
                workspace_id=workspace_id,
                source_path=target.source_path,
                chunk_index=target.position - 1,
                content=stored_content,
                token_estimate=estimate_tokens(stored_content),
                metadata={
                    "detected_type": target.file_type or "",
                    "extension": target.extension or "",
                    "enriched": "1",
                },
            )
            self.vector_store.upsert_chunks(
                workspace_id=workspace_id,
                chunks=[chunk],
                embeddings=[embedding],
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=len(embedding),
            )
            return True
        except EnrichWorkspaceContextCancelledError:
            raise
        except Exception:  # noqa: BLE001 - per-chunk enrichment is best-effort
            return False

    @staticmethod
    def _checkpoint(cancellation_check: Callable[[], bool] | None) -> None:
        if cancellation_check is not None and cancellation_check():
            raise EnrichWorkspaceContextCancelledError("Enrichment cancelled")

    @staticmethod
    def _empty(workspace_id: str, enabled: bool) -> EnrichWorkspaceContextResult:
        return EnrichWorkspaceContextResult(
            workspace_id=workspace_id,
            enabled=enabled,
            examined_chunks=0,
            enriched_chunks=0,
            skipped_chunks=0,
            documents_touched=0,
        )
