"""The five canonical roles resolve, and legacy modes fold onto them."""

from app.core.domain.role_lens import role_lens_for


def test_five_canonical_roles_have_distinct_lenses():
    roles = ["developer", "devops", "tester", "business_analyst", "manager"]
    labels = {role_lens_for(r).label for r in roles}
    # Five roles → five distinct labels (no accidental aliasing).
    assert len(labels) == 5
    assert role_lens_for("manager").label == "Manager"
    assert role_lens_for("tester").label == "Tester / QA"
    assert role_lens_for("business_analyst").label == "Business analyst"


def test_legacy_modes_fold_onto_canonical_roles():
    # Old assistant_modes must still resolve to a sensible lens.
    assert role_lens_for("documentation").role == "developer"
    assert role_lens_for("support_incident").role == "devops"
    assert role_lens_for("incident_support").role == "devops"
    assert role_lens_for("manager_summary").role == "manager"


def test_unknown_mode_falls_back_to_developer():
    assert role_lens_for("totally-unknown").role == "developer"
    assert role_lens_for(None).role == "developer"
