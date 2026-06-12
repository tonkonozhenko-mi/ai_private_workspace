from pydantic import BaseModel

from app.core.domain.local_model_install_guide import (
    LocalModelInstallGuide,
    LocalModelInstallOption,
)


class LocalModelInstallOptionResponse(BaseModel):
    provider: str
    model: str
    model_type: str
    display_name: str
    purpose: str
    estimated_size: str | None
    recommended: bool
    install_command: str
    verify_command: str
    notes: list[str]


class LocalModelInstallGuideResponse(BaseModel):
    title: str
    summary: str
    status: str
    options: list[LocalModelInstallOptionResponse]
    safety_notes: list[str]
    next_steps: list[str]


def to_local_model_install_option_response(
    option: LocalModelInstallOption,
) -> LocalModelInstallOptionResponse:
    return LocalModelInstallOptionResponse(
        provider=option.provider,
        model=option.model,
        model_type=option.model_type,
        display_name=option.display_name,
        purpose=option.purpose,
        estimated_size=option.estimated_size,
        recommended=option.recommended,
        install_command=option.install_command,
        verify_command=option.verify_command,
        notes=option.notes,
    )


def to_local_model_install_guide_response(
    guide: LocalModelInstallGuide,
) -> LocalModelInstallGuideResponse:
    return LocalModelInstallGuideResponse(
        title=guide.title,
        summary=guide.summary,
        status=guide.status,
        options=[to_local_model_install_option_response(option) for option in guide.options],
        safety_notes=guide.safety_notes,
        next_steps=guide.next_steps,
    )
