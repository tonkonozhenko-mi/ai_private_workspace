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


class DataFolderResponse(BaseModel):
    """Where everything this app knows about you is kept.

    One folder, one sentence: back it up by copying it. Notes and chats are the
    only irreplaceable things in it — the search index is rebuilt from your own
    files whenever it is missing.
    """

    path: str
    exists: bool
    opened: bool = False
    # Why it could not be opened, when it could not. Empty on success and on a
    # plain read — an empty string is not an apology, it is the absence of one.
    error: str = ""
