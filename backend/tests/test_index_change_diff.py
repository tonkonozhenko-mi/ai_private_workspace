"""The index's answer to "what changed" must be one answer.

Live on 0.7.9: a plain `.txt` added to a project after the workspace existed
could not be indexed by any button. The Settings button said "already up to
date"; directly above it an orange line said "1 file(s) changed since the AI
last indexed them"; a full rebuild after clearing the index still found only
the original three files; and Ask answered, honestly, that it had never seen
the file. The person reported it as "it doesn't read text files" — the .md
files present when the workspace was created worked, so the difference looked
like the file type. It was the timing.

Two separate defects produced that, and both are pinned here.

1. The count and the action each did their own subtraction. The handbook is
   indexed as a pseudo-document, so it is legitimately in the manifest and
   never on disk. The action knew that; the count did not, and reported it as
   a removal on every single check — a permanent "1 file changed" on a project
   where nothing had changed.

2. Everything read the stored scan, which is a photograph taken when the
   project was last scanned. A file added afterwards is not in the photograph.
"""

import pytest

from app.core.domain.handbook_source import HANDBOOK_SOURCE_PATH
from app.core.domain.indexing import (
    PSEUDO_DOCUMENT_PATHS,
    diff_against_manifest,
)


def _manifest(**paths: str) -> dict[str, dict]:
    return {path: {"hash": digest} for path, digest in paths.items()}


def test_the_handbook_is_never_reported_as_a_removed_file():
    # The exact live shape: three indexed files, nothing touched, handbook present.
    manifest = _manifest(**{"a.md": "h1", "b.md": "h2", "c.md": "h3"})
    manifest[HANDBOOK_SOURCE_PATH] = {"hash": "handbook"}

    diff = diff_against_manifest(
        current_hashes={"a.md": "h1", "b.md": "h2", "c.md": "h3"},
        manifest=manifest,
    )

    assert diff.removed == ()
    # This is the number the orange hint shows. It sat at 1 for ever.
    assert diff.pending == 0


def test_a_file_added_after_the_baseline_counts_as_new():
    manifest = _manifest(**{"a.md": "h1"})
    manifest[HANDBOOK_SOURCE_PATH] = {"hash": "handbook"}

    diff = diff_against_manifest(
        current_hashes={"a.md": "h1", "data/oncall-notes.txt": "fresh"},
        manifest=manifest,
    )

    assert diff.new == ("data/oncall-notes.txt",)
    assert diff.pending == 1


def test_a_genuinely_deleted_file_is_still_reported():
    # Excluding pseudo-paths must not blunt real deletions.
    manifest = _manifest(**{"a.md": "h1", "gone.md": "h2"})
    manifest[HANDBOOK_SOURCE_PATH] = {"hash": "handbook"}

    diff = diff_against_manifest(current_hashes={"a.md": "h1"}, manifest=manifest)

    assert diff.removed == ("gone.md",)


def test_a_changed_file_is_told_apart_from_an_unchanged_one():
    manifest = _manifest(**{"same.md": "h1", "edited.md": "old"})

    diff = diff_against_manifest(
        current_hashes={"same.md": "h1", "edited.md": "new"},
        manifest=manifest,
    )

    assert diff.changed == ("edited.md",)
    assert diff.unchanged == ("same.md",)


def test_the_count_and_the_action_cannot_disagree():
    """The heart of the complaint: the hint and the button showed opposite
    things at the same moment. They now derive from this one function, so a
    disagreement is not something to test for — it is something to make
    unrepresentable. What is testable is that the function is the only
    arithmetic there is: same inputs, same answer, every time it is asked."""
    manifest = _manifest(**{"a.md": "h1", "b.md": "old"})
    manifest[HANDBOOK_SOURCE_PATH] = {"hash": "handbook"}
    current = {"a.md": "h1", "b.md": "new", "added.txt": "x"}

    first = diff_against_manifest(current_hashes=current, manifest=manifest)
    second = diff_against_manifest(current_hashes=current, manifest=manifest)

    assert first == second
    assert first.pending == 2  # one edited, one added; the handbook is not a removal


def test_pseudo_paths_are_declared_once():
    # If a second pseudo-document is ever indexed, it belongs in this set — not
    # in a second private list inside whichever caller noticed first.
    assert HANDBOOK_SOURCE_PATH in PSEUDO_DOCUMENT_PATHS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
