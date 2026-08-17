"""The one workflow that runs with a write token must stay narrow.

Every dependency bump used to be a manual chore, because Dependabot raises a
floor in requirements.txt and knows nothing about requirements.lock — which is
the file CI and the release build actually install. Three bumps in a row were
fixed by hand, and the first attempt at doing it by hand produced a lock that
dropped uvloop's Windows marker and pulled in 22 packages nobody declared. So a
workflow does it now.

Doing it needs ``pull_request_target``: Dependabot's own runs get a read-only
token and cannot push anything back. That event is the one people get badly
wrong, because it hands a write token to a workflow whose checkout can be the
pull request's own code. What keeps it safe here is a short list of properties,
and a short list is exactly the kind of thing that erodes quietly — someone adds
a build step "just to check", and a dependency PR gains the ability to run
arbitrary code with a token that can push to this repository.

These tests read the workflow as YAML and assert the properties, not the
wording. They will not notice a clever attack; they will notice the ordinary way
this goes wrong, which is a well-meaning edit.
"""

from pathlib import Path

import pytest
import yaml

_WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "dependabot-lock-sync.yml"
)


@pytest.fixture(scope="module")
def workflow() -> dict:
    # PyYAML parses the bare `on:` key as the boolean True (YAML 1.1), which is
    # a footgun worth naming rather than working around silently.
    loaded = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    loaded["on"] = loaded.pop(True, loaded.get("on"))
    return loaded


@pytest.fixture(scope="module")
def job(workflow: dict) -> dict:
    assert list(workflow["jobs"]) == ["sync"], "one job; a second one would need its own review"
    return workflow["jobs"]["sync"]


def test_it_runs_only_for_dependabot_and_only_on_this_repository(job: dict) -> None:
    """The actor check keeps it off human pull requests. The repository check
    keeps it off forks, where the head branch is a stranger's and checking it out
    with a write token is the whole vulnerability."""
    condition = " ".join(job["if"].split())

    assert "github.actor == 'dependabot[bot]'" in condition
    assert (
        "github.event.pull_request.head.repo.full_name == github.repository" in condition
    ), "without this it would run on forks"


def test_it_wakes_only_for_dependency_manifests(workflow: dict) -> None:
    paths = workflow["on"]["pull_request_target"]["paths"]

    assert set(paths) == {"backend/requirements.txt", "backend/requirements-qdrant.txt"}


def test_write_permission_is_narrow(workflow: dict, job: dict) -> None:
    """Read by default, write on the one job, and nothing beyond contents."""
    assert workflow["permissions"] == {"contents": "read"}
    assert job["permissions"] == {"contents": "write"}


def test_the_script_it_runs_comes_from_the_base_commit(job: dict) -> None:
    """The checkout is the pull request's branch, so the script sitting in it is
    the pull request's script. Restoring it from the base commit is what stops a
    dependency PR from choosing what runs against a write token."""
    steps = " ".join(step.get("run", "") for step in job["steps"])

    assert "git checkout ${{ github.event.pull_request.base.sha }} -- " in steps
    assert "scripts/sync_requirements_lock.py" in steps


def test_nothing_from_the_pull_request_is_installed_or_executed(job: dict) -> None:
    """No dependency install, no build, no test run. The script is standard
    library and reads two text files; anything that resolves or executes package
    content would undo every other guarantee here."""
    commands = " ".join(step.get("run", "") for step in job["steps"])

    for forbidden in ("pip install", "npm ", "yarn ", "pnpm ", "cargo ", "make ", "pytest"):
        assert forbidden not in commands, f"{forbidden!r} would run code from the pull request"

    for step in job["steps"]:
        uses = step.get("uses", "")
        if uses:
            assert uses.startswith(("actions/checkout@", "actions/setup-python@")), uses


def test_every_action_is_pinned_to_a_commit(job: dict) -> None:
    """A tag can be moved; a commit cannot. The rest of this repository pins by
    SHA and this workflow has more to lose than the rest."""
    for step in job["steps"]:
        uses = step.get("uses")
        if not uses:
            continue
        _, _, ref = uses.partition("@")
        assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), uses


def test_it_only_ever_commits_the_lock(job: dict) -> None:
    commands = " ".join(step.get("run", "") for step in job["steps"])

    assert "git add backend/requirements.lock" in commands
    assert "git add ." not in commands
    assert "git commit -a" not in commands


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
