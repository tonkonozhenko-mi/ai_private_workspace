from pydantic import BaseModel

from app.core.domain.local_model_install_status import (
    LocalModelInstallStatus,
    LocalModelStatusItem,
)


class LocalModelStatusItemResponse(BaseModel):
    provider: str
    model: str
    model_type: str
    display_name: str
    recommended: bool
    status: str
    detail: str
    installed_as: str | None
    size_bytes: int | None
    install_command: str


class LocalModelInstallStatusResponse(BaseModel):
    title: str
    summary: str
    status: str
    provider: str
    runtime_reachable: bool
    runtime_url: str
    installed_count: int
    items: list[LocalModelStatusItemResponse]
    safety_notes: list[str]


def to_local_model_status_item_response(
    item: LocalModelStatusItem,
) -> LocalModelStatusItemResponse:
    return LocalModelStatusItemResponse(
        provider=item.provider,
        model=item.model,
        model_type=item.model_type,
        display_name=item.display_name,
        recommended=item.recommended,
        status=item.status,
        detail=item.detail,
        installed_as=item.installed_as,
        size_bytes=item.size_bytes,
        install_command=item.install_command,
    )


def to_local_model_install_status_response(
    status: LocalModelInstallStatus,
) -> LocalModelInstallStatusResponse:
    return LocalModelInstallStatusResponse(
        title=status.title,
        summary=status.summary,
        status=status.status,
        provider=status.provider,
        runtime_reachable=status.runtime_reachable,
        runtime_url=status.runtime_url,
        installed_count=status.installed_count,
        items=[to_local_model_status_item_response(item) for item in status.items],
        safety_notes=status.safety_notes,
    )
