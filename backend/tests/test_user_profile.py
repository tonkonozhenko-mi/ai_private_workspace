"""Pure tests for the user profile (cross-project memory about the person)."""

from app.adapters.memory.in_memory_user_profile_repository import (
    InMemoryUserProfileRepository,
)
from app.core.domain.user_profile import (
    UserProfileCategory,
    UserProfileItem,
    format_user_profile_context,
    is_duplicate,
    select_for_prompt,
)
from app.core.use_cases.manage_user_profile import (
    AddUserProfileFactInput,
    ManageUserProfileUseCase,
    UserProfileValidationError,
)


def _item(text: str, *, pinned: bool = False, created_at: str = "2026-01-01", cat: str = "fact") -> UserProfileItem:
    return UserProfileItem(id=text, category=cat, text=text, created_at=created_at, pinned=pinned)


def test_format_context_is_framed_about_the_person():
    block = format_user_profile_context([_item("Answer in Russian", cat="style")])
    assert "person" in block.lower()
    assert "Answer in Russian" in block
    assert "not a fact about the project" in block.lower()


def test_empty_profile_yields_no_block():
    assert format_user_profile_context([]) == ""


def test_select_puts_pinned_first_then_query_overlap():
    items = [
        _item("likes concise answers", created_at="2026-01-01"),
        _item("works with terragrunt infra", created_at="2026-01-02"),
        _item("prefers russian", pinned=True, created_at="2025-01-01"),
    ]
    out = select_for_prompt(items, query="how is terragrunt configured?")
    assert out[0].text == "prefers russian"  # pinned wins
    assert any("terragrunt" in i.text for i in out[:2])  # query overlap ranks up


def test_is_duplicate_ignores_case_and_whitespace():
    items = [_item("I am a DevOps engineer")]
    assert is_duplicate(items, "i am a   devops ENGINEER")
    assert not is_duplicate(items, "I am a backend developer")


def test_use_case_add_list_delete_pin():
    uc = ManageUserProfileUseCase(InMemoryUserProfileRepository())
    a = uc.add(AddUserProfileFactInput(text="DevOps engineer", category=UserProfileCategory.ROLE))
    uc.add(AddUserProfileFactInput(text="Answer concisely", category=UserProfileCategory.PREFERENCE))
    assert len(uc.list()) == 2

    uc.set_pinned(a.id, True)
    assert next(i for i in uc.list() if i.id == a.id).pinned is True

    uc.delete(a.id)
    assert len(uc.list()) == 1


def test_use_case_dedups_and_validates():
    uc = ManageUserProfileUseCase(InMemoryUserProfileRepository())
    first = uc.add(AddUserProfileFactInput(text="Prefers Russian"))
    again = uc.add(AddUserProfileFactInput(text="  prefers russian  "))
    assert first.id == again.id  # de-duplicated, not a second entry
    assert len(uc.list()) == 1

    try:
        uc.add(AddUserProfileFactInput(text="   "))
        raise AssertionError("expected validation error")
    except UserProfileValidationError:
        pass
