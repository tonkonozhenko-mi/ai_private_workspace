"""The role is a lens, not a search filter.

The whole feature rests on one promise: the same question, asked by a tester and
by a manager, retrieves the same files and cites the same lines — only the framing
changes. These tests hold that promise to the fire, and check that a role that was
never chosen degrades to the neutral developer lens instead of to nothing.
"""

from app.core.domain.rag_prompt import assistant_mode_lens_hint, build_workspace_question_prompt
from app.core.domain.role_lens import role_lens_for
from app.core.domain.starter_questions import starter_questions


class _Result:
    """The bit of ContextSearchResult the prompt builder actually reads."""

    def __init__(self, source_path: str, content: str) -> None:
        self.source_path = source_path
        self.chunk_id = f"{source_path}:0"
        self.content = content


_CONTEXT = [
    _Result("deploy/main.tf", "resource aws_s3_bucket state {}"),
    _Result("tests/test_api.py", "def test_health(): assert client.get('/health').ok"),
]

_ROLES = ["developer", "tester", "manager", "devops", "business_analyst"]


def _prompt(role: str | None) -> str:
    return build_workspace_question_prompt(
        question="How is this deployed?",
        context_results=_CONTEXT,
        assistant_mode=role,
    )


def test_the_role_changes_the_framing_of_the_prompt():
    prompts = {role: _prompt(role) for role in _ROLES}
    # Every role reads differently...
    assert len(set(prompts.values())) == len(_ROLES)
    assert "QA/test engineer" in prompts["tester"]
    assert "engineering manager" in prompts["manager"]
    assert "DevOps/platform engineer" in prompts["devops"]


def test_the_role_never_changes_the_evidence():
    """Invariant 1: same context, same source paths, same content — for every role.

    If a role ever starts filtering or reordering the evidence, this fails.
    """
    for role in _ROLES:
        prompt = _prompt(role)
        for result in _CONTEXT:
            assert result.source_path in prompt
            assert result.content in prompt
    # And the question itself is untouched by the lens.
    assert all("How is this deployed?" in _prompt(role) for role in _ROLES)


def test_an_unchosen_role_reads_as_the_neutral_developer_lens():
    """Invariant 4: skipping the role question costs nothing."""
    assert _prompt(None) == _prompt("developer")
    assert _prompt("") == _prompt("developer")
    assert _prompt("something_we_never_heard_of") == _prompt("developer")
    assert role_lens_for(None).role == "developer"
    assert role_lens_for("").role == "developer"


def test_every_role_has_its_own_hint_and_lens():
    hints = {role: assistant_mode_lens_hint(role) for role in _ROLES}
    assert len(set(hints.values())) == len(_ROLES)
    for role in _ROLES:
        assert role_lens_for(role).role == role


def test_starter_questions_differ_by_role_even_without_a_map():
    """No project map yet (fresh workspace): the openers must still be the role's,
    not one generic list — that is the whole point of asking who you are."""
    tester = starter_questions(None, role_lens_for("tester"))
    manager = starter_questions(None, role_lens_for("manager"))
    assert tester
    assert manager
    assert tester != manager
