from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.model_switching import ModelSwitchImpact, ModelSwitchingPlan
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


ALLOWED_MODEL_TYPES = {"llm", "embedding"}
ADVISORY_NOTE = (
    "This plan is advisory and does not change active runtime settings, download "
    "models, restart services, or reindex workspaces."
)
UNKNOWN_TARGET_NOTE = (
    "Target model is not in catalog; validate metadata before use."
)


@dataclass(frozen=True)
class CreateModelSwitchingPlanInput:
    model_type: str
    current_provider: str
    current_model: str
    target_provider: str
    target_model: str
    workspace_id: str | None = None


class ModelSwitchingPlanValidationError(ValueError):
    pass


class ModelSwitchingPlanWorkspaceNotFoundError(ValueError):
    pass


class CreateModelSwitchingPlanUseCase:
    def __init__(
        self,
        model_catalog_registry: ModelCatalogRegistry,
        workspace_repository: WorkspaceRepositoryPort | None = None,
        index_status_repository: IndexStatusRepositoryPort | None = None,
    ) -> None:
        self.model_catalog_registry = model_catalog_registry
        self.workspace_repository = workspace_repository
        self.index_status_repository = index_status_repository

    def execute(
        self,
        request: CreateModelSwitchingPlanInput,
    ) -> ModelSwitchingPlan:
        model_type = request.model_type.strip().lower()
        self._validate(request, model_type)

        workspace_id = request.workspace_id.strip() if request.workspace_id else None
        if workspace_id is not None:
            if (
                self.workspace_repository is None
                or self.workspace_repository.get(workspace_id) is None
            ):
                raise ModelSwitchingPlanWorkspaceNotFoundError("Workspace not found")

        current_provider = request.current_provider.strip().lower()
        current_model_name = request.current_model.strip()
        target_provider = request.target_provider.strip().lower()
        target_model_name = request.target_model.strip()
        current_model = self._find_model(
            model_type,
            current_provider,
            current_model_name,
        )
        target_model = self._find_model(
            model_type,
            target_provider,
            target_model_name,
        )

        if model_type == "embedding":
            return self._embedding_plan(
                workspace_id=workspace_id,
                current_provider=current_provider,
                current_model_name=current_model_name,
                target_provider=target_provider,
                target_model_name=target_model_name,
                current_model=current_model,
                target_model=target_model,
            )

        return self._llm_plan(
            workspace_id=workspace_id,
            current_provider=current_provider,
            current_model_name=current_model_name,
            target_provider=target_provider,
            target_model_name=target_model_name,
            current_model=current_model,
            target_model=target_model,
        )

    def _validate(
        self,
        request: CreateModelSwitchingPlanInput,
        model_type: str,
    ) -> None:
        if model_type not in ALLOWED_MODEL_TYPES:
            raise ModelSwitchingPlanValidationError(
                f"Unknown model type: {request.model_type}"
            )
        required_values = {
            "current_provider": request.current_provider,
            "current_model": request.current_model,
            "target_provider": request.target_provider,
            "target_model": request.target_model,
        }
        for field_name, value in required_values.items():
            if not value.strip():
                raise ModelSwitchingPlanValidationError(
                    f"{field_name} is required"
                )

    def _find_model(
        self,
        model_type: str,
        provider: str,
        model_name: str,
    ) -> LocalModelDefinition | None:
        return next(
            (
                model
                for model in self.model_catalog_registry.list_models()
                if model.model_type == model_type
                and model.provider.lower() == provider.lower()
                and model.model_name.lower() == model_name.lower()
            ),
            None,
        )

    def _llm_plan(
        self,
        workspace_id: str | None,
        current_provider: str,
        current_model_name: str,
        target_provider: str,
        target_model_name: str,
        current_model: LocalModelDefinition | None,
        target_model: LocalModelDefinition | None,
    ) -> ModelSwitchingPlan:
        notes = self._catalog_notes(current_model, target_model)
        notes.append(
            "LLM changes affect answer generation but do not invalidate existing "
            "embeddings or vector collections."
        )
        self._append_workspace_note(notes, workspace_id, requires_reindex=False)

        return ModelSwitchingPlan(
            workspace_id=workspace_id,
            model_type="llm",
            current_provider=current_provider,
            current_model=current_model_name,
            target_provider=target_provider,
            target_model=target_model_name,
            requires_reindex=False,
            requires_new_vector_collection=False,
            can_switch_without_reindex=True,
            requires_backend_restart=True,
            recommended_actions=[
                "Pull target model manually if not installed.",
                (
                    "Restart backend with "
                    f"OLLAMA_LLM_MODEL={target_model_name} if using Ollama."
                ),
                "Ask the same workspace question again to compare answers.",
            ],
            impacts=[
                ModelSwitchImpact(
                    area="answer_generation",
                    impact="The selected model may change answer quality, style, and speed.",
                    requires_reindex=False,
                    requires_backend_restart=True,
                    risk="medium",
                    explanation=(
                        "Generation changes after restart, while retrieved context "
                        "remains compatible."
                    ),
                ),
                ModelSwitchImpact(
                    area="retrieval",
                    impact="No retrieval changes are required.",
                    requires_reindex=False,
                    requires_backend_restart=False,
                    risk="none",
                    explanation="The embedding provider and stored vectors are unchanged.",
                ),
                ModelSwitchImpact(
                    area="vector_index",
                    impact="Existing vector collections remain usable.",
                    requires_reindex=False,
                    requires_backend_restart=False,
                    risk="none",
                    explanation="LLM selection does not alter the vector space.",
                ),
            ],
            notes=notes,
        )

    def _embedding_plan(
        self,
        workspace_id: str | None,
        current_provider: str,
        current_model_name: str,
        target_provider: str,
        target_model_name: str,
        current_model: LocalModelDefinition | None,
        target_model: LocalModelDefinition | None,
    ) -> ModelSwitchingPlan:
        notes = self._catalog_notes(current_model, target_model)
        notes.append(
            "Embedding changes create an incompatible vector space and require "
            "workspace context to be indexed again."
        )
        if target_model is not None and target_model.embedding_dimension is not None:
            notes.append(
                f"Target embedding dimension is {target_model.embedding_dimension}; "
                "Qdrant collection naming is embedding-provider/model/dimension aware."
            )
        self._append_workspace_note(notes, workspace_id, requires_reindex=True)

        return ModelSwitchingPlan(
            workspace_id=workspace_id,
            model_type="embedding",
            current_provider=current_provider,
            current_model=current_model_name,
            target_provider=target_provider,
            target_model=target_model_name,
            requires_reindex=True,
            requires_new_vector_collection=True,
            can_switch_without_reindex=False,
            requires_backend_restart=True,
            recommended_actions=[
                "Pull target embedding model manually if not installed.",
                (
                    "Restart backend with "
                    f"OLLAMA_EMBEDDING_MODEL={target_model_name}."
                ),
                "Reindex workspace context.",
                "Existing Qdrant collections are not deleted automatically.",
            ],
            impacts=[
                ModelSwitchImpact(
                    area="retrieval",
                    impact="Search results will use a different embedding space.",
                    requires_reindex=True,
                    requires_backend_restart=True,
                    risk="high",
                    explanation=(
                        "Query vectors must be compatible with all stored chunk vectors."
                    ),
                ),
                ModelSwitchImpact(
                    area="vector_index",
                    impact="A new dimension-aware vector collection is required.",
                    requires_reindex=True,
                    requires_backend_restart=True,
                    risk="high",
                    explanation=(
                        "Vectors from different embedding models must not be mixed."
                    ),
                ),
                ModelSwitchImpact(
                    area="historical_answers",
                    impact="Previous answers remain records but future retrieval may differ.",
                    requires_reindex=False,
                    requires_backend_restart=False,
                    risk="medium",
                    explanation=(
                        "Changing retrieval can change which context supports later answers."
                    ),
                ),
            ],
            notes=notes,
        )

    @staticmethod
    def _catalog_notes(
        current_model: LocalModelDefinition | None,
        target_model: LocalModelDefinition | None,
    ) -> list[str]:
        notes = [ADVISORY_NOTE]
        if current_model is None:
            notes.append(
                "Current model is not in catalog; current metadata could not be verified."
            )
        if target_model is None:
            notes.append(UNKNOWN_TARGET_NOTE)
        else:
            notes.append(
                f"Target model catalog entry: {target_model.display_name} "
                f"({target_model.provider}/{target_model.model_name})."
            )
        return notes

    def _append_workspace_note(
        self,
        notes: list[str],
        workspace_id: str | None,
        requires_reindex: bool,
    ) -> None:
        if workspace_id is None or self.index_status_repository is None:
            return
        index_status = self.index_status_repository.get(workspace_id)
        if index_status is None or index_status.status == "not_indexed":
            notes.append("The selected workspace has no saved indexed status.")
        elif requires_reindex:
            notes.append(
                f"Workspace index status is '{index_status.status}'; switching "
                "embeddings requires a new index before context search or RAG use."
            )
        else:
            notes.append(
                f"Workspace index status is '{index_status.status}' and remains "
                "compatible with this LLM switch."
            )
