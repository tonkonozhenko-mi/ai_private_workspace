"""The scan that writes the baseline and the check that reads it back must agree
about which files this project is made of.

Live finding (Fable, 16.07): a group card was stuck on "1 file changed
(1 removed)" for wiki-export. Nothing was removed — `find` said so — and no
rescan could clear it.

The mechanism, and it is a good one to remember: the watcher's rebuild wrote the
stored scan with `ScanWorkspaceProjectInput(workspace_id=workspace_id)` and
nothing else, so it scanned with NO patterns and took everything the walk allows.
The change check scanned the same folder through the workspace's own rules, which
are a whitelist ("src/**", "app/**", "docs/**", "README*", …). Every file the
walk takes and the whitelist does not was therefore in the baseline and not in
the live set: "removed", on every check, for ever. Rescan could not help — it was
the very thing writing the mismatch back.

Two questions written in the same words, answered from different books. So the
question is asked in one place now, and "I did not mention rules" no longer means
"this project has no rules".
"""

from app.core.domain.indexing_rules import IndexingRulesProfile
from app.core.domain.project_scan import ProjectFile
from app.core.use_cases.get_workspace_scan_changes import (
    GetWorkspaceScanChangesInput,
    GetWorkspaceScanChangesUseCase,
)
from app.core.use_cases.scan_workspace_project import (
    ScanWorkspaceProjectInput,
    ScanWorkspaceProjectUseCase,
    resolve_scan_rules,
)

WS = "ws-wiki"

# What the walk finds on disk. The diagram sits beside its page, in a folder no
# whitelist has ever heard of — exactly the shape of the file that got stuck.
ON_DISK = [
    ("docs/index.md", 100),
    ("Design_files/billing flow.drawio", 50),
]


class _Workspace:
    id = WS
    name = "Wiki"
    project_path = "/tmp/wiki"


class _WorkspaceRepo:
    def get(self, workspace_id):
        return _Workspace() if workspace_id == WS else None


class _RulesRepo:
    """The workspace's saved rules: a whitelist that does not name Design_files."""

    def __init__(self, profile=None):
        self.profile = profile

    def get(self, workspace_id):
        return self.profile


class _FileSystem:
    """A disk. It lists what is on it; deciding which of those files count is the
    scan's job, and that decision is exactly what is under test."""

    def path_exists(self, path):
        return True

    def is_directory(self, path):
        return True

    def list_files(self, root_path, respect_gitignore=True, progress=None):
        return [
            ProjectFile(
                path=path,
                extension="." + path.rsplit(".", 1)[-1],
                size_bytes=size,
                detected_type="document",
                modified_at=1.0,
            )
            for path, size in ON_DISK
        ]


class _ScanRepo:
    def __init__(self):
        self.latest = None

    def save_latest_scan(self, workspace_id, scan_result):
        self.latest = scan_result

    def get_latest_scan(self, workspace_id):
        return self.latest


WHITELIST = IndexingRulesProfile(
    workspace_id=WS,
    include_patterns=("docs/**",),
    exclude_patterns=(),
)


def _rescan(rules_repo, file_system, scan_repo):
    """What the watcher's rebuild does: scan and persist, naming no rules."""
    ScanWorkspaceProjectUseCase(
        _WorkspaceRepo(),
        file_system,
        scan_repo,
        indexing_rules_repository=rules_repo,
    ).execute(ScanWorkspaceProjectInput(workspace_id=WS))


def _changes(rules_repo, file_system, scan_repo):
    return GetWorkspaceScanChangesUseCase(
        workspace_repository=_WorkspaceRepo(),
        project_scan_repository=scan_repo,
        file_system=file_system,
        indexing_rules_repository=rules_repo,
    ).execute(GetWorkspaceScanChangesInput(workspace_id=WS))


# --- the phantom ---------------------------------------------------------------


def test_a_rescan_then_a_check_reports_nothing_changed():
    """The bug, in one sentence: rescan, change nothing, and be told a file left."""
    rules, fs, scans = _RulesRepo(WHITELIST), _FileSystem(), _ScanRepo()

    _rescan(rules, fs, scans)
    changes = _changes(rules, fs, scans)

    assert changes.removed_count == 0
    assert changes.added_count == 0
    assert changes.changed is False


def test_the_baseline_holds_only_what_the_rules_take():
    """The phantom's source: the diagram is on disk and outside the whitelist, so
    it must be in neither set — not in the baseline and not in the live scan."""
    rules, fs, scans = _RulesRepo(WHITELIST), _FileSystem(), _ScanRepo()

    _rescan(rules, fs, scans)

    stored = {f.path for f in scans.latest.files}
    assert stored == {"docs/index.md"}
    assert "Design_files/billing flow.drawio" not in stored


def test_a_real_change_is_still_reported():
    """The fix must not buy silence by looking at nothing."""
    rules, fs, scans = _RulesRepo(WHITELIST), _FileSystem(), _ScanRepo()
    _rescan(rules, fs, scans)

    ON_DISK.append(("docs/new-page.md", 10))
    try:
        changes = _changes(rules, fs, scans)
    finally:
        ON_DISK.pop()

    assert changes.added_count == 1
    assert changes.changed is True


# --- the rule that makes it so -------------------------------------------------


def test_naming_no_rules_means_the_workspace_rules():
    assert resolve_scan_rules(_RulesRepo(WHITELIST), WS, None, None) == (("docs/**",), ())


def test_naming_rules_overrides_them():
    """The scan screen previews a different selection; that must still win."""
    assert resolve_scan_rules(_RulesRepo(WHITELIST), WS, ("src/**",), ()) == (("src/**",), ())


def test_a_workspace_with_no_saved_rules_gets_the_defaults_not_nothing():
    from app.core.domain.indexing_rules import DEFAULT_INCLUDE_PATTERNS

    include, _exclude = resolve_scan_rules(_RulesRepo(None), WS, None, None)

    assert include == DEFAULT_INCLUDE_PATTERNS
    assert include != ()  # the old answer, and the reason the counts disagreed
