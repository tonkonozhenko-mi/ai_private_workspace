from dataclasses import dataclass

from app.core.domain.assistant_profile_registry import AssistantProfileRegistry
from app.core.domain.laptop_profile_registry import LaptopProfileRegistry
from app.core.domain.onboarding import OnboardingPlan, OnboardingStep


@dataclass(frozen=True)
class CreateOnboardingPlanInput:
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str = "local_only"


class OnboardingPlanValidationError(ValueError):
    pass


class CreateOnboardingPlanUseCase:
    def __init__(
        self,
        assistant_profile_registry: AssistantProfileRegistry | None = None,
        laptop_profile_registry: LaptopProfileRegistry | None = None,
    ) -> None:
        self.assistant_profile_registry = assistant_profile_registry or AssistantProfileRegistry()
        self.laptop_profile_registry = laptop_profile_registry or LaptopProfileRegistry()

    def execute(self, request: CreateOnboardingPlanInput) -> OnboardingPlan:
        assistant_profile = next(
            (
                profile
                for profile in self.assistant_profile_registry.list_profiles()
                if profile.id == request.assistant_profile_id
            ),
            None,
        )
        if assistant_profile is None:
            raise OnboardingPlanValidationError(
                f"Unknown assistant profile: {request.assistant_profile_id}"
            )

        laptop_profile = self.laptop_profile_registry.find_profile(request.laptop_profile_id)
        if laptop_profile is None:
            raise OnboardingPlanValidationError(
                f"Unknown laptop profile: {request.laptop_profile_id}"
            )

        recommended_runtime = {
            **assistant_profile.recommended_runtime,
            **self.laptop_profile_registry.runtime_recommendation(laptop_profile.id),
        }
        if request.privacy_mode == "local_only" and laptop_profile.id != "low_power":
            recommended_runtime.update(
                {
                    "VECTOR_STORE": "qdrant",
                    "EMBEDDING_PROVIDER": "ollama",
                    "LLM_PROVIDER": "ollama",
                }
            )

        recommended_models = self.laptop_profile_registry.model_recommendation(laptop_profile.id)
        return OnboardingPlan(
            assistant_profile_id=assistant_profile.id,
            laptop_profile_id=laptop_profile.id,
            privacy_mode=request.privacy_mode,
            recommended_runtime=recommended_runtime,
            recommended_models=recommended_models,
            steps=self._steps(recommended_runtime),
            notes=self._notes(
                assistant_profile_name=assistant_profile.name,
                laptop_profile_id=laptop_profile.id,
                privacy_mode=request.privacy_mode,
                recommended_runtime=recommended_runtime,
            ),
        )

    @staticmethod
    def _steps(recommended_runtime: dict[str, str]) -> list[OnboardingStep]:
        uses_qdrant = recommended_runtime.get("VECTOR_STORE") == "qdrant"
        uses_ollama_embeddings = recommended_runtime.get("EMBEDDING_PROVIDER") == "ollama"
        uses_ollama_llm = recommended_runtime.get("LLM_PROVIDER") == "ollama"
        uses_ollama = uses_ollama_embeddings or uses_ollama_llm

        return [
            OnboardingStep(
                id="select_project_path",
                title="Select project path",
                description="Choose the local project folder for this workspace.",
                required=True,
                status="pending",
            ),
            OnboardingStep(
                id="create_workspace",
                title="Create or open workspace",
                description="Create a workspace using the selected assistant profile.",
                required=True,
                status="pending",
            ),
            OnboardingStep(
                id="run_project_scan",
                title="Run project scan",
                description="Detect project files, technologies, and skills.",
                required=True,
                status="recommended",
            ),
            OnboardingStep(
                id="review_detected_skills",
                title="Review detected skills",
                description="Confirm the deterministic skill signals found by the scan.",
                required=False,
                status="recommended",
            ),
            OnboardingStep(
                id="start_qdrant_if_needed",
                title="Start Qdrant if needed",
                description="Start Qdrant for persistent vector context.",
                required=False,
                status="recommended" if uses_qdrant else "optional",
            ),
            OnboardingStep(
                id="start_ollama_if_needed",
                title="Start Ollama if needed",
                description="Start Ollama for configured local embedding or LLM models.",
                required=False,
                status="recommended" if uses_ollama else "optional",
            ),
            OnboardingStep(
                id="pull_embedding_model_if_needed",
                title="Pull embedding model if needed",
                description="Install the recommended local embedding model.",
                required=False,
                status="recommended" if uses_ollama_embeddings else "optional",
            ),
            OnboardingStep(
                id="pull_llm_model_if_needed",
                title="Pull LLM model if needed",
                description="Install the recommended local language model.",
                required=False,
                status="recommended" if uses_ollama_llm else "optional",
            ),
            OnboardingStep(
                id="index_workspace",
                title="Index workspace",
                description="Build searchable workspace context after scanning.",
                required=False,
                status="recommended",
            ),
            OnboardingStep(
                id="ask_first_question",
                title="Ask first workspace question",
                description="Verify the workspace question flow using indexed context.",
                required=False,
                status="recommended",
            ),
            OnboardingStep(
                id="review_readiness",
                title="Review workspace readiness",
                description="Confirm available capabilities and recommended next actions.",
                required=False,
                status="recommended",
            ),
        ]

    @staticmethod
    def _notes(
        assistant_profile_name: str,
        laptop_profile_id: str,
        privacy_mode: str,
        recommended_runtime: dict[str, str],
    ) -> list[str]:
        notes = [
            f"Plan is tailored for the {assistant_profile_name}.",
            "This plan does not create a workspace, execute commands, or contact runtimes.",
        ]
        if privacy_mode == "local_only":
            notes.append("Local-only privacy keeps project data on configured local services.")
        if laptop_profile_id == "low_power":
            notes.append(
                "Low-power mode starts with memory and fake providers; real local AI "
                "can be enabled later."
            )
        if recommended_runtime.get("VECTOR_STORE") == "memory":
            notes.append("In-memory vector context is lost when the API restarts.")
        return notes
