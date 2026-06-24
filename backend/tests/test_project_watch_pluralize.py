"""Watch-digest counts must read with correct English plurals (no 'dependencys')."""

from app.core.domain.project_watch import _pluralize


def test_y_becomes_ies():
    assert _pluralize("dependency", 2) == "dependencies"


def test_singular_is_unchanged():
    assert _pluralize("dependency", 1) == "dependency"


def test_regular_plurals():
    assert _pluralize("module", 2) == "modules"
    assert _pluralize("external reference", 3) == "external references"
    assert _pluralize("important file", 2) == "important files"
