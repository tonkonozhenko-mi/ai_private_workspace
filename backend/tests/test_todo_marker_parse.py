"""TODO marker parsing: trailing comment-close tokens are stripped without a
regex that static analysers mistake for an HTML tag filter (CodeQL bad-tag-filter).
"""

from app.core.use_cases.get_workspace_todos import _parse_marker


def test_strips_trailing_comment_close_tokens():
    assert _parse_marker("// TODO: refactor this -->") == ("TODO", "refactor this")
    assert _parse_marker("// TODO: refactor this --!>") == ("TODO", "refactor this")
    assert _parse_marker("// TODO: refactor this */") == ("TODO", "refactor this")
    assert _parse_marker("# TODO: clean up #}") == ("TODO", "clean up")


def test_only_trailing_token_is_removed():
    # A token in the middle of the note is kept.
    assert _parse_marker("// TODO: keep --> arrow mid") == ("TODO", "keep --> arrow mid")


def test_plain_marker_unchanged():
    assert _parse_marker("// FIXME: plain note") == ("FIXME", "plain note")


def test_non_marker_line_is_ignored():
    assert _parse_marker("just some prose without a marker") is None
