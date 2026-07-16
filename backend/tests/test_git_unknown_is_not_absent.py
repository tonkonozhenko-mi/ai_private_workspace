"""A git call that could not be made is not a project without git.

Live finding (Fable, 16.07): while macOS held a folder-access dialog open, the
group's git call timed out and the card announced "Not a git repository" about a
repository with 1,390 commits. The moment the dialog was dismissed it was a
repository again.

It was one boolean doing two jobs, and the docstring said so out loud: "not a git
repository (or git is unavailable)". Those are different facts. The same rule we
fixed in answers — not knowing is not the same as knowing there is nothing —
applies to a card reading a number off a subprocess.
"""

from app.core.domain.git_insights import GitInsights


class _FakeGit:
    """Stands in for `git`, which is the only part that can fail here."""

    def __init__(self, answers):
        self.answers = answers

    def __call__(self, root, args):
        return self.answers.get(tuple(args))


def _read_insights(answers, path):
    from app.adapters.system.local_git_history import LocalGitHistory

    history = LocalGitHistory()
    history._run = _FakeGit(answers)  # noqa: SLF001 - git itself is what we fake
    return history.read_insights(path)


INSIDE = ("rev-parse", "--is-inside-work-tree")


def test_a_timed_out_git_says_nothing_rather_than_no(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        # _run returns None for every failure it catches: timeout, no git binary,
        # a folder the OS will not let us read yet.
        insights = _read_insights({INSIDE: None}, folder)

    assert insights.known is False
    assert insights.is_repo is False  # nothing to show, but nothing is claimed


def test_git_answering_no_is_an_answer():
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        insights = _read_insights({INSIDE: "false\n"}, folder)

    assert insights.known is True
    assert insights.is_repo is False


def test_a_folder_that_is_not_there_is_known_not_to_be_a_repository():
    insights = _read_insights({}, "/nowhere/at/all")

    assert insights.known is True
    assert insights.is_repo is False


def test_the_two_factories_say_different_things():
    assert GitInsights.not_a_repo().known is True
    assert GitInsights.unknown().known is False
    assert GitInsights.unknown().is_repo is False


# --- and the group carries the distinction to the card -------------------------


class _Workspace:
    id = "ws-1"
    name = "Backend"
    project_path = "/tmp/backend"


class _WorkspaceRepo:
    def get(self, workspace_id):
        return _Workspace()


class _GroupRepo:
    def get(self, group_id):
        from app.core.domain.project_group import ProjectGroup

        return ProjectGroup(
            id=group_id, name="G", workspace_ids=("ws-1",), created_at="2026-07-16"
        )


class _GraphRepo:
    def get_latest_graph(self, workspace_id):
        return None


class _Git:
    def __init__(self, insights):
        self.insights = insights

    def read_insights(self, project_path):
        if isinstance(self.insights, Exception):
            raise self.insights
        return self.insights


def _member(insights):
    from app.core.use_cases.build_group_overview import BuildGroupOverviewUseCase

    overview = BuildGroupOverviewUseCase(
        group_repository=_GroupRepo(),
        workspace_repository=_WorkspaceRepo(),
        project_graph_repository=_GraphRepo(),
        git_history=_Git(insights),
    ).execute("g1")
    return overview.members[0]


def test_the_card_knows_when_git_could_not_be_asked():
    assert _member(GitInsights.unknown()).git_known is False


def test_the_card_knows_when_git_said_no():
    assert _member(GitInsights.not_a_repo()).git_known is True


def test_a_git_call_that_blows_up_is_also_not_knowing():
    assert _member(RuntimeError("git exploded")).git_known is False


def test_a_real_repository_is_reported_as_one():
    member = _member(GitInsights(is_repo=True, branch="main", total_commits=1390))

    assert member.git_known is True
    assert member.is_repo is True
    assert member.total_commits == 1390
