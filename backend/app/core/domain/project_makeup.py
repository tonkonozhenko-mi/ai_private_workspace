"""What a project is made of, in one line — and in one vocabulary.

The single-project view learned to describe a project by what it contains: a wiki is
"169 pages of documentation across 5 areas, 23 of them decision records", an infra repo
is "a Terraform stack across 5 environments". The group view described every member in
the old dialect — services, environments, pipelines — so a wiki with a fully built map
appeared in the group as "Not analyzed yet": the map was there, and the aggregate was
reading it for things a wiki does not have.

One description, one vocabulary, both places. Two rules hold it honest:

* **Lead with what the project mostly is.** A Terraform monorepo with 938 .tf files and
  106 READMEs announced itself as "106 pages of documentation" — technically the pages
  were counted first, so they went first. Documentation *in* a repository is not what
  the repository is; it goes last, and it is called what it is: documents, not pages.
* **One sentence, each word once.** The old line read "infrastructure project (Terraform,
  CI/CD), 6 module(s); infrastructure: Terraform; 4 CI/CD pipeline(s)" — a train of
  semicolons that says infrastructure twice and trusts the reader to sort it out.
"""

from app.core.domain.project_graph import EntityType, ProjectGraph
from app.core.domain.project_type import KIND_INFRASTRUCTURE, classify_project

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


def makeup_counts(graph: ProjectGraph | None) -> dict[str, int]:
    """Every kind of thing a project can be made of, counted. Zero is a real answer;
    a missing key would not be."""
    if graph is None:
        return dict.fromkeys(MAKEUP_KEYS, 0)
    return {
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


def frameworks_of(graph: ProjectGraph) -> set[str]:
    frameworks: set[str] = set()
    for app in graph.entities_of_type(EntityType.APPLICATION):
        raw = app.metadata.get("frameworks", "")
        frameworks |= {f.strip() for f in raw.split(",") if f.strip()}
    return frameworks


def technologies_of(graph: ProjectGraph | None) -> list[str]:
    """The tools this project is built with.

    Not the names of its CI jobs. The technology list read "Detect Changed Directories,
    Terragrunt Apply, Terragrunt Plan" — those are things that run, not things the
    project is written in. Pipelines are counted; they are not technologies.
    """
    if graph is None:
        return []
    names = {e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT)}
    names |= {e.name for e in graph.entities_of_type(EntityType.DEPENDENCY)}
    names |= frameworks_of(graph)
    return sorted(names)


def is_documentation_project(graph: ProjectGraph | None) -> bool:
    """Is this a body of documentation, or a project that contains some?

    The difference is what the project HAS besides its pages. A wiki has pages and
    nothing else; a Terraform monorepo has 938 .tf files and a README in every module.
    """
    if graph is None:
        return False
    counts = makeup_counts(graph)
    if not counts["pages"]:
        return False
    has_a_system = bool(
        counts["infrastructure"]
        or counts["pipelines"]
        or counts["services"]
        or counts["modules"]
        or counts["tables"]
        or graph.entities_of_type(EntityType.APPLICATION)
    )
    return not has_a_system


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"


def _article(noun: str) -> str:
    """ "a Python application", but "an infrastructure project"."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def describe_project(graph: ProjectGraph | None) -> str:
    """One sentence: what this project is, led by whatever it mostly is."""
    if graph is None:
        return "No map built yet — build one to see what this project is made of."

    counts = makeup_counts(graph)
    applications = graph.entities_of_type(EntityType.APPLICATION)
    infra = graph.entities_of_type(EntityType.INFRA_COMPONENT)
    environments = graph.entities_of_type(EntityType.ENVIRONMENT)
    frameworks = frameworks_of(graph)
    classification = classify_project(graph)

    # A folder of documentation is documentation before it is anything else.
    if is_documentation_project(graph):
        line = "Detected " + _plural(counts["pages"], "page") + " of documentation"
        if counts["areas"]:
            line += " across " + _plural(counts["areas"], "area")
        if counts["decisions"]:
            line += f", {counts['decisions']} of them decision records"
        return line + "."

    # Otherwise the project leads with what it is built of. Each thing said once — the
    # label may already name the infrastructure ("infrastructure project (Terraform,
    # CI/CD)"), and appending "on Terraform" to that said it twice.
    label = classification.label or "project"
    lead = f"{_article(label)} {label}"
    names_its_infra = label.lower().startswith("infrastructure")
    if classification.kind == KIND_INFRASTRUCTURE:
        if applications:
            lead += (
                f" with a {sorted(frameworks)[0]} component"
                if frameworks
                else " with helper scripts"
            )
    elif applications and infra and not names_its_infra:
        lead += " on " + ", ".join(sorted(e.name for e in infra))

    tail: list[str] = []
    if counts["modules"]:
        tail.append(_plural(counts["modules"], "module"))
    if counts["services"]:
        tail.append(_plural(counts["services"], "service"))
    if counts["pipelines"]:
        tail.append(_plural(counts["pipelines"], "CI/CD pipeline"))
    if environments:
        tail.append(
            _plural(len(environments), "environment")
            + " ("
            + ", ".join(sorted(e.name for e in environments))
            + ")"
        )
    if counts["tables"]:
        tail.append(_plural(counts["tables"], "table"))
    if counts["tests"]:
        tail.append(_plural(counts["tests"], "test suite"))
    # Documentation *inside* a repository is a part of it, not the point of it — so it
    # comes last, and it is called what it is. "106 pages" led a Terraform monorepo's
    # description; 938 .tf files went unmentioned.
    if counts["pages"]:
        tail.append(_plural(counts["pages"], "document"))

    if not tail:
        return f"Detected {lead}."
    if len(tail) == 1:
        return f"Detected {lead} with {tail[0]}."
    return f"Detected {lead} with {', '.join(tail[:-1])} and {tail[-1]}."
