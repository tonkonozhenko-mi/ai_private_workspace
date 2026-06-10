from pydantic import BaseModel


class LocalDataBackupHintResponse(BaseModel):
    label: str
    command: str


class LocalDataSafetyResponse(BaseModel):
    status: str
    app_data_dir: str
    database_path: str
    database_exists: bool
    database_size_bytes: int
    repository: str
    vector_store: str
    llm_provider: str
    embedding_provider: str
    workspaces_count: int | None
    conversations_count: int | None
    saved_reports_count: int | None
    answer_notes_count: int | None
    warnings: list[str]
    protected_paths: list[str]
    safe_update_excludes: list[str]
    backup_hints: list[LocalDataBackupHintResponse]



class StartupChecklistItemResponse(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    detail: str
    action_label: str | None = None
    copy_command: str | None = None


class StartupChecklistResponse(BaseModel):
    status: str
    summary: str
    items: list[StartupChecklistItemResponse]
    safe_to_continue: bool
    safety_note: str
