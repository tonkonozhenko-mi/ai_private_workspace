from pydantic import BaseModel, Field

from app.core.domain.onboarding_setup import OnboardingSetupCommands, SetupCommand


class GetOnboardingSetupCommandsRequest(BaseModel):
    assistant_profile_id: str = Field(..., min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    privacy_mode: str = Field(default="local_only", min_length=1)
    container_runtime: str = Field(default="podman", min_length=1)


class SetupCommandResponse(BaseModel):
    id: str
    title: str
    command: str
    description: str
    category: str
    required: bool
    risk: str
    can_be_proposed: bool


class OnboardingSetupCommandsResponse(BaseModel):
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str
    commands: list[SetupCommandResponse]
    notes: list[str]


def to_setup_command_response(command: SetupCommand) -> SetupCommandResponse:
    return SetupCommandResponse(
        id=command.id,
        title=command.title,
        command=command.command,
        description=command.description,
        category=command.category,
        required=command.required,
        risk=command.risk,
        can_be_proposed=command.can_be_proposed,
    )


def to_onboarding_setup_commands_response(
    setup_commands: OnboardingSetupCommands,
) -> OnboardingSetupCommandsResponse:
    return OnboardingSetupCommandsResponse(
        assistant_profile_id=setup_commands.assistant_profile_id,
        laptop_profile_id=setup_commands.laptop_profile_id,
        privacy_mode=setup_commands.privacy_mode,
        commands=[
            to_setup_command_response(command) for command in setup_commands.commands
        ],
        notes=setup_commands.notes,
    )
