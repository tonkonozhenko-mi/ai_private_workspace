from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_indexing_workspace_with_latest_scan_indexes_expected_files(tmp_path) -> None:
    _write_indexable_project(tmp_path)
    _write_text(tmp_path / "notes.bin", "ignore me")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.post(f"/workspaces/{workspace['id']}/index")

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["indexed_files_count"] >= 5
    assert result["chunks_count"] >= result["indexed_files_count"]
    assert result["skipped_files_count"] >= 1
    source_paths = {document["source_path"] for document in result["documents"]}
    assert {
        "README.md",
        "main.tf",
        "app.py",
        ".gitlab-ci.yml",
        ".github/workflows/ci.yml",
    }.issubset(source_paths)


def test_search_returns_relevant_indexed_chunks(tmp_path) -> None:
    _write_indexable_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace['id']}/context/search",
        params={"query": "ragcontexttoken", "limit": 3},
    )

    assert response.status_code == 200
    results = response.json()
    assert results
    assert results[0]["source_path"] == "README.md"
    assert "ragcontexttoken" in results[0]["content"]
    assert results[0]["score"] > 0
    assert results[0]["metadata"]["detected_type"] == "markdown"


def test_indexing_requires_scan_first(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.post(f"/workspaces/{workspace['id']}/index")

    assert response.status_code == 400
    assert response.json()["detail"] == "Project scan required before indexing workspace"


def test_indexing_unknown_workspace_returns_404() -> None:
    response = client.post("/workspaces/missing-workspace/index")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_search_unknown_workspace_returns_404() -> None:
    response = client.get(
        "/workspaces/missing-workspace/context/search",
        params={"query": "anything"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_reindex_clears_previous_workspace_index(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "alphaindexterm")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    search_response = client.get(
        f"/workspaces/{workspace['id']}/context/search",
        params={"query": "alphaindexterm"},
    )
    assert search_response.status_code == 200
    assert search_response.json()

    (tmp_path / "README.md").unlink()
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    reindex_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert reindex_response.status_code == 200
    assert reindex_response.json()["chunks_count"] == 0

    cleared_search_response = client.get(
        f"/workspaces/{workspace['id']}/context/search",
        params={"query": "alphaindexterm"},
    )

    assert cleared_search_response.status_code == 200
    assert cleared_search_response.json() == []


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Index Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _write_indexable_project(root: Path) -> None:
    _write_text(
        root / "README.md",
        "# Example\n\nThis project contains ragcontexttoken for context search.",
    )
    _write_text(root / "main.tf", 'resource "null_resource" "example" {}')
    _write_text(root / "app.py", "print('hello')")
    _write_text(
        root / ".gitlab-ci.yml",
        """
stages:
  - test

test:
  stage: test
  script:
    - echo test
""".strip(),
    )
    _write_text(
        root / ".github" / "workflows" / "ci.yml",
        """
name: CI
on:
  push:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""".strip(),
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
