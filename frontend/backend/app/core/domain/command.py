from dataclasses import dataclass
from enum import Enum


class CommandStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class CommandRisk(str, Enum):
    READONLY = "readonly"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CommandProposal:
    id: str
    workspace_id: str
    command: str
    cwd: str
    reason: str
    risk: str
    status: str
    created_at: str
    approved_at: str | None
    rejected_at: str | None
    executed_at: str | None
    stdout: str | None
    stderr: str | None
    exit_code: int | None
    policy_allowed: bool | None = None
    policy_mode: str | None = None
    policy_reason: str | None = None
