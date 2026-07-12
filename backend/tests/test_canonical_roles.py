"""A role offered anywhere must work everywhere.

DBA was offered in the create-project form and missing from the Intelligence lens
picker, so a person who set up a DBA workspace could not switch back to their own
lens — the app forgot who they said they were. The cure is one list, and this test
is what keeps it one list: every canonical role must have a lens, a saveable
profile, starter questions and a prompt hint, and must appear in the frontend's
role library, which every picker in the UI is built from.
"""

from pathlib import Path

from app.core.domain.assistant_profile_registry import DEFAULT_ASSISTANT_PROFILES
from app.core.domain.rag_prompt import assistant_mode_lens_hint
from app.core.domain.role_lens import CANONICAL_ROLES, ROLE_LENSES, role_lens_for
from app.core.domain.starter_questions import ROLE_STARTERS

_SKILL_LIBRARY = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "skillLibrary.ts"
)


def test_every_canonical_role_has_a_lens_of_its_own():
    for role in CANONICAL_ROLES:
        assert role in ROLE_LENSES, role
        # Not merely resolvable: resolvable *to itself*. A missing lens quietly
        # falls back to developer, which is exactly the bug being pinned here.
        assert role_lens_for(role).role == role


def test_every_canonical_role_can_be_saved_as_a_profile():
    registered = {profile.id for profile in DEFAULT_ASSISTANT_PROFILES}
    assert set(CANONICAL_ROLES) <= registered


def test_every_canonical_role_brings_its_own_questions_and_prompt_hint():
    developer_hint = assistant_mode_lens_hint("developer")
    for role in CANONICAL_ROLES:
        assert ROLE_STARTERS.get(role), role
        hint = assistant_mode_lens_hint(role)
        assert hint
        if role != "developer":
            assert hint != developer_hint, role


def test_the_frontend_offers_exactly_the_canonical_roles():
    """The pickers are all built from SKILL_PRESETS, so pinning that list pins them."""
    library = _SKILL_LIBRARY.read_text(encoding="utf-8")
    for role in CANONICAL_ROLES:
        assert f'id: "{role}"' in library, f"{role} is missing from the frontend role library"
