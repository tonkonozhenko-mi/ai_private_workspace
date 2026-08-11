"""A skill you can switch on is a skill that can be saved.

Reported from the beta as "the skills aren't saving". Not reproduced as
described — nothing errored, and the request reached the server — but the cause
was in plain sight once the two lists were put side by side.

The app offers six roles: developer, devops, tester, business analyst, manager,
DBA. The saveable skills were a different, older set: devops, developer,
documentation, incident_support, manager_summary. Two names overlapped. So
Settings sent all six, the server kept the two it recognised, silently discarded
tester / business_analyst / manager / dba, and filled the rest from its own
defaults. Switch on Tester alone and press Save: the stored profile had nothing
enabled at all, the response said so, and reopening Settings showed DevOps
again, because a role the server never mentions falls back to its default.

Four of six toggles could not be saved, and nowhere did anything say a word.
"""

from pathlib import Path

import pytest

from app.api.schemas.skill_profile_schemas import WorkspaceSkillProfileRequest
from app.core.domain.role_lens import CANONICAL_ROLES
from app.core.domain.skill_profile import (
    DEFAULT_SKILL_INSTRUCTIONS,
    KNOWN_SKILL_IDS,
    LEGACY_SKILL_IDS,
    MAX_ACTIVE_SKILL_INSTRUCTIONS,
    SkillProfileItem,
    canonical_skill_id,
    default_skill_profile,
    normalize_skill_profile,
)

_SKILL_LIBRARY = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "skillLibrary.ts"
)


def _item(skill_id: str, *, enabled: bool = True, instructions: str = "") -> SkillProfileItem:
    return SkillProfileItem(
        id=skill_id,
        name=skill_id.title(),
        enabled=enabled,
        custom_instructions=instructions,
    )


def test_the_saveable_skills_are_the_canonical_roles():
    # One list. This is the assertion the whole complaint reduces to.
    assert KNOWN_SKILL_IDS == CANONICAL_ROLES


def test_the_request_accepts_every_role_at_once():
    """Settings sends all the roles in one request, so any cap below their number
    rejects the whole save before anything reads it.

    This was the first half of "the skills aren't saving", and the more brutal
    half: a literal ``max_length=5`` written when there were five roles. Adding
    DBA made it six, and from that day every save from the Settings panel was
    refused with a 422 — not four toggles lost, the entire request.
    """
    request = WorkspaceSkillProfileRequest(
        profile="workspace",
        skills=[
            {"id": role, "name": role, "enabled": True, "custom_instructions": "Guidance."}
            for role in CANONICAL_ROLES
        ],
    )

    assert [item.id for item in request.skills] == list(CANONICAL_ROLES)


def test_the_prompt_has_room_for_every_role_at_once():
    # Nothing stops a person enabling all of them; a lower ceiling would drop
    # one person's guidance silently, which is the same failure one layer down.
    assert MAX_ACTIVE_SKILL_INSTRUCTIONS >= len(CANONICAL_ROLES)


def test_every_canonical_role_has_default_guidance():
    assert set(DEFAULT_SKILL_INSTRUCTIONS) == set(CANONICAL_ROLES)
    for role in CANONICAL_ROLES:
        assert DEFAULT_SKILL_INSTRUCTIONS[role].strip()


@pytest.mark.parametrize("role", CANONICAL_ROLES)
def test_turning_on_one_role_and_saving_keeps_that_role_on(role):
    """The live gesture: enable exactly one role, save, read it back.

    Before the fix this passed for devops and developer and failed for the other
    four — which is exactly what "the skills aren't saving" looked like from the
    outside, since the two that worked were the two on by default.
    """
    submitted = [
        _item(candidate, enabled=candidate == role, instructions=f"Guidance for {candidate}.")
        for candidate in CANONICAL_ROLES
    ]

    profile = normalize_skill_profile(workspace_id="w1", profile="workspace", skills=submitted)

    by_id = {skill.id: skill for skill in profile.skills}
    assert by_id[role].enabled is True
    assert by_id[role].custom_instructions == f"Guidance for {role}."
    assert profile.enabled_skills_count == 1


def test_nothing_a_person_typed_is_dropped():
    submitted = [_item(role, instructions=f"Mine: {role}") for role in CANONICAL_ROLES]

    profile = normalize_skill_profile(workspace_id="w1", profile="workspace", skills=submitted)

    assert [skill.id for skill in profile.skills] == list(CANONICAL_ROLES)
    for skill in profile.skills:
        assert skill.custom_instructions == f"Mine: {skill.id}"


@pytest.mark.parametrize(("legacy", "canonical"), sorted(LEGACY_SKILL_IDS.items()))
def test_guidance_written_under_an_old_id_survives(legacy, canonical):
    """Profiles saved by earlier versions fold into the role they became.

    Dropping them would have been a second silent loss: someone's own wording,
    gone because the id it was filed under was renamed.
    """
    profile = normalize_skill_profile(
        workspace_id="w1",
        profile="workspace",
        skills=[_item(legacy, instructions="Words I wrote myself.")],
    )

    folded = next(skill for skill in profile.skills if skill.id == canonical)
    assert folded.enabled is True
    assert folded.custom_instructions == "Words I wrote myself."


def test_an_id_that_names_no_role_is_recognisably_not_a_role():
    # The endpoint refuses these rather than absorbing them; here we pin only
    # that they are distinguishable, which is what makes refusing possible.
    assert canonical_skill_id("dba") == "dba"
    assert canonical_skill_id("manager_summary") == "manager"
    assert canonical_skill_id("  DevOps  ") == "devops"
    assert canonical_skill_id("astrologer") is None
    assert canonical_skill_id("") is None


def test_the_default_guidance_is_word_for_word_what_the_app_shows():
    """Settings shows a role's default guidance and lets you edit it; the server
    holds the same text for anyone who never edited it. Two copies of a sentence
    is how the vocabularies drifted apart in the first place, so if they must be
    written twice — once in Python, once in TypeScript — they at least have to
    stay identical, and this is what notices when they do not."""
    library = _SKILL_LIBRARY.read_text(encoding="utf-8")
    for role, instruction in DEFAULT_SKILL_INSTRUCTIONS.items():
        assert instruction in library, f"{role}'s default guidance differs from the UI's"


def test_a_fresh_workspace_starts_with_every_role_present():
    profile = default_skill_profile("w1")

    assert [skill.id for skill in profile.skills] == list(CANONICAL_ROLES)
    # One on by default, so the count in Settings matches what is actually used.
    assert profile.enabled_skills_count == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
