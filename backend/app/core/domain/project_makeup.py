"""What a project is made of, in one line — and in one vocabulary.

The single-project view learned to describe a project by what it contains: a wiki is
"169 page(s) of documentation across 5 area(s), 23 of them decision records", an infra
repo is "Terraform stack; 5 environment(s)". The group view never got the memo. It
described every member in the old dialect — services, environments, pipelines — so a
wiki with a fully built map appeared in the group as "Not analyzed yet": the map was
there, and the aggregate was reading for things a wiki does not have.

One description, one vocabulary, both places. This is the only place that decides how a
project is announced; anything else asking the question calls it.
"""

from app.core.domain.project_graph import EntityType, ProjectGraph
from app.core.domain.project_type import KIND_INFRASTRUCTURE, classify_project


def makeup_counts(graph: ProjectGraph | None) -> dict[str, int]:
    """Every kind of thing a project can be made of, counted. Zero is a real answer;
    absence of a key would not be."""
    if graph is None:
        return dict.fromkeys(MAKEUP_KEYS, 0)
    counts = {
        "services": len(graph.entities_of_type(EntityType.SERVICE)),
        "environments": len(graph.entities_of_type(EntityType.ENVIRONMENT)),
        "pipelines": len(graph.entities_of_type(EntityType.PIPELINE)),
        "infrastructure": len(graph.entities_of_type(EntityType.INFRA_COMPONENT)),
        # A wiki's facts count too — they are what a documentation project is made of,
        # and leaving them out of the group's arithmetic is what made one disappear.
        "pages": len(graph.entities_of_type(EntityType.DOCUMENT))
        + len(graph.entities_of_type(EntityType.DECISION)),
        "decisions": len(graph.entities_of_type(EntityType.DECISION)),
        "areas": len(graph.entities_of_type(EntityType.TOPIC)),
        "modules": len(graph.entities_of_type(EntityType.MODULE)),
        "tables": len(graph.entities_of_type(EntityType.TABLE)),
        "tests": len(graph.entities_of_type(EntityType.TEST_SUITE)),
    }
    return counts


MAKEUP_KEYS = (
    "services",
    "environments",
    "pipelines",
    "infrastructure",
    "pages",
    "decisions",
    "areas",
    "modules",
    "tables",
    "tests",
)


def frameworks_of(graph: ProjectGraph) -> set[str]:
    frameworks: set[str] = set()
    for app in graph.entities_of_type(EntityType.APPLICATION):
        raw = app.metadata.get("frameworks", "")
        frameworks |= {f.strip() for f in raw.split(",") if f.strip()}
    return frameworks


def technologies_of(graph: ProjectGraph | None) -> list[str]:
    """The tools this project is built with.

    Not the names of its CI jobs. The group's technology list read "Detect Changed
    Directories, Terragrunt Apply, Terragrunt Plan" — those are things that run, not
    things the project is written in, and a person scanning for "what is this built
    with" learns nothing from them. Pipelines are counted; they are not technologies.
    """
    if graph is None:
        return []
    names = {e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT)}
    names |= {e.name for e in graph.entities_of_type(EntityType.DEPENDENCY)}
    names |= frameworks_of(graph)
    return sorted(names)


def describe_project(graph: ProjectGraph | None) -> str:
    """The one-line answer to "what is this?", led by whatever the project mostly is.

    A Terraform repository is not announced as a Python application because it has one
    helper script; a folder of documentation is announced as documentation before
    anything else is said about it.
    """
    if graph is None:
        return "No map built yet — build one to see what this project is made of."

    applications = graph.entities_of_type(EntityType.APPLICATION)
    modules = graph.entities_of_type(EntityType.MODULE)
    infra = graph.entities_of_type(EntityType.INFRA_COMPONENT)
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    environments = graph.entities_of_type(EntityType.ENVIRONMENT)
    frameworks = frameworks_of(graph)

    classification = classify_project(graph)
    parts: list[str] = []
    if classification.kind == KIND_INFRASTRUCTURE:
        parts.append(classification.label)
        if applications:
            parts.append(
                f"with a {sorted(frameworks)[0]} component" if frameworks else "with helper scripts"
            )
    else:
        if applications:
            app_part = classification.label
            if modules:
                app_part += f", {len(modules)} module(s)"
            parts.append(app_part)
        if infra:
            parts.append("infrastructure: " + ", ".join(sorted(e.name for e in infra)))
        if pipelines:
            parts.append(f"{len(pipelines)} CI/CD pipeline(s)")
    if environments:
        parts.append(
            f"{len(environments)} environment(s): " + ", ".join(sorted(e.name for e in environments))
        )

    counts = makeup_counts(graph)
    if counts["pages"]:
        doc_part = f"{counts['pages']} page(s) of documentation"
        if counts["areas"]:
            doc_part += f" across {counts['areas']} area(s)"
        if counts["decisions"]:
            doc_part += f", {counts['decisions']} of them decision records"
        parts.insert(0, doc_part)

    if not parts:
        return "Nothing the analyzers recognise yet — the files are still searchable in Ask."
    return "Detected " + "; ".join(parts) + "."
