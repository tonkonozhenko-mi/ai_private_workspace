from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.core.domain.model_experiment_run import (
    ModelExperimentCandidateRequest,
    ModelExperimentCandidateResult,
    ModelExperimentRun,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag import RagSource
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer
from app.core.domain.rag_prompt import build_workspace_question_prompt
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider_factory import LLMProviderFactoryPort
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


SUPPORTED_EXPERIMENT_TYPE = "llm_comparison"
NO_ACTIVE_CONTEXT_NOTE = (
    "Index metadata exists, but no context chunks were found in the active vector "
    "store. Reindex the workspace in the active vector store before retrying."
)
SHARED_CONTEXT_NOTE = (
    "All candidates used the same retrieved context chunks and prompt."
)


@dataclass(frozen=True)
class RunModelExperimentInput:
    workspace_id: str
    question: str
    candidates: list[ModelExperimentCandidateRequest]
    experiment_type: str = SUPPORTED_EXPERIMENT_TYPE
    limit: int = 3


class RunModelExperimentValidationError(ValueError):
    pass


class RunModelExperimentWorkspaceNotFoundError(ValueError):
    pass


class RunModelExperimentIndexRequiredError(ValueError):
    pass


class RunModelExperimentUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        vector_store: VectorStorePort,
        embedding_provider: EmbeddingProviderPort,
        llm_provider_factory: LLMProviderFactoryPort,
        model_experiment_repository: ModelExperimentRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.index_status_repository = index_status_repository
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.llm_provider_factory = llm_provider_factory
        self.model_experiment_repository = model_experiment_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: RunModelExperimentInput) -> ModelExperimentRun:
        workspace_id = request.workspace_id.strip()
        question = request.question.strip()
        experiment_type = request.experiment_type.strip().lower()
        self._validate(request, workspace_id, question, experiment_type)

        if self.workspace_repository.get(workspace_id) is None:
            raise RunModelExperimentWorkspaceNotFoundError("Workspace not found")

        index_status = self.index_status_repository.get(workspace_id)
        if index_status is None or index_status.status != "indexed":
            raise RunModelExperimentIndexRequiredError(
                "Workspace must be indexed before running a model experiment"
            )

        created_at = datetime.now(UTC).isoformat()
        context_results = self._search_context(
            workspace_id=workspace_id,
            question=question,
            limit=request.limit,
        )
        if not context_results:
            run = self._failed_no_context_run(
                request=request,
                workspace_id=workspace_id,
                question=question,
                experiment_type=experiment_type,
                created_at=created_at,
            )
            return self._save_and_record(run)

        prompt = build_workspace_question_prompt(
            question=question,
            context_results=context_results,
        )
        sources = [
            RagSource(
                chunk_id=result.chunk_id,
                source_path=result.source_path,
                score=result.score,
                preview=result.content[:200],
            )
            for result in context_results
        ]
        source_contents = [result.content for result in context_results]
        candidate_results = [
            self._run_candidate(
                candidate=candidate,
                question=question,
                prompt=prompt,
                sources=sources,
                source_contents=source_contents,
            )
            for candidate in request.candidates
        ]
        run = ModelExperimentRun(
            id=str(uuid4()),
            workspace_id=workspace_id,
            question=question,
            experiment_type=experiment_type,
            status=self._overall_status(candidate_results),
            created_at=created_at,
            completed_at=datetime.now(UTC).isoformat(),
            shared_context_sources_count=len(context_results),
            candidates=candidate_results,
            notes=[SHARED_CONTEXT_NOTE],
        )
        return self._save_and_record(run)

    @staticmethod
    def _validate(
        request: RunModelExperimentInput,
        workspace_id: str,
        question: str,
        experiment_type: str,
    ) -> None:
        if not workspace_id:
            raise RunModelExperimentValidationError("workspace_id is required")
        if not question:
            raise RunModelExperimentValidationError("Question is required")
        if experiment_type != SUPPORTED_EXPERIMENT_TYPE:
            raise RunModelExperimentValidationError(
                f"Unknown experiment type: {request.experiment_type}"
            )
        if not request.candidates:
            raise RunModelExperimentValidationError(
                "At least one model candidate is required"
            )
        if request.limit <= 0 or request.limit > 50:
            raise RunModelExperimentValidationError(
                "Context limit must be between 1 and 50"
            )
        for candidate in request.candidates:
            if not candidate.provider.strip():
                raise RunModelExperimentValidationError(
                    "Candidate provider is required"
                )
            if not candidate.model.strip():
                raise RunModelExperimentValidationError(
                    "Candidate model is required"
                )

    def _search_context(
        self,
        workspace_id: str,
        question: str,
        limit: int,
    ) -> list[ContextSearchResult]:
        query_embedding = self.embedding_provider.embed_text(question)
        return self.vector_store.search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            limit=limit,
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name,
            embedding_dimension=len(query_embedding),
        )

    def _run_candidate(
        self,
        candidate: ModelExperimentCandidateRequest,
        question: str,
        prompt: str,
        sources: list[RagSource],
        source_contents: list[str],
    ) -> ModelExperimentCandidateResult:
        provider_name = candidate.provider.strip().lower()
        model_name = candidate.model.strip()
        started_at = perf_counter()
        try:
            provider = self.llm_provider_factory.create(
                provider=provider_name,
                model=model_name,
            )
            answer = provider.generate(prompt)
            quality_warnings = evaluate_rag_answer(
                question=question,
                answer=answer,
                sources=sources,
                source_contents=source_contents,
            )
            return ModelExperimentCandidateResult(
                provider=provider_name,
                model=model_name,
                status="completed",
                answer=answer,
                error=None,
                llm_provider=provider.provider_name,
                llm_model=provider.model_name or model_name,
                used_context_chunks=len(sources),
                sources_count=len(sources),
                quality_warnings_count=len(quality_warnings),
                latency_ms=self._latency_ms(started_at),
            )
        except Exception as exc:
            return ModelExperimentCandidateResult(
                provider=provider_name,
                model=model_name,
                status="failed",
                answer=None,
                error=str(exc),
                llm_provider=provider_name,
                llm_model=model_name,
                used_context_chunks=len(sources),
                sources_count=len(sources),
                quality_warnings_count=0,
                latency_ms=self._latency_ms(started_at),
            )

    def _failed_no_context_run(
        self,
        request: RunModelExperimentInput,
        workspace_id: str,
        question: str,
        experiment_type: str,
        created_at: str,
    ) -> ModelExperimentRun:
        return ModelExperimentRun(
            id=str(uuid4()),
            workspace_id=workspace_id,
            question=question,
            experiment_type=experiment_type,
            status="failed",
            created_at=created_at,
            completed_at=datetime.now(UTC).isoformat(),
            shared_context_sources_count=0,
            candidates=[
                ModelExperimentCandidateResult(
                    provider=candidate.provider.strip().lower(),
                    model=candidate.model.strip(),
                    status="skipped",
                    answer=None,
                    error=NO_ACTIVE_CONTEXT_NOTE,
                    llm_provider=candidate.provider.strip().lower(),
                    llm_model=candidate.model.strip(),
                    used_context_chunks=0,
                    sources_count=0,
                    quality_warnings_count=0,
                    latency_ms=None,
                )
                for candidate in request.candidates
            ],
            notes=[NO_ACTIVE_CONTEXT_NOTE],
        )

    @staticmethod
    def _overall_status(
        candidates: list[ModelExperimentCandidateResult],
    ) -> str:
        completed = sum(candidate.status == "completed" for candidate in candidates)
        if completed == len(candidates):
            return "completed"
        if completed:
            return "partial"
        return "failed"

    @staticmethod
    def _latency_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    def _save_and_record(self, run: ModelExperimentRun) -> ModelExperimentRun:
        saved = self.model_experiment_repository.save(run)
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=saved.workspace_id,
                    event_type="model_experiment_run",
                    title="Model experiment run",
                    summary=f"Compared {len(saved.candidates)} model candidates.",
                    metadata={
                        "experiment_id": saved.id,
                        "candidates_count": str(len(saved.candidates)),
                        "status": saved.status,
                    },
                )
            )
        return saved
