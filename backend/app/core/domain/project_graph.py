"""Project Intelligence — the normalized, role-neutral project graph.

These are *facts* extracted deterministically by analyzers (Terraform, CI, …),
never guessed by an LLM. Every entity/relation/finding carries its source,
evidence, confidence and a status (confirmed / inferred / needs_confirmation),
so the UI can show exactly why each statement is made and what is uncertain.

Role lenses (see ``role_lens.py``) only re-order and prioritise this graph for a
given role — they never change the facts here.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Vocabularies. Kept deliberately small for M1; grow as analyzers prove a need.
# ---------------------------------------------------------------------------


class EntityType:
    SERVICE = "service"
    ENVIRONMENT = "environment"
    PIPELINE = "pipeline"
    PIPELINE_JOB = "pipeline_job"
    INFRA_COMPONENT = "infra_component"
    CONFIG_FILE = "config_file"
    CONTAINER_IMAGE = "container_image"
    APPLICATION = "application"  # a runnable app (e.g. a Python service)
    MODULE = "module"  # an internal top-level code package
    DEPENDENCY = "dependency"  # a notable third-party library


class RelationType:
    DEPENDS_ON = "depends_on"
    DEPLOYS = "deploys"
    CONFIGURES = "configures"
    TRIGGERS = "triggers"
    BUILDS = "builds"
    DEFINED_IN = "defined_in"
    INCLUDES = "includes"
    RUNS = "runs"


class Confidence:
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceStatus:
    """How sure we are a fact is real."""

    CONFIRMED = "confirmed"  # directly parsed from a file
    INFERRED = "inferred"  # derived (e.g. environment from a directory name)
    NEEDS_CONFIRMATION = "needs_confirmation"  # plausible, but ask the team


class FindingCategory:
    SECURITY = "security"
    RELIABILITY = "reliability"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    TESTING = "testing"
    OBSERVABILITY = "observability"
    GENERAL = "general"


class Severity:
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Graph elements.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRange:
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ProjectEntity:
    id: str
    type: str
    name: str
    analyzer: str
    confidence: str = Confidence.HIGH
    status: str = EvidenceStatus.CONFIRMED
    source_file: str | None = None
    source_range: SourceRange | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectRelation:
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    analyzer: str
    confidence: str = Confidence.HIGH
    source_file: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectFinding:
    id: str
    category: str
    severity: str
    title: str
    explanation: str
    analyzer: str
    confidence: str = Confidence.HIGH
    source_file: str | None = None
    evidence: list[str] = field(default_factory=list)
    recommendation: str | None = None


@dataclass(frozen=True)
class ProjectGraph:
    """The full role-neutral project graph for one workspace snapshot."""

    workspace_id: str
    entities: list[ProjectEntity] = field(default_factory=list)
    relations: list[ProjectRelation] = field(default_factory=list)
    findings: list[ProjectFinding] = field(default_factory=list)
    # Which analyzers actually ran (and which were skipped), so the UI can be
    # honest about coverage instead of implying completeness.
    analyzers_run: list[str] = field(default_factory=list)
    analyzers_skipped: list[str] = field(default_factory=list)

    def entities_of_type(self, entity_type: str) -> list[ProjectEntity]:
        return [entity for entity in self.entities if entity.type == entity_type]

    def relations_of_type(self, relation_type: str) -> list[ProjectRelation]:
        return [rel for rel in self.relations if rel.relation_type == relation_type]


@dataclass(frozen=True)
class ProjectSnapshotMeta:
    """Lightweight metadata for a persisted graph snapshot."""

    id: str
    workspace_id: str
    created_at: str
    entity_count: int
    relation_count: int
    finding_count: int
    analyzers_run: list[str] = field(default_factory=list)
    analyzers_skipped: list[str] = field(default_factory=list)
    # A signature of the scan the graph was built from, so the UI can warn when
    # the snapshot is stale relative to the current files.
    scan_signature: str | None = None
