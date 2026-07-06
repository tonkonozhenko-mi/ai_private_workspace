from app.core.domain.chunking import (
    build_contextual_chunk,
    chunk_section_label,
    config_keys,
    strip_contextual_header,
)


def test_label_from_markdown_heading():
    label = chunk_section_label("## Deployment flow\n\nsome text", file_type="markdown")
    assert label == "Deployment flow"


def test_label_from_python_def():
    content = "@decorator\ndef compose_context(workspace_id):\n    return 1\n"
    assert chunk_section_label(content, file_type="python") == "compose_context"


def test_label_from_brace_definition():
    content = 'resource "aws_s3_bucket" {\n  bucket = "x"\n}\n'
    # Generic definition keyword "resource" → first identifier after it.
    assert chunk_section_label(content, extension=".tf") == "aws_s3_bucket"


def test_label_none_when_no_structure():
    assert chunk_section_label("just some prose with no headings", extension=".txt") is None


def test_header_includes_path_label_and_part():
    out = build_contextual_chunk(
        "def f():\n    pass",
        source_path="app/core/x.py",
        position=2,
        total=5,
        file_type="python",
    )
    first_line = out.split("\n", 1)[0]
    assert first_line == "[source: app/core/x.py › f · part 2/5]"
    assert out.endswith("def f():\n    pass")


def test_header_omits_part_for_single_chunk():
    out = build_contextual_chunk(
        "hello", source_path="README.md", position=1, total=1, file_type="markdown"
    )
    assert out.split("\n", 1)[0] == "[source: README.md]"


def test_markdown_does_not_borrow_code_label():
    # A markdown chunk with no heading must not pick up a code-style definition.
    assert chunk_section_label("def x():\n    pass", file_type="markdown") is None


def test_strip_header_round_trips_to_original_body():
    body = "def f():\n    return 1\n"
    built = build_contextual_chunk(
        body, source_path="x.py", position=1, total=3, file_type="python"
    )
    # Embedding must see exactly the original body, not the provenance header.
    assert strip_contextual_header(built) == body


def test_strip_header_leaves_plain_content_untouched():
    plain = "just a normal chunk\nwith two lines"
    assert strip_contextual_header(plain) == plain


def test_config_keys_finds_nested_json_key():
    # The pp-csp case: asking about the content security policy, but the file only
    # spells it `csp`, nested under `security`. Both keys must surface.
    content = '{\n  "security": {\n    "csp": "default-src \'self\'"\n  }\n}'
    keys = config_keys(content, file_type="json")
    assert "security" in keys and "csp" in keys


def test_config_keys_finds_yaml_keys_at_any_indent():
    content = "server:\n  host: localhost\n  tls:\n    enabled: true\n"
    keys = config_keys(content, file_type="yaml")
    assert keys[:1] == ["server"]
    for expected in ("host", "tls", "enabled"):
        assert expected in keys


def test_config_keys_empty_for_non_config():
    assert config_keys("def f():\n    pass", file_type="python") == []


def test_config_header_lists_keys_and_still_strips_clean():
    body = '{\n  "security": {\n    "csp": "x"\n  }\n}'
    built = build_contextual_chunk(
        body, source_path="tauri.conf.json", position=1, total=1, file_type="json"
    )
    header = built.split("\n", 1)[0]
    assert header.startswith("[source: tauri.conf.json")
    assert "keys: " in header and "csp" in header
    # The embedded body must stay clean — keys live in the header only.
    assert strip_contextual_header(built) == body
