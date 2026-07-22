"""A real scan of a project shaped like a real project.

The parity test proves the two lists agree. This one proves the scan actually
behaves — on a folder laid out the way repositories are laid out, with
infrastructure in `infra/` and automation in `scripts/` and nothing at all in
`src/`. That layout is the entire bug: the same files under `src/` worked
perfectly in 0.7.3, which is why the gap survived review.

Fable's live acceptance run, made into something that runs every time.
"""

from pathlib import Path

from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.core.domain.indexing_blind_spots import unread_files_in_scan, unread_files_note
from app.core.domain.indexing_rules import DEFAULT_EXCLUDE_PATTERNS, DEFAULT_INCLUDE_PATTERNS
from app.core.use_cases.scan_project import ScanProjectInput, ScanProjectUseCase

FIXTURE = Path(__file__).parent / "fixtures" / "blindspot_project"


def _scan(include=DEFAULT_INCLUDE_PATTERNS, exclude=DEFAULT_EXCLUDE_PATTERNS, default=True):
    return ScanProjectUseCase(file_system=LocalFileSystem()).execute(
        ScanProjectInput(
            project_path=str(FIXTURE),
            include_patterns=include,
            exclude_patterns=exclude,
            respect_gitignore=False,
            include_patterns_are_default=default,
        )
    )


def test_infrastructure_outside_src_is_scanned():
    scan = _scan()

    kept = {f.path: f.detected_type for f in scan.files}

    assert kept.get("infra/appservice.bicep") == "source_code", kept
    assert kept.get("scripts/deploy.ps1") == "source_code", kept
    assert kept.get("README.md") == "markdown", kept


def test_the_unreadable_note_names_the_xyz_and_nothing_else():
    """Fable's acceptance line, exactly. `.bicep` and `.ps1` are read now, so the
    only thing left to admit is the format nobody has heard of."""
    scan = _scan()

    assert unread_files_note(unread_files_in_scan(scan)) == "1 file I can't read yet: .xyz ×1"


def test_a_file_the_default_rules_cut_is_still_admitted():
    """`data/notes.xyz` matches no include pattern, so it is not in `files` at
    all. Before this change that made it doubly invisible: not indexed, and not
    counted as unreadable either, because a rule had cut it. A rule the person
    never wrote is not their decision."""
    scan = _scan()

    assert "data/notes.xyz" not in {f.path for f in scan.files}
    assert "data/notes.xyz" in {f.path for f in scan.unseen_files}


def test_rules_the_person_wrote_themselves_stay_silent():
    """The other half of the semantics. Their own narrow rules are a decision,
    and printing someone's decision back to them as a limitation is nonsense."""
    scan = _scan(include=("README*",), default=False)

    assert scan.unseen_files == []
    assert unread_files_note(unread_files_in_scan(scan)) == ""


def test_an_excluded_file_is_not_a_blind_spot_either():
    """Excludes carry a reason — junk, secrets, machine output. A refusal with a
    reason is not something we failed to see."""
    scan = _scan(exclude=(*DEFAULT_EXCLUDE_PATTERNS, "data/**"))

    assert "data/notes.xyz" not in {f.path for f in scan.unseen_files}
    assert unread_files_note(unread_files_in_scan(scan)) == ""


def test_nothing_unreadable_means_no_line_at_all():
    scan = _scan(exclude=(*DEFAULT_EXCLUDE_PATTERNS, "*.xyz"))

    assert unread_files_note(unread_files_in_scan(scan)) == ""
