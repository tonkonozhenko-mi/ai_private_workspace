from dataclasses import dataclass

from app.core.domain.command_risk import classify_command_risk
from app.core.domain.onboarding_setup import OnboardingSetupCommands, SetupCommand
from app.core.use_cases.create_onboarding_plan import (
    CreateOnboardingPlanInput,
    CreateOnboardingPlanUseCase,
    OnboardingPlanValidationError,
)


ALLOWED_CONTAINER_RUNTIMES = {"podman", "docker"}


@dataclass(frozen=True)
class GetOnboardingSetupCommandsInput:
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str = "local_only"
    container_runtime: str = "podman"


class OnboardingSetupCommandsValidationError(ValueError):
    pass


class GetOnboardingSetupCommandsUseCase:
    def __init__(
        self,
        onboarding_plan_use_case: CreateOnboardingPlanUseCase | None = None,
    ) -> None:
        self.onboarding_plan_use_case = (
            onboarding_plan_use_case or CreateOnboardingPlanUseCase()
        )

    def execute(
        self,
        request: GetOnboardingSetupCommandsInput,
    ) -> OnboardingSetupCommands:
        container_runtime = request.container_runtime.lower()
        if container_runtime not in ALLOWED_CONTAINER_RUNTIMES:
            raise OnboardingSetupCommandsValidationError(
                f"Unknown container runtime: {request.container_runtime}"
            )

        try:
            plan = self.onboarding_plan_use_case.execute(
                CreateOnboardingPlanInput(
                    assistant_profile_id=request.assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                    privacy_mode=request.privacy_mode,
                )
            )
        except OnboardingPlanValidationError as exc:
            raise OnboardingSetupCommandsValidationError(str(exc)) from exc

        commands: list[SetupCommand] = []
        if plan.recommended_runtime.get("VECTOR_STORE") == "qdrant":
            commands.extend(self._qdrant_commands(container_runtime))

        if plan.recommended_runtime.get("EMBEDDING_PROVIDER") == "ollama":
            commands.append(
                self._command(
                    id="pull_ollama_embedding_model",
                    title="Pull Ollama embedding model",
                    command=(
                        "ollama pull "
                        f"{plan.recommended_models['OLLAMA_EMBEDDING_MODEL']}"
                    ),
                    description="Install the recommended local embedding model.",
                    category="ollama",
                    required=True,
                )
            )

        if plan.recommended_runtime.get("LLM_PROVIDER") == "ollama":
            commands.append(
                self._command(
                    id="pull_ollama_llm_model",
                    title="Pull Ollama LLM model",
                    command=(
                        f"ollama pull {plan.recommended_models['OLLAMA_LLM_MODEL']}"
                    ),
                    description="Install the recommended local language model.",
                    category="ollama",
                    required=True,
                )
            )

        commands.append(self._backend_start_command(plan.recommended_runtime))
        return OnboardingSetupCommands(
            assistant_profile_id=plan.assistant_profile_id,
            laptop_profile_id=plan.laptop_profile_id,
            privacy_mode=plan.privacy_mode,
            commands=commands,
            notes=[
                "Setup commands are instructions only and are never executed automatically.",
                (
                    "Setup commands cannot be proposed through the workspace command "
                    "approval flow because they operate outside a workspace."
                ),
                *plan.notes,
            ],
        )

    def _qdrant_commands(self, container_runtime: str) -> list[SetupCommand]:
        if container_runtime == "docker":
            return [
                self._command(
                    id="start_qdrant_docker",
                    title="Start Qdrant with Docker Compose",
                    command="docker compose up -d qdrant",
                    description="Start the optional Qdrant service from docker-compose.yml.",
                    category="qdrant",
                    required=True,
                )
            ]

        return [
            self._command(
                id="start_podman_machine",
                title="Start Podman machine",
                command="podman machine start",
                description="Start the local Podman virtual machine if it is not running.",
                category="container_runtime",
                required=True,
            ),
            self._command(
                id="start_qdrant_podman",
                title="Start Qdrant with Podman",
                command=(
                    "podman run -d --name qdrant -p 6333:6333 "
                    "-v qdrant_data:/qdrant/storage "
                    "docker.io/qdrant/qdrant:latest"
                ),
                description="Start a persistent local Qdrant container using Podman.",
                category="qdrant",
                required=True,
            ),
        ]

    def _backend_start_command(
        self,
        recommended_runtime: dict[str, str],
    ) -> SetupCommand:
        environment = [
            f"VECTOR_STORE={recommended_runtime['VECTOR_STORE']}",
            f"EMBEDDING_PROVIDER={recommended_runtime['EMBEDDING_PROVIDER']}",
            f"LLM_PROVIDER={recommended_runtime['LLM_PROVIDER']}",
        ]
        if recommended_runtime.get("VECTOR_STORE") == "qdrant":
            environment.append("QDRANT_URL=http://localhost:6333")
        if (
            recommended_runtime.get("EMBEDDING_PROVIDER") == "ollama"
            or recommended_runtime.get("LLM_PROVIDER") == "ollama"
        ):
            environment.append("OLLAMA_BASE_URL=http://localhost:11434")

        return self._command(
            id="start_backend",
            title="Start backend with recommended runtime",
            command=f"{' '.join(environment)} uvicorn app.main:app --reload",
            description="Start the backend using the recommended runtime configuration.",
            category="backend",
            required=True,
        )

    @staticmethod
    def _command(
        id: str,
        title: str,
        command: str,
        description: str,
        category: str,
        required: bool,
    ) -> SetupCommand:
        return SetupCommand(
            id=id,
            title=title,
            command=command,
            description=description,
            category=category,
            required=required,
            risk=classify_command_risk(command),
            can_be_proposed=False,
        )
