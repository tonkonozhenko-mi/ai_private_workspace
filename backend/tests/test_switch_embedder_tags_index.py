"""Switching the search model tags an older, untagged index with the previous
model, so the indexing plan can detect it as stale and prompt a rebuild."""

from types import SimpleNamespace

from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.workspace_model_selection import (
    WorkspaceModelSelection,
    WorkspaceSelectedModel,
)
from app.core.use_cases.update_workspace_model_selection import (
    UpdateWorkspaceModelSelectionInput,
    UpdateWorkspaceModelSelectionUseCase,
)


class _IndexRepo:
    def __init__(self, index):
        self.index = index

    def get(self, _workspace_id):
        return self.index

    def save(self, status):
        self.index = status
        return status


class _SelRepo:
    def __init__(self, selection):
        self.selection = selection

    def get(self, _workspace_id):
        return self.selection

    def save(self, selection):
        self.selection = selection
        return selection


def _use_case(index_repo, sel_repo):
    return UpdateWorkspaceModelSelectionUseCase(
        workspace_repository=SimpleNamespace(get=lambda _id: object()),
        selection_repository=sel_repo,
        model_catalog_registry=ModelCatalogRegistry(),
        index_status_repository=index_repo,
    )


def _switch(index_repo, sel_repo, model):
    _use_case(index_repo, sel_repo).execute(
        UpdateWorkspaceModelSelectionInput(
            workspace_id="w", provider="llamacpp", model=model, model_type="embedding"
        )
    )


def test_untagged_index_is_tagged_with_previous_model_on_switch():
    prior = WorkspaceSelectedModel("llamacpp", "nomic-embed-text", "embedding", "t", None)
    index_repo = _IndexRepo(
        WorkspaceIndexStatus("w", "indexed", 1, 1, 0, "t", None, embedding_model=None)
    )
    sel_repo = _SelRepo(WorkspaceModelSelection("w", None, prior, []))

    _switch(index_repo, sel_repo, "qwen3-embedding-0.6b")

    assert index_repo.index.embedding_model == "nomic-embed-text"


def test_reselecting_same_model_does_not_tag_stale():
    prior = WorkspaceSelectedModel("llamacpp", "nomic-embed-text", "embedding", "t", None)
    index_repo = _IndexRepo(
        WorkspaceIndexStatus("w", "indexed", 1, 1, 0, "t", None, embedding_model=None)
    )
    sel_repo = _SelRepo(WorkspaceModelSelection("w", None, prior, []))

    _switch(index_repo, sel_repo, "nomic-embed-text")

    assert index_repo.index.embedding_model is None  # unchanged → no false prompt
