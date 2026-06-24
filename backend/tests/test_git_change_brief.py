from app.core.domain.git_change_brief import (
    GitChangeBrief,
    build_change_summary_prompt,
    format_git_brief,
    top_changed_areas,
)


def test_top_areas_grouped_and_ranked():
    paths = [
        "auth/login.py",
        "auth/session.py",
        "terraform/staging/main.tf",
        "README.md",
    ]
    assert top_changed_areas(paths) == [
        ("auth", 2),
        ("(root)", 1),
        ("terraform", 1),
    ]


def test_format_no_baseline_is_empty():
    brief = GitChangeBrief(comparable=False, head="abc", commit_count=0)
    assert format_git_brief(brief) == []


def test_format_no_new_commits():
    brief = GitChangeBrief(comparable=True, head="abc", commit_count=0)
    assert format_git_brief(brief) == ["No new commits since your last check."]


def test_format_headline_and_areas():
    brief = GitChangeBrief(
        comparable=True,
        head="abc",
        commit_count=12,
        authors=["Anya", "Oleg", "You"],
        changed_paths=["auth/a.py", "auth/b.py", "terraform/staging/main.tf"],
    )
    lines = format_git_brief(brief)
    assert lines[0] == "12 commits by Anya, Oleg and You since your last check."
    assert lines[1].startswith("Most changes in auth (2 files)")


def test_format_many_authors_summarised():
    brief = GitChangeBrief(
        comparable=True,
        head="abc",
        commit_count=5,
        authors=["A", "B", "C", "D", "E"],
        changed_paths=[],
    )
    assert "and 2 others" in format_git_brief(brief)[0]


def test_singular_commit():
    brief = GitChangeBrief(comparable=True, head="abc", commit_count=1, authors=["A"])
    assert format_git_brief(brief)[0] == "1 commit by A since your last check."


def test_summary_prompt_none_without_baseline_or_commits():
    assert build_change_summary_prompt(GitChangeBrief(False, "abc", 0)) is None
    # Comparable but no subjects → nothing to summarise.
    assert (
        build_change_summary_prompt(
            GitChangeBrief(True, "abc", 3, authors=["A"], commit_subjects=[])
        )
        is None
    )


def test_summary_prompt_includes_subjects_and_authors():
    brief = GitChangeBrief(
        comparable=True,
        head="abc",
        commit_count=2,
        authors=["Anya", "Oleg"],
        changed_paths=["auth/a.py"],
        commit_subjects=["feat: add login", "fix: token refresh"],
    )
    prompt = build_change_summary_prompt(brief)
    assert prompt is not None
    assert "2 commits by Anya and Oleg" in prompt
    assert "feat: add login" in prompt
    assert "fix: token refresh" in prompt
    assert prompt.rstrip().endswith("Summary:")


def test_summary_prompt_trims_to_window():
    subjects = [f"commit number {i} doing a fair amount of work" for i in range(5000)]
    brief = GitChangeBrief(
        comparable=True,
        head="abc",
        commit_count=len(subjects),
        authors=["A"],
        commit_subjects=subjects,
    )
    # Tiny window forces aggressive trimming but still yields a usable prompt.
    prompt = build_change_summary_prompt(brief, max_context_tokens=1024)
    assert prompt is not None
    assert "more commits not shown" in prompt
    # The prompt must stay far below the raw material it was built from.
    assert len(prompt) < sum(len(s) for s in subjects)
