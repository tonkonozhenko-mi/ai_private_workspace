from dataclasses import dataclass

from app.core.domain.onboarding import OnboardingPlan
from app.core.domain.onboarding_setup import SetupCommand
from app.core.domain.runtime_health import RuntimeComponentHealth, RuntimeHealth
from app.core.domain.runtime_setup_guide import RuntimeSetupAction, RuntimeSetupGuide
from app.core.use_cases.create_onboarding_plan import (
    CreateOnboardingPlanInput,
    CreateOnboardingPlanUseCase,
    OnboardingPlanValidationError,
)
from app.core.use_cases.get_onboarding_setup_commands import (
    GetOnboardingSetupCommandsInput,
    GetOnboardingSetupCommandsUseCase,
    OnboardingSetupCommandsValidationError,
)
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase


@dataclass(frozen=True)
class GetRuntimeSetupGuideInput:
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str = "local_only"
    container_runtime: str = "podman"


class RuntimeSetupGuideValidationError(ValueError):
    pass


class GetRuntimeSetupGuideUseCase:
    def __init__(
        self,
        runtime_health_use_case: GetRuntimeHealthUseCase,
        onboarding_plan_use_case: CreateOnboardingPlanUseCase | None = None,
        setup_commands_use_case: GetOnboardingSetupCommandsUseCase | None = None,
    ) -> None:
        self.runtime_health_use_case = runtime_health_use_case
        self.onboarding_plan_use_case = (
            onboarding_plan_use_case or CreateOnboardingPlanUseCase()
        )
        self.setup_commands_use_case = (
            setup_commands_use_case
            or GetOnboardingSetupCommandsUseCase(self.onboarding_plan_use_case)
        )

    def execute(self, request: GetRuntimeSetupGuideInput) -> RuntimeSetupGuide:
        plan = self._create_plan(request)
        setup_commands = self._get_setup_commands(request)
        runtime_health = self.runtime_health_use_case.execute()
        components = {
            component.name: component for component in runtime_health.components
        }

        actions = [
            self._setup_command_action(command, plan, runtime_health, components)
            for command in setup_commands.commands
        ]
        if self._uses_ollama(plan):
            actions.insert(
                self._ollama_action_position(actions),
                self._ollama_runtime_action(components.get("ollama")),
            )

        overall_status = self._overall_status(runtime_health, actions)
        return RuntimeSetupGuide(
            assistant_profile_id=plan.assistant_profile_id,
            laptop_profile_id=plan.laptop_profile_id,
            privacy_mode=plan.privacy_mode,
            container_runtime=request.container_runtime.lower(),
            overall_status=overall_status,
            actions=actions,
            notes=[
                "This guide only returns instructions and never executes commands.",
                "Runtime health checks are lightweight and do not mutate workspace data.",
                *setup_commands.notes,
            ],
        )

    def _create_plan(self, request: GetRuntimeSetupGuideInput) -> OnboardingPlan:
        try:
            return self.onboarding_plan_use_case.execute(
                CreateOnboardingPlanInput(
                    assistant_profile_id=request.assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                    privacy_mode=request.privacy_mode,
                )
            )
        except OnboardingPlanValidationError as exc:
            raise RuntimeSetupGuideValidationError(str(exc)) from exc

    def _get_setup_commands(self, request: GetRuntimeSetupGuideInput):
        try:
            return self.setup_commands_use_case.execute(
                GetOnboardingSetupCommandsInput(
                    assistant_profile_id=request.assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                    privacy_mode=request.privacy_mode,
                    container_runtime=request.container_runtime,
                )
            )
        except OnboardingSetupCommandsValidationError as exc:
            raise RuntimeSetupGuideValidationError(str(exc)) from exc

    def _setup_command_action(
        self,
        command: SetupCommand,
        plan: OnboardingPlan,
        health: RuntimeHealth,
        components: dict[str, RuntimeComponentHealth],
    ) -> RuntimeSetupAction:
        if command.category in {"qdrant", "container_runtime"}:
            qdrant = components.get("qdrant")
            done = self._component_ready(qdrant) and (
                health.configuration.get("VECTOR_STORE") == "qdrant"
            )
            return self._action_from_command(
                command,
                done=done,
                done_reason="Qdrant is configured and reachable.",
                needed_reason="The recommended Qdrant runtime is not ready.",
            )

        if command.id in {
            "pull_ollama_embedding_model",
            "pull_ollama_llm_model",
        }:
            ollama = components.get("ollama")
            model_key = (
                "OLLAMA_EMBEDDING_MODEL"
                if command.id == "pull_ollama_embedding_model"
                else "OLLAMA_LLM_MODEL"
            )
            model = plan.recommended_models.get(model_key, "")
            done = self._model_is_installed(model, ollama)
            return self._action_from_command(
                command,
                done=done,
                done_reason=f"Ollama model {model} is installed.",
                needed_reason=(
                    f"Ollama model {model} is not confirmed as installed."
                ),
            )

        if command.id == "start_backend":
            done = all(
                health.configuration.get(key) == value
                for key, value in plan.recommended_runtime.items()
            )
            return self._action_from_command(
                command,
                done=done,
                done_reason="The backend is using the recommended runtime providers.",
                needed_reason=(
                    "Restart the backend with the recommended runtime providers."
                ),
            )

        return self._action_from_command(
            command,
            done=False,
            done_reason="Setup action is complete.",
            needed_reason="This setup action still needs review.",
        )

    @staticmethod
    def _action_from_command(
        command: SetupCommand,
        done: bool,
        done_reason: str,
        needed_reason: str,
    ) -> RuntimeSetupAction:
        return RuntimeSetupAction(
            id=command.id,
            title=command.title,
            description=command.description,
            command=command.command,
            status="done" if done else "needed",
            reason=done_reason if done else needed_reason,
            category=command.category,
        )

    @staticmethod
    def _ollama_runtime_action(
        component: RuntimeComponentHealth | None,
    ) -> RuntimeSetupAction:
        done = bool(
            component
            and component.configured
            and (
                component.healthy
                or component.metadata.get("reachable") == "true"
            )
        )
        return RuntimeSetupAction(
            id="verify_ollama_runtime",
            title="Verify Ollama runtime",
            description="Confirm that the recommended local Ollama runtime is reachable.",
            command=None,
            status="done" if done else "needed",
            reason=(
                "Ollama is configured and reachable."
                if done
                else "The recommended Ollama runtime is not ready."
            ),
            category="ollama",
        )

    @staticmethod
    def _component_ready(component: RuntimeComponentHealth | None) -> bool:
        return bool(component and component.configured and component.healthy)

    @staticmethod
    def _model_is_installed(
        model: str,
        component: RuntimeComponentHealth | None,
    ) -> bool:
        if not model or component is None:
            return False
        installed_models = {
            installed.strip()
            for installed in component.metadata.get("installed_models", "").split(",")
            if installed.strip()
        }
        return any(
            installed == model
            or installed.removesuffix(":latest") == model
            or model.removesuffix(":latest") == installed
            for installed in installed_models
        )

    @staticmethod
    def _uses_ollama(plan: OnboardingPlan) -> bool:
        return (
            plan.recommended_runtime.get("EMBEDDING_PROVIDER") == "ollama"
            or plan.recommended_runtime.get("LLM_PROVIDER") == "ollama"
        )

    @staticmethod
    def _ollama_action_position(actions: list[RuntimeSetupAction]) -> int:
        return next(
            (
                index
                for index, action in enumerate(actions)
                if action.category == "ollama"
            ),
            len(actions),
        )

    @staticmethod
    def _overall_status(
        health: RuntimeHealth,
        actions: list[RuntimeSetupAction],
    ) -> str:
        if health.status == "degraded":
            return "degraded"
        if all(action.status in {"done", "optional"} for action in actions):
            return "ready"
        return "needs_setup"
