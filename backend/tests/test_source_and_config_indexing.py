"""A real repository — not just Python and Terraform — reaches the index.

Every case here is a file the index used to be blind to (a .ts module, a
pyproject.toml, a CSV, a notebook) or a file it must stay blind to (a lockfile, a
minified bundle, a real .env).
"""

import json

import pytest

from app.adapters.documents.local_document_extractor import LocalDocumentExtractor
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.core.domain.chunking import build_contextual_chunk, config_keys
from app.core.domain.project_graph_builder import build_project_graph
from app.core.domain.project_type import KIND_APPLICATION, classify_project
from app.core.domain.source_files import dominant_source_language, is_generated_source
from app.core.use_cases.index_workspace import INDEXABLE_FILE_TYPES, IndexWorkspaceUseCase


def _detected(tmp_path) -> dict[str, str]:
    return {f.path: f.detected_type for f in LocalFileSystem().list_files(str(tmp_path))}


def test_source_and_config_files_are_detected_and_indexable(tmp_path):
    (tmp_path / "api.ts").write_text("export function health() { return 'ok'; }\n")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    (tmp_path / "Makefile").write_text("build:\n\tgo build ./...\n")
    (tmp_path / "pom.xml").write_text("<project><artifactId>payments</artifactId></project>")
    (tmp_path / ".env.example").write_text("DATABASE_URL=postgres://localhost/dev\n")

    detected = _detected(tmp_path)
    assert detected["api.ts"] == "source_code"
    assert detected["main.go"] == "source_code"
    assert detected["pyproject.toml"] == "config"
    assert detected["Makefile"] == "makefile"
    assert detected["pom.xml"] == "xml_config"
    assert detected[".env.example"] == "config"
    assert set(detected.values()) <= INDEXABLE_FILE_TYPES | {"unknown"}
    for file_type in ("source_code", "config", "makefile", "xml_config"):
        assert file_type in INDEXABLE_FILE_TYPES


def test_lockfiles_bundles_and_real_env_are_never_indexed(tmp_path):
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}')
    (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n")
    (tmp_path / "go.sum").write_text("golang.org/x/net v0.0.1 h1:abc=\n")
    (tmp_path / "app.min.js").write_text("!function(){}();")
    (tmp_path / "bundle.js.map").write_text('{"version":3}')
    (tmp_path / ".env").write_text("AWS_SECRET_ACCESS_KEY=hunter2\n")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.js").write_text("console.log(1)\n")

    detected = _detected(tmp_path)
    for path in (
        "package-lock.json",
        "yarn.lock",
        "go.sum",
        "app.min.js",
        "bundle.js.map",
        ".env",
    ):
        assert detected[path] == "unknown", path
        assert detected[path] not in INDEXABLE_FILE_TYPES

    # dist/ never even reaches classification: the walk prunes build output.
    assert "dist/index.js" not in detected


def test_a_minified_source_file_is_refused_by_content(tmp_path):
    # Survives every name check (plain .js) but is one 3000-character line.
    minified = "var a=1;" + "x" * 3000 + "\n"
    (tmp_path / "vendor.js").write_text(minified)
    assert is_generated_source(minified)

    use_case = IndexWorkspaceUseCase(
        workspace_repository=None,
        project_scan_repository=None,
        file_system=LocalFileSystem(),
        embedding_provider=None,
        vector_store=None,
        index_status_repository=None,
    )
    scan = LocalFileSystem().list_files(str(tmp_path))
    bundle = next(f for f in scan if f.path == "vendor.js")

    chunks, _ = use_case._chunks_for_file("ws-1", str(tmp_path), bundle)
    assert chunks == []


def test_a_typescript_file_is_chunked_and_indexed(tmp_path):
    (tmp_path / "AnswerFeedback.tsx").write_text(
        "export function AnswerFeedback({ answerId }: Props) {\n"
        "  // Records a thumbs up or down against the answer.\n"
        "  return <button onClick={() => rate(answerId)}>Helpful</button>;\n"
        "}\n"
    )
    use_case = IndexWorkspaceUseCase(
        workspace_repository=None,
        project_scan_repository=None,
        file_system=LocalFileSystem(),
        embedding_provider=None,
        vector_store=None,
        index_status_repository=None,
    )
    scan = LocalFileSystem().list_files(str(tmp_path))
    component = next(f for f in scan if f.path == "AnswerFeedback.tsx")

    chunks, file_hash = use_case._chunks_for_file("ws-1", str(tmp_path), component)
    assert file_hash
    assert chunks
    assert "AnswerFeedback" in chunks[0].content
    assert chunks[0].content.startswith("[source: AnswerFeedback.tsx")


def test_toml_keys_reach_the_chunk_header(tmp_path):
    content = "[tool.ruff]\nline-length = 100\nselect = ['E', 'F']\n"
    keys = config_keys(content, file_type="config", extension=".toml")
    assert "tool.ruff" in keys
    assert "line-length" in keys

    header = build_contextual_chunk(
        content,
        source_path="pyproject.toml",
        position=1,
        total=1,
        file_type="config",
        extension=".toml",
    ).splitlines()[0]
    assert "line-length" in header  # so "what linting rules are configured" can hit it


def test_csv_rows_carry_their_header_and_a_row_locator(tmp_path):
    (tmp_path / "costs.csv").write_text(
        "environment,monthly_cost_usd,owner\nproduction,4200,platform\nstaging,900,platform\n"
    )
    assert _detected(tmp_path)["costs.csv"] == "tabular_data"

    result = LocalDocumentExtractor().extract(str(tmp_path), "costs.csv", "tabular_data")
    assert result.skipped_reason is None
    assert result.sections[0].locator == "rows 2-3"
    assert "monthly_cost_usd" in result.sections[0].text  # header repeated with the rows
    assert "4200" in result.sections[0].text


def test_notebook_cells_are_addressed_by_number_and_outputs_are_dropped(tmp_path):
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Revenue model\n"]},
            {
                "cell_type": "code",
                "source": ["df = load('sales.csv')\n"],
                "outputs": [{"data": {"image/png": "BASE64BLOBTHATMUSTNOTBEINDEXED"}}],
            },
        ]
    }
    (tmp_path / "model.ipynb").write_text(json.dumps(notebook))
    assert _detected(tmp_path)["model.ipynb"] == "notebook"

    result = LocalDocumentExtractor().extract(str(tmp_path), "model.ipynb", "notebook")
    assert [s.locator for s in result.sections] == ["cell 1", "cell 2"]
    body = "\n".join(s.text for s in result.sections)
    assert "Revenue model" in body
    assert "load('sales.csv')" in body
    assert "BASE64BLOBTHATMUSTNOTBEINDEXED" not in body


def test_a_corrupt_notebook_is_skipped_with_a_reason(tmp_path):
    (tmp_path / "broken.ipynb").write_text("{not json at all")
    result = LocalDocumentExtractor().extract(str(tmp_path), "broken.ipynb", "notebook")
    assert result.sections == []
    assert result.skipped_reason


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["a.ts", "b.tsx", "c.ts", "d.go"], "TypeScript"),
        (["main.go", "server.go", "util.go"], "Go"),
        (["notes.txt"], None),
    ],
)
def test_dominant_source_language(paths, expected):
    assert dominant_source_language(paths)[0] == expected


def test_a_typescript_repo_introduces_itself_as_a_typescript_application():
    graph = build_project_graph(
        "ws-1",
        source_paths=["src/app.ts", "src/api.ts", "src/ui.tsx"],
    )
    classification = classify_project(graph)
    assert classification.kind == KIND_APPLICATION
    assert classification.label == "TypeScript application"


def test_one_stray_source_file_does_not_make_a_project_an_application():
    graph = build_project_graph("ws-1", source_paths=["scripts/helper.ts"])
    assert classify_project(graph).label == ""  # unknown, not "TypeScript application"
