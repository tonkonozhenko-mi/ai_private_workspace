"""Deterministic branch-strategy inference from branch names."""

from app.core.domain.git_insights import infer_branch_strategy


def test_gitflow_from_develop_and_release():
    s = infer_branch_strategy(
        ["main", "develop", "release/1.2", "hotfix/urgent", "feature/login"], "main"
    )
    assert s.inferred_strategy == "GitFlow"
    assert "develop" in s.long_lived_branches
    assert "release" in s.prefixes and "hotfix" in s.prefixes
    assert s.total_branches == 5


def test_github_flow_from_feature_branches_no_develop():
    s = infer_branch_strategy(["main", "feature/a", "feature/b"], "main")
    assert s.inferred_strategy == "GitHub Flow"
    assert s.default_branch == "main"


def test_trunk_based_single_branch():
    s = infer_branch_strategy(["main"], "main")
    assert s.inferred_strategy == "Trunk-based"


def test_unknown_when_no_pattern():
    s = infer_branch_strategy(["foo", "bar", "baz"], None)
    assert s.inferred_strategy == "Unknown"
    assert s.rationale


def test_dedup_and_empty_names_ignored():
    s = infer_branch_strategy(["main", "main", "", "  "], "main")
    assert s.total_branches == 1
