from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceFileWriteResult:
    workspace_id: str
    relative_path: str
    bytes_written: int
    replaced_existing: bool
    status: str
