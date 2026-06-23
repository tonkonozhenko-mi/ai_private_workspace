"""Pure tests for the human-readable risk explanation derivation."""

from app.core.domain.project_graph import (
    Confidence,
    FindingCategory,
    ProjectFinding,
    Severity,
)
from app.core.domain.risk_explanation import explain_finding


def _finding(**kwargs) -> ProjectFinding:
    base = dict(
        id="f1",
        category=FindingCategory.SECURITY,
        severity=Severity.HIGH,
        title="Broad IAM action",
        explanation='IAM policy contains Action: "*".',
        analyzer="terraform",
        confidence=Confidence.HIGH,
        source_file="infra/iam/app_role.tf",
        recommendation="Scope the action to what the role needs.",
    )
    base.update(kwargs)
    return ProjectFinding(**base)


def test_explanation_is_review_oriented_not_a_verdict():
    out = explain_finding(_finding()).as_dict()
    # Never asserts the thing is broken — only that it needs a human look.
    assert "Needs review" in out["review_status"]
    assert out["where"] == "infra/iam/app_role.tf"
    assert out["what"] == 'IAM policy contains Action: "*".'
    assert out["suggested_idea"] == "Scope the action to what the role needs."


def test_why_and_checks_follow_category():
    sec = explain_finding(_finding(category=FindingCategory.SECURITY)).as_dict()
    test = explain_finding(_finding(category=FindingCategory.TESTING)).as_dict()
    assert "access" in sec["why_it_may_matter"].lower()
    assert sec["check_manually"]  # non-empty
    assert "test" in " ".join(test["check_manually"]).lower()
    # Different categories give different guidance.
    assert sec["why_it_may_matter"] != test["why_it_may_matter"]


def test_low_confidence_leans_on_confirm_first():
    low = explain_finding(_finding(confidence=Confidence.LOW)).as_dict()
    assert "confirm" in low["review_status"].lower()
    assert "confirm" in low["confidence_label"].lower()


def test_unknown_category_falls_back_to_general():
    out = explain_finding(_finding(category="weird-unknown")).as_dict()
    assert out["why_it_may_matter"]  # falls back, never crashes
    assert out["check_manually"]


def test_missing_recommendation_is_none():
    out = explain_finding(_finding(recommendation=None)).as_dict()
    assert out["suggested_idea"] is None
