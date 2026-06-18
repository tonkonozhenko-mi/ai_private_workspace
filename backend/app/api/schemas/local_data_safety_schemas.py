from pydantic import BaseModel


class DesktopStartupCommandResponse(BaseModel):
    label: str
    command: str
    description: str


class FirstLaunchChecklistItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    detail: str
    user_action: str | None = None


class FirstLaunchReadinessResponse(BaseModel):
    status: str
    title: str
    summary: str
    checklist: list[FirstLaunchChecklistItemResponse]
    recommended_flow: list[str]
    copy_commands: list[DesktopStartupCommandResponse]
    safety_note: str
