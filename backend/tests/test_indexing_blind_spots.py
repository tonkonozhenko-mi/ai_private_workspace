"""Files the scan walked past, counted honestly.

The live case: an Azure repository whose .bicep and .ps1 files were found,
counted in the totals, classified "unknown", and dropped at the index step
without a word anywhere. These tests hold the two halves of the fix — the
extensions are now read, and whatever is still unread says so.
"""

from app.core.domain.indexing_blind_spots import (
    unread_files,
    unread_files_note,
    unread_files_prompt_note,
)
from app.core.domain.project_scan import ProjectFile


def _file(path: str, detected_type: str) -> ProjectFile:
    extension = ("." + path.rsplit(".", 1)[1]) if "." in path.rsplit("/", 1)[-1] else None
    return ProjectFile(path=path, extension=extension, size_bytes=10, detected_type=detected_type)


# --- the summary ---------------------------------------------------------------


def test_the_summary_counts_what_was_not_recognised():
    scanned = [
        *[_file(f"infra/main{i}.bicep", "unknown") for i in range(12)],
        _file("scripts/deploy.ps1", "unknown"),
        _file("scripts/rollback.ps1", "unknown"),
        _file("notes/thing.xyz", "unknown"),
        _file("app/main.py", "python"),
    ]

    unread = unread_files(scanned)

    assert unread.summary() == {".bicep": 12, ".ps1": 2, ".xyz": 1}
    assert unread.total == 15


def test_bicep_and_powershell_are_no_longer_skipped():
    """The other half of the fix: with the dictionary extended, these arrive as
    source_code, so they never reach this count at all."""
    scanned = [
        _file("infra/main.bicep", "source_code"),
        _file("scripts/deploy.ps1", "source_code"),
        _file("notes/thing.xyz", "unknown"),
    ]

    assert unread_files(scanned).summary() == {".xyz": 1}


def test_what_the_person_excluded_is_not_something_we_could_not_read():
    """Their own exclude rules are applied before the scan result exists, so an
    excluded file is simply absent here. "I didn't ask for it" is not "I can't
    read it", and printing someone's own decision back as a limitation is noise."""
    # What the scan hands us after `*.ps1` was excluded: the .ps1 files are gone.
    after_exclusion = [_file("app/main.py", "python"), _file("README.md", "markdown")]

    assert unread_files(after_exclusion).is_empty


def test_deliberate_refusals_are_not_confessions():
    """A lockfile, a bundle and a real .env are "unknown" *on purpose*. Counting
    our own judgement as a failure would teach the person to distrust the line."""
    scanned = [
        _file("package-lock.json", "unknown"),
        _file("dist/app.min.js", "unknown"),
        _file(".env", "unknown"),
        _file(".DS_Store", "unknown"),
    ]

    assert unread_files(scanned).is_empty


def test_a_file_with_no_extension_is_not_counted_in_a_total_it_cannot_itemise():
    scanned = [_file("LICENSE", "unknown"), _file("infra/main.bicep", "unknown")]

    unread = unread_files(scanned)

    # 1, not 2: the line names extensions, and a total that includes what it
    # cannot name adds up to less than it claims.
    assert unread.total == 1
    assert unread.summary() == {".bicep": 1}


def test_nothing_in_nothing_out():
    assert unread_files([]).is_empty
    assert unread_files(None).is_empty


# --- the two sentences ---------------------------------------------------------


def test_the_prompt_line_names_the_extensions_and_says_what_to_do():
    note = unread_files_prompt_note(
        unread_files([*[_file(f"a{i}.bicep", "unknown") for i in range(3)]])
    )

    assert note == (
        "Note: 3 files with extensions .bicep were not indexed and are invisible "
        "to you; say so if the question may depend on them."
    )


def test_no_skips_means_no_sentence_anywhere():
    """Empty state is silence. Not "0 files skipped", not a reassurance — the
    line's absence is the good news, and a line on every project is unread."""
    assert unread_files_prompt_note(unread_files([_file("a.py", "python")])) == ""
    assert unread_files_note(unread_files([_file("a.py", "python")])) == ""


def test_the_home_line_reads_as_a_fact():
    scanned = [
        *[_file(f"i{i}.bicep", "unknown") for i in range(12)],
        *[_file(f"s{i}.ps1", "unknown") for i in range(2)],
    ]

    assert unread_files_note(unread_files(scanned)) == (
        "14 files I can't read yet: .bicep ×12, .ps1 ×2"
    )
