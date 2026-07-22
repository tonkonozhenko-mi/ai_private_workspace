"""The dictionary and the walk are two records of one piece of knowledge.

0.7.3 taught the classifier Bicep and PowerShell and did not tell
``DEFAULT_INCLUDE_PATTERNS``. The walk cut `infra/appservice.bicep` before the
dictionary could name it — and because a rule cut it, it did not appear in the
"files I can't read yet" line either. Invisible in the index and invisible in the
confession. The same files under `src/` worked perfectly, which is the only
reason it survived review.

That is the second time these two drifted. A comment asking the next person to
remember both is not a mechanism; this file is. If the classifier can name an
extension and the index accepts that name, the default rules must be able to
reach a file with it — anywhere in the project, not only in the handful of
folders someone once thought to privilege.
"""

import re
from fnmatch import fnmatch
from pathlib import Path

from app.core.domain.indexing_rules import (
    DEFAULT_INCLUDE_PATTERNS,
    MAX_PATTERNS,
    normalize_patterns,
)
from app.core.domain.source_files import (
    CONFIG_EXTENSIONS,
    SOURCE_CODE_EXTENSIONS,
    XML_CONFIG_EXTENSIONS,
)
from app.core.use_cases.index_workspace import INDEXABLE_FILE_TYPES

# Deliberately not `src/` or `app/`: those are already privileged by a folder
# pattern, and testing there is what let the drift through. Infrastructure lives
# in `infra/`, automation in `scripts/`, and neither is on anyone's whitelist.
_ORDINARY_FOLDERS = ("infra", "scripts", "deploy", "tools")


def _reachable(extension: str) -> bool:
    """Can the default rules reach a file with this extension, anywhere?"""
    return all(
        any(
            fnmatch(f"{folder}/thing{extension}", pattern)
            or (
                pattern.endswith("/**")
                and f"{folder}/thing{extension}".startswith(pattern[:-3].rstrip("/") + "/")
            )
            for pattern in DEFAULT_INCLUDE_PATTERNS
        )
        for folder in _ORDINARY_FOLDERS
    )


def _classifier_suffixes() -> set[str]:
    """Every extension the file-type classifier tests for, read from the file.

    Reading the source rather than importing keeps this honest about additions:
    a new `if suffix == ".foo"` is caught even if nobody exports it in a set.
    """
    source = Path("app/adapters/filesystem/local_file_system.py").read_text()
    body = source[source.index("def _detect_file_type") :]
    return set(re.findall(r'"(\.[a-z0-9]+)"', body))


def test_every_extension_the_dictionary_names_can_be_reached():
    named = SOURCE_CODE_EXTENSIONS | CONFIG_EXTENSIONS | XML_CONFIG_EXTENSIONS

    unreachable = sorted(extension for extension in named if not _reachable(extension))

    assert unreachable == [], (
        f"{len(unreachable)} extensions are in the dictionary but the default rules "
        f"cut them outside src/: {' '.join(unreachable)}"
    )


def test_every_extension_the_classifier_knows_can_be_reached():
    """Wider than the three sets: JSON, .pptx, .drawio and .hcl are none of them,
    and all four were unreachable outside src/ when this test was written."""
    unreachable = sorted(
        extension
        for extension in _classifier_suffixes()
        # Images are classified so they are *known*, never indexed — being
        # unreachable is correct for them, and whitelisting them would put
        # every screenshot in the walk for nothing.
        if extension not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
        and not _reachable(extension)
    )

    assert unreachable == [], f"classifier knows these, the walk cannot see them: {unreachable}"


def test_the_defaults_survive_being_saved():
    """The pattern ceiling exists so a pasted wall of text cannot become the
    rules. At 80 it also truncated our own 100 defaults, so opening the rules
    editor and pressing Save — changing nothing — silently dropped the last
    twenty and re-broke exactly this."""
    assert len(DEFAULT_INCLUDE_PATTERNS) <= MAX_PATTERNS
    assert normalize_patterns(DEFAULT_INCLUDE_PATTERNS) == DEFAULT_INCLUDE_PATTERNS


def test_the_indexable_types_are_what_this_parity_is_about():
    """If a type stops being indexable, reaching it stops mattering — and this
    test should be revisited rather than silently kept passing."""
    assert "source_code" in INDEXABLE_FILE_TYPES
    assert "config" in INDEXABLE_FILE_TYPES
    assert "xml_config" in INDEXABLE_FILE_TYPES
    assert "image" not in INDEXABLE_FILE_TYPES
