import subprocess
from pathlib import Path

import pytest

from app.adapters.system.local_git_history import LocalGitHistory


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _has_git() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def test_non_repo_directory_returns_not_a_repo(tmp_path: Path):
    insights = LocalGitHistory().read_insights(str(tmp_path))
    assert insights.is_repo is False
    assert insights.total_commits == 0
    assert insights.last_commit is None


def test_missing_directory_returns_not_a_repo():
    insights = LocalGitHistory().read_insights("/this/path/does/not/exist")
    assert insights.is_repo is False


@pytest.mark.skipif(not _has_git(), reason="git is not installed")
def test_real_repo_insights(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Dev One")
    (repo / "app.py").write_text("print('hello')\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-q", "-m", "Initial commit")
    (repo / "app.py").write_text("print('hello world')\n")
    _git(repo, "commit", "-qam", "Update greeting")

    insights = LocalGitHistory().read_insights(str(repo))
    assert insights.is_repo is True
    assert insights.total_commits == 2
    assert insights.last_commit is not None
    assert insights.last_commit.subject == "Update greeting"
    assert insights.last_commit.author == "Dev One"
    assert insights.contributors_count == 1
    assert insights.first_commit_at is not None
    # app.py changed in both commits -> it is the top hotspot.
    assert insights.hotspots
    assert insights.hotspots[0].path == "app.py"
