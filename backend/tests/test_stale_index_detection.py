"""The search-context reindex prompt must appear exactly when the index was built
by a different embedder than the active one — and stay hidden otherwise."""

from types import SimpleNamespace

from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.workspace_model_selection import WorkspaceSelectedModel
from app.core.use_cases.get_selected_embedding_indexing_plan import (
    GetSelectedEmbeddingIndexingPlanInput,
    GetSelectedEmbeddingIndexingPlanUseCase,
)


def _plan(index_embedder, active_model="qwen3-embedding-0.6b"):
    selected = WorkspaceSelectedModel(
        provider="llamacpp",
        model="qwen3-embedding-0.6b",
        model_type="embedding",
        selected_at="t",
        selected_reason=None,
    )
    index = WorkspaceIndexStatus(
        workspace_id="w",
        status="indexed",
        indexed_files_count=1,
        chunks_count=1,
        skipped_files_count=0,
        last_indexed_at="t",
        last_error=None,
        embedding_model=index_embedder,
    )
    use_case = GetSelectedEmbeddingIndexingPlanUseCase(
        workspace_repository=SimpleNamespace(get=lambda _id: object()),
        selection_repository=SimpleNamespace(
            get=lambda _id: SimpleNamespace(selected_embedding=selected)
        ),
        index_status_repository=SimpleNamespace(get=lambda _id: index),
        configuration={
            "EMBEDDING_PROVIDER": "llamacpp",
            "OLLAMA_EMBEDDING_MODEL": active_model,
        },
    )
    return use_case.execute(GetSelectedEmbeddingIndexingPlanInput(workspace_id="w"))


def test_stale_index_prompts_reindex_when_embedder_changed():
    plan = _plan(index_embedder="nomic-embed-text")
    assert plan.plan_status == "needs_index"
    assert plan.requires_reindex is True
    assert plan.can_search_now is False


def test_no_reindex_prompt_when_index_embedder_matches():
    plan = _plan(index_embedder="qwen3-embedding-0.6b")
    assert plan.plan_status == "ready"
    assert plan.requires_reindex is False


def test_legacy_index_without_recorded_embedder_does_not_false_prompt():
    plan = _plan(index_embedder=None)
    assert plan.plan_status == "ready"
