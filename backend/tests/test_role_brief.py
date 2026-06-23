"""Pure tests for the role brief and suggested questions."""

from app.core.domain.project_graph import (
    EntityType,
    FindingCategory,
    ProjectEntity,
    ProjectFinding,
    ProjectGraph,
    Severity,
)
from app.core.domain.role_brief import build_role_brief, suggested_questions
from app.core.domain.role_lens import role_lens_for


def _entity(etype: str, name: str) -> ProjectEntity:
    return ProjectEntity(id=f"{etype}:{name}", type=etype, name=name, analyzer="t")


def _graph() -> ProjectGraph:
    return ProjectGraph(
        workspace_id="w",
        entities=[
            _entity(EntityType.ENVIRONMENT, "prod"),
            _entity(EntityType.ENVIRONMENT, "dev"),
            _entity(EntityType.PIPELINE, "deploy"),
            _entity(EntityType.INFRA_COMPONENT, "vpc"),
            _entity(EntityType.MODULE, "billing"),
        ],
        findings=[
            ProjectFinding(
                id="f1",
                category=FindingCategory.SECURITY,
                severity=Severity.HIGH,
                title="Broad IAM action",
                explanation="...",
                analyzer="terraform",
            ),
            ProjectFinding(
                id="f2",
                category=FindingCategory.TESTING,
                severity=Severity.LOW,
                title="Thin test coverage",
                explanation="...",
                analyzer="python",
            ),
        ],
    )


def test_brief_only_lists_present_priority_types():
    brief = build_role_brief(_graph(), role_lens_for("devops")).as_dict()
    labels = [f["label"] for f in brief["facts"]]
    # DevOps leads with infra/env/pipeline — all present here.
    assert "Environments" in labels
    assert "Pipelines" in labels
    # Environments fact counts both env entities.
    env = next(f for f in brief["facts"] if f["label"] == "Environments")
    assert env["count"] == 2
    assert "prod" in env["examples"]


def test_brief_focus_mentions_role():
    brief = build_role_brief(_graph(), role_lens_for("devops")).as_dict()
    assert "DevOps" in brief["focus"]


def test_devops_risks_lead_with_security():
    brief = build_role_brief(_graph(), role_lens_for("devops")).as_dict()
    # Security is highlighted for DevOps, so the IAM finding sorts first.
    assert brief["top_risks"][0] == "Broad IAM action"


def test_suggested_questions_only_when_answerable():
    # A graph with no cloud services must not offer the cloud question.
    qs = suggested_questions(_graph(), role_lens_for("devops"))
    assert all("cloud services" not in q.lower() for q in qs)
    # But it can answer deployment/env questions.
    assert any("deployed" in q.lower() or "environments" in q.lower() for q in qs)
    # Always-on questions are present.
    assert any("start reading" in q.lower() for q in qs)


def test_suggested_questions_role_ordering():
    g = _graph()
    devops_qs = suggested_questions(g, role_lens_for("devops"))
    dev_qs = suggested_questions(g, role_lens_for("developer"))
    # Different roles surface a different leading question.
    assert devops_qs[0] != dev_qs[0] or devops_qs != dev_qs


def test_empty_graph_still_offers_general_questions():
    g = ProjectGraph(workspace_id="w")
    qs = suggested_questions(g, role_lens_for("developer"))
    assert any("start reading" in q.lower() for q in qs)
    assert any("risks" in q.lower() for q in qs)
