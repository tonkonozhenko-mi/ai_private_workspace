from dataclasses import dataclass, field
from enum import Enum


class SkillCategory(str, Enum):
    DEVOPS = "devops"
    DEVELOPER = "developer"
    QA = "qa"
    DOCUMENTATION = "documentation"
    MANAGER = "manager"
    GENERAL = "general"


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    category: str
    description: str
    file_types: list[str]
    high_confidence_file_types: list[str] = field(default_factory=list)
    medium_confidence_file_types: list[str] = field(default_factory=list)
    evidence_limit: int = 5


@dataclass(frozen=True)
class SkillMatch:
    name: str
    category: str
    confidence: str
    evidence: list[str]
