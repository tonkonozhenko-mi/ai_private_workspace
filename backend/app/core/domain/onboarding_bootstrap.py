from dataclasses import dataclass

from app.core.domain.onboarding import OnboardingPlan
from app.core.domain.onboarding_setup import OnboardingSetupCommands
from app.core.domain.runtime_setup_guide import RuntimeSetupGuide
from app.core.domain.workspace import Workspace
from app.core.domain.workspace_readiness import WorkspaceReadiness


@dataclass(frozen=True)
class OnboardingBootstrapResult:
    workspace: Workspace
    onboarding_plan: OnboardingPlan
    setup_commands: OnboardingSetupCommands
    runtime_setup_guide: RuntimeSetupGuide
    readiness: WorkspaceReadiness
    next_steps: list[str]
