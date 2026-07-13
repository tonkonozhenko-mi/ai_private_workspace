"""A group of a repository and a wiki must be able to see both of them.

The union of sources works — one answer carrying a decision from the wiki and the files
that implement it from the Terraform repo. But the group's *aggregate* counted only the
things a code repository is made of, so the wiki, with a fully built map of 169 pages,
appeared in the group as "Not analyzed yet" — the map was there; the summary was
reading it for services and pipelines.
"""

from app.core.domain.project_graph import ProjectEntity, ProjectGraph
from app.core.domain.project_makeup import describe_project, makeup_counts, technologies_of


def _wiki_graph() -> ProjectGraph:
    entities = [
        ProjectEntity(id=f"d{i}", type="document", name=f"Page {i}", analyzer="documentation")
        for i in range(140)
    ]
    entities += [
        ProjectEntity(id=f"a{i}", type="decision", name=f"[ADR-{i}]", analyzer="documentation")
        for i in range(23)
    ]
    entities += [
        ProjectEntity(id=f"t{i}", type="topic", name=f"AREA{i}", analyzer="documentation")
        for i in range(5)
    ]
    return ProjectGraph(workspace_id="wiki", entities=entities)


def _infra_graph() -> ProjectGraph:
    entities = [
        ProjectEntity(id="tf", type="infra_component", name="Terraform", analyzer="terraform"),
        ProjectEntity(id="tg", type="infra_component", name="Terragrunt", analyzer="terragrunt"),
        ProjectEntity(id="e1", type="environment", name="prod", analyzer="terragrunt"),
        # Pipelines carry the names of CI jobs — "Terragrunt Apply", "Detect Changed
        # Directories". They are things that run, not things the project is built with.
        ProjectEntity(id="p1", type="pipeline", name="Terragrunt Apply", analyzer="github_actions"),
    ]
    return ProjectGraph(workspace_id="infra", entities=entities)


def test_a_wiki_with_a_map_is_not_reported_as_unanalyzed():
    counts = makeup_counts(_wiki_graph())
    assert counts["pages"] == 163
    assert counts["decisions"] == 23
    assert counts["areas"] == 5

    description = describe_project(_wiki_graph())
    assert "163 pages of documentation" in description
    assert "23 of them decision records" in description
    assert "across 5 areas" in description
    assert "Not analyzed" not in description


def test_the_group_can_add_a_wiki_and_a_repository_together():
    """The point of a group: one arithmetic over both kinds of project."""
    totals: dict[str, int] = {}
    for graph in (_wiki_graph(), _infra_graph()):
        for key, value in makeup_counts(graph).items():
            totals[key] = totals.get(key, 0) + value

    assert totals["pages"] == 163
    assert totals["environments"] == 1
    assert totals["infrastructure"] == 2


def test_the_names_of_ci_jobs_are_not_technologies():
    """ "Detect Changed Directories" is a thing that runs, not a thing this is built
    with. A person scanning "what is this written in" learns nothing from it."""
    technologies = technologies_of(_infra_graph())
    assert technologies == ["Terraform", "Terragrunt"]
    assert "Terragrunt Apply" not in technologies


def test_a_project_with_no_map_says_so_plainly():
    assert "No map built yet" in describe_project(None)
