"""Project Watcher: deterministic diff of two graph snapshots + a digest.

The watcher answers "what changed since I last looked?" purely by comparing two
``ProjectGraph`` snapshots — no LLM is needed for the facts. Entities are matched
by id, findings by id. The digest turns the raw diff into a small, ordered set of
human-readable highlights (new environments, new cloud services, new/resolved
risks, new pipelines/services, and counts for the noisier kinds).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.domain.project_graph import (
    EntityType,
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
    ProjectSnapshotMeta,
)

if TYPE_CHECKING:
    # Imported for type annotations only; the runtime import lives in the function
    # that constructs it, to keep the domain module import-light.
    from app.core.domain.git_change_brief import GitChangeBrief

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}

# Entity types worth listing one-by-one in the digest (high signal). Other types
# (modules, dependencies, images, references, config files) are summarised as
# counts so the digest stays readable.
_LISTED_TYPES = [
    EntityType.ENVIRONMENT,
    EntityType.CLOUD_SERVICE,
    EntityType.INFRA_COMPONENT,
    EntityType.SERVICE,
    EntityType.PIPELINE,
    EntityType.APPLICATION,
]

_TYPE_LABEL = {
    EntityType.ENVIRONMENT: "environment",
    EntityType.CLOUD_SERVICE: "cloud service",
    EntityType.INFRA_COMPONENT: "infrastructure tool",
    EntityType.SERVICE: "service",
    EntityType.PIPELINE: "pipeline",
    EntityType.APPLICATION: "application",
    EntityType.MODULE: "module",
    EntityType.DEPENDENCY: "dependency",
    EntityType.CONTAINER_IMAGE: "container image",
    EntityType.REFERENCE: "external reference",
    EntityType.CONFIG_FILE: "important file",
}


def _pluralize(label: str, count: int) -> str:
    """English plural that handles 'y' → 'ies' (dependency → dependencies), so
    counts never read like '2 new dependencys'."""
    if count == 1:
        return label
    if label.endswith("y") and label[-2:-1].lower() not in "aeiou":
        return f"{label[:-1]}ies"
    return f"{label}s"


@dataclass(frozen=True)
class GraphDiff:
    is_baseline: bool
    added_entities: list[ProjectEntity] = field(default_factory=list)
    removed_entities: list[ProjectEntity] = field(default_factory=list)
    added_findings: list[ProjectFinding] = field(default_factory=list)
    resolved_findings: list[ProjectFinding] = field(default_factory=list)
    added_analyzers: list[str] = field(default_factory=list)
    removed_analyzers: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_entities
            or self.removed_entities
            or self.added_findings
            or self.resolved_findings
        )


def diff_graphs(previous: ProjectGraph | None, current: ProjectGraph) -> GraphDiff:
    if previous is None:
        return GraphDiff(is_baseline=True)

    prev_entities = {e.id: e for e in previous.entities}
    cur_entities = {e.id: e for e in current.entities}
    prev_findings = {f.id: f for f in previous.findings}
    cur_findings = {f.id: f for f in current.findings}
    prev_analyzers = set(previous.analyzers_run)
    cur_analyzers = set(current.analyzers_run)

    return GraphDiff(
        is_baseline=False,
        added_entities=[cur_entities[i] for i in cur_entities if i not in prev_entities],
        removed_entities=[prev_entities[i] for i in prev_entities if i not in cur_entities],
        added_findings=[cur_findings[i] for i in cur_findings if i not in prev_findings],
        resolved_findings=[prev_findings[i] for i in prev_findings if i not in cur_findings],
        added_analyzers=sorted(cur_analyzers - prev_analyzers),
        removed_analyzers=sorted(prev_analyzers - cur_analyzers),
    )


def _entities_of(entities: list[ProjectEntity], entity_type: str) -> list[ProjectEntity]:
    return sorted((e for e in entities if e.type == entity_type), key=lambda e: e.name)


def _highlights(diff: GraphDiff) -> list[dict]:
    highlights: list[dict] = []

    # Newly detected analyzers (a whole technology appeared).
    for analyzer in diff.added_analyzers:
        highlights.append(
            {
                "kind": "analyzer_added",
                "text": f"{analyzer} is now detected in the project",
            }
        )

    # New risks first, ordered by severity.
    for finding in sorted(diff.added_findings, key=lambda f: _SEVERITY_RANK.get(f.severity, 99)):
        highlights.append(
            {
                "kind": "risk_added",
                "severity": finding.severity,
                "text": finding.title,
                "source_file": finding.source_file,
            }
        )

    # High-signal new entities, listed individually.
    for entity_type in _LISTED_TYPES:
        for entity in _entities_of(diff.added_entities, entity_type):
            highlights.append(
                {
                    "kind": "entity_added",
                    "entity_type": entity_type,
                    "text": f"New {_TYPE_LABEL[entity_type]}: {entity.name}",
                    "source_file": entity.source_file,
                }
            )

    # Resolved risks.
    for finding in diff.resolved_findings:
        highlights.append({"kind": "risk_resolved", "text": f"Resolved: {finding.title}"})

    # Removed high-signal entities.
    for entity_type in _LISTED_TYPES:
        for entity in _entities_of(diff.removed_entities, entity_type):
            highlights.append(
                {
                    "kind": "entity_removed",
                    "entity_type": entity_type,
                    "text": f"Removed {_TYPE_LABEL[entity_type]}: {entity.name}",
                }
            )

    # Noisier kinds summarised as counts.
    noisy = [
        EntityType.MODULE,
        EntityType.DEPENDENCY,
        EntityType.CONTAINER_IMAGE,
        EntityType.REFERENCE,
    ]
    for entity_type in noisy:
        added = len(_entities_of(diff.added_entities, entity_type))
        if added:
            label = _TYPE_LABEL[entity_type]
            highlights.append(
                {
                    "kind": "count_added",
                    "entity_type": entity_type,
                    "text": f"{added} new {_pluralize(label, added)}",
                }
            )

    # Tag each line so the UI can lead with what a person cares about (real
    # risks) and tuck the analyzer bookkeeping (counts, "detected X", structural
    # adds/removes) under a collapsed "structural details" section.
    for highlight in highlights:
        highlight["category"] = _highlight_category(highlight["kind"], highlight.get("severity"))
    return highlights


def _highlight_category(kind: str, severity: str | None) -> str:
    if kind == "risk_added":
        # "info" findings are really just "we detected X" — not a real risk.
        return "structural" if (severity or "").lower() == "info" else "risk"
    if kind == "risk_resolved":
        return "risk"
    return "structural"


def build_watch_digest(
    diff: GraphDiff,
    previous_meta: ProjectSnapshotMeta | None,
    current_meta: ProjectSnapshotMeta,
    git_brief: "GitChangeBrief | None" = None,
) -> dict:
    from app.core.domain.git_change_brief import format_git_brief, top_changed_areas

    counts = {
        "entities_added": len(diff.added_entities),
        "entities_removed": len(diff.removed_entities),
        "findings_added": len(diff.added_findings),
        "findings_resolved": len(diff.resolved_findings),
    }

    git_lines = format_git_brief(git_brief) if git_brief is not None else []

    if diff.is_baseline:
        summary = (
            f"Baseline recorded: {current_meta.entity_count} item(s) and "
            f"{current_meta.finding_count} finding(s). Future checks will report what changed."
        )
    elif not diff.has_changes:
        summary = "No changes since the last check."
    else:
        parts: list[str] = []
        if counts["findings_added"]:
            parts.append(f"{counts['findings_added']} new risk(s)")
        if counts["findings_resolved"]:
            parts.append(f"{counts['findings_resolved']} resolved")
        if counts["entities_added"]:
            parts.append(f"{counts['entities_added']} added")
        if counts["entities_removed"]:
            parts.append(f"{counts['entities_removed']} removed")
        summary = "Since the last check: " + ", ".join(parts) + "."

    # Lead with the human, git-grounded headline when we have one.
    if git_lines:
        summary = git_lines[0]

    return {
        "baseline": diff.is_baseline,
        "has_changes": diff.has_changes or bool(git_brief and git_brief.commit_count),
        "checked_at": current_meta.created_at,
        "previous_checked_at": previous_meta.created_at if previous_meta else None,
        "summary": summary,
        "git_brief": {
            "lines": git_lines,
            "commit_count": git_brief.commit_count if git_brief else 0,
            "authors": git_brief.authors if git_brief else [],
            "areas": [
                {"area": area, "files": files}
                for area, files in (top_changed_areas(git_brief.changed_paths) if git_brief else [])
            ],
            # Raw commit subjects, kept so an optional one-tap LLM summary can be
            # produced without re-querying git (and reflecting exactly this digest).
            "commit_subjects": git_brief.commit_subjects if git_brief else [],
        },
        "git_head": git_brief.head if git_brief else None,
        "highlights": _highlights(diff),
        "counts": counts,
    }
