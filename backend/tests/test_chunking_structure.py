"""Structure-aware chunking: AST for Python, brace-aware for C-family, fenced-safe
markdown, with graceful fallback and no dropped content."""

from app.core.domain.chunking import (
    _split_brace_aware,
    _split_markdown,
    _split_python_ast,
    chunk_document,
    chunk_text,
)

PYTHON = """\
import os


def first():
    return 1


@decorator
def second(x):
    # a helper
    return x + 1


class Widget:
    def method(self):
        return os.getcwd()
"""


def test_python_ast_splits_on_top_level_defs():
    units = _split_python_ast(PYTHON)
    # header (import) + first + second + class = 4 units
    assert len(units) == 4
    assert units[0].strip() == "import os"
    assert units[1].lstrip().startswith("def first")
    # decorator stays attached to its function
    assert "@decorator" in units[2] and "def second" in units[2]
    # whole class (with its method) is one unit
    assert "class Widget" in units[3] and "def method" in units[3]


def test_python_syntax_error_falls_back_not_crash():
    broken = "def oops(:\n    pass\n"
    assert _split_python_ast(broken) == []
    # chunk_document must still produce a chunk via fallback
    assert chunk_document(broken, file_type="python")


def test_python_function_that_fits_is_never_split_mid_body():
    # Each function fits in max_chars but the two together do not, so each lands
    # in its own chunk — and a fitting function is never split internally.
    body = "\n".join(f"    x{i} = {i}" for i in range(18))
    src = f"def big_one():\n{body}\n\n\ndef big_two():\n{body}\n"
    chunks = chunk_document(src, file_type="python", max_chars=400)
    holder = [c for c in chunks if "def big_one" in c][0]
    assert "x17 = 17" in holder  # header and last body line in the same chunk


def test_brace_block_stays_together_across_blank_lines():
    js = (
        "function outer() {\n"
        "  const a = 1;\n"
        "\n"  # blank line inside the body must NOT split the function
        "  return a;\n"
        "}\n"
        "\n"
        "function other() {\n"
        "  return 2;\n"
        "}\n"
    )
    units = _split_brace_aware(js)
    outer = [u for u in units if "function outer" in u][0]
    assert "const a = 1;" in outer and "return a;" in outer


def test_markdown_does_not_split_inside_code_fence():
    md = (
        "# Title\n"
        "intro\n"
        "\n"
        "```\n"
        "# this is code, not a heading\n"
        "echo hi\n"
        "```\n"
        "\n"
        "# Real Section\n"
        "body\n"
    )
    sections = _split_markdown(md)
    # Two real headings → two sections; the '# this is code' stays in the first.
    assert len(sections) == 2
    assert "# this is code" in sections[0]


def test_no_content_is_dropped():
    chunks = chunk_document(PYTHON, file_type="python", max_chars=400)
    joined = "\n".join(chunks)
    for line in PYTHON.split("\n"):
        if line.strip():
            assert line.strip() in joined


def test_unknown_extension_routes_to_brace_split():
    go = 'package main\n\nfunc main() {\n\tprintln("hi")\n}\n'
    chunks = chunk_document(go, file_type="unknown", extension=".go", max_chars=500)
    assert any("func main" in c and "println" in c for c in chunks)


def test_chunk_text_backward_compatible():
    text = "Para one.\n\nPara two.\n\nPara three."
    assert chunk_text(text, max_chars=12, overlap=4)  # still splits prose, no error
