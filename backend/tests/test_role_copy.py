"""What the roles are promised, and whether we can keep the promise.

Copy is not decoration here: "where coverage is thin" promises a number the app
never computes (it does not run your tests), and a tester whose view opened on
Deployment was being handed the DevOps screen with a different label. These pin
the wording and the ordering that the live review found wrong.
"""

from pathlib import Path

from app.core.domain.project_graph import EntityType, ProjectEntity, ProjectGraph
from app.core.domain.role_brief import suggested_questions
from app.core.domain.role_lens import Section, role_lens_for

_SKILL_LIBRARY = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "skillLibrary.ts"
)


def _graph(*types: str) -> ProjectGraph:
    return ProjectGraph(
        workspace_id="w",
        entities=[
            ProjectEntity(id=f"{t}:{i}", type=t, name=f"{t}-{i}", analyzer="test")
            for i, t in enumerate(types)
        ],
        relations=[],
        findings=[],
    )


def test_a_tester_opens_on_risks_not_on_deployment():
    order = role_lens_for("tester").section_order
    assert order[0] == Section.SUMMARY
    assert order.index(Section.RISKS) < order.index(Section.DEPLOYMENT)


def test_a_manager_is_offered_what_changed_recently():
    graph = _graph(EntityType.PIPELINE, EntityType.ENVIRONMENT, EntityType.SERVICE)
    assert "What changed recently?" in suggested_questions(graph, role_lens_for("manager"))


def test_the_other_roles_are_not_offered_the_managers_question():
    graph = _graph(EntityType.PIPELINE, EntityType.ENVIRONMENT, EntityType.SERVICE)
    assert "What changed recently?" not in suggested_questions(graph, role_lens_for("devops"))


def test_a_tester_is_offered_a_question_about_tests():
    graph = _graph(EntityType.TEST_SUITE, EntityType.PIPELINE, EntityType.ENVIRONMENT)
    questions = suggested_questions(graph, role_lens_for("tester"))
    assert any("test" in question.lower() for question in questions)


def test_we_never_promise_coverage_we_do_not_measure():
    """The app does not run the tests, so it cannot say how thin coverage is."""
    library = _SKILL_LIBRARY.read_text(encoding="utf-8").lower()
    assert "coverage is thin" not in library
