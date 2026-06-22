"""Merge & PR activity inference from commit subjects."""
from app.core.domain.git_insights import summarize_merges


def test_github_merge_pr_and_squash():
    merges = [
        "Merge pull request #12 from acme/feature/login",
        "Merge pull request #15 from acme/hotfix/crash",
    ]
    allsub = merges + ["Add tests (#20)", "Refactor (#12)", "chore: bump"]
    m = summarize_merges(merges, allsub)
    assert m.merge_commits == 2
    # #12, #15, #20 distinct
    assert m.pull_requests_detected == 3
    assert m.source_branch_types.get("feature") == 1
    assert m.source_branch_types.get("hotfix") == 1


def test_merge_branch_into_target():
    merges = ["Merge branch 'feature/x' into 'main'", "Merge branch 'develop' into 'main'"]
    m = summarize_merges(merges, merges + ["See merge request !45"])
    assert m.target_branches.get("main") == 2
    assert m.merge_requests_detected == 1
    assert m.source_branch_types.get("feature") == 1


def test_empty():
    m = summarize_merges([], [])
    assert m.merge_commits == 0 and m.pull_requests_detected == 0
