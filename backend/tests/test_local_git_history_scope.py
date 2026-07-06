"""A workspace that is a subfolder of a bigger git repo must report only its own
history, never the parent repository's (privacy)."""

import subprocess
import tempfile
from pathlib import Path

from app.adapters.system.local_git_history import LocalGitHistory


def _git(root: Path, *args: str) -> None:
    env = {
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@e.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@e.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "PATH": "/usr/bin:/bin:/usr/local/bin",
    }
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


def _commit(root: Path, rel: str, text: str, author: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    _git(root, "add", "-A")
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", f"add {rel}"],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": f"{author}@e.com",
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": f"{author}@e.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


def _make_nested_repo(tmp: Path) -> Path:
    """Repo with 3 parent-only commits and 1 commit inside a `ws/` subfolder."""
    _git(tmp, "init", "-q")
    _git(tmp, "config", "commit.gpgsign", "false")
    _commit(tmp, "parent_a.txt", "a", "Alice")
    _commit(tmp, "parent_b.txt", "b", "Bob")
    _commit(tmp, "docs/parent_c.md", "c", "Carol")
    _commit(tmp, "ws/app.py", "print()\n", "Dana")  # the only commit inside ws/
    return tmp / "ws"


def test_nested_workspace_reports_only_its_own_commits():
    with tempfile.TemporaryDirectory() as d:
        ws = _make_nested_repo(Path(d))
        insights = LocalGitHistory().read_insights(str(ws))
        assert insights.is_repo is True
        # 4 commits in the parent repo, but only 1 touched the workspace.
        assert insights.total_commits == 1
        assert [c.author for c in insights.recent_commits] == ["Dana"]
        assert insights.contributors_count == 1
        # No parent commit subject leaks into the workspace's recent history.
        subjects = " ".join(c.subject for c in insights.recent_commits)
        assert "parent_" not in subjects


def test_repo_root_workspace_still_sees_everything():
    with tempfile.TemporaryDirectory() as d:
        _make_nested_repo(Path(d))
        insights = LocalGitHistory().read_insights(d)  # the repo root itself
        # Not nested → unchanged behaviour → all 4 commits.
        assert insights.total_commits == 4


def test_file_activity_without_path_is_scoped_on_nested_workspace():
    with tempfile.TemporaryDirectory() as d:
        ws = _make_nested_repo(Path(d))
        activity = LocalGitHistory().file_activity(str(ws))  # no relative_path
        assert activity is not None
        assert activity.total_commits == 1
        assert [a.name for a in activity.top_authors] == ["Dana"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
