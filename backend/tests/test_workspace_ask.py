from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import vector_store
from app.api.routes import workspaces as workspace_routes
from app.main import app


client = TestClient(app)


def test_ask_unknown_workspace_returns_404() -> None:
    response = client.post(
        "/workspaces/missing-workspace/ask",
        json={"question": "What is this project?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_ask_before_indexing_returns_workspace_not_indexed_diagnostic(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _ask(workspace["id"], "What is this project?")

    assert response.status_code == 200
    result = response.json()
    assert (
        result["answer"]
        == "This workspace has not been indexed yet. Run workspace indexing first."
    )
    assert result["diagnostic_code"] == "workspace_not_indexed"
    assert result["diagnostic_message"] == "No workspace index metadata was found."
    assert result["sources"] == []
    assert result["used_context_chunks"] == 0
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm"
    assert result["quality_warnings"] == []


def test_ask_with_index_metadata_but_empty_active_store_returns_diagnostic(
    tmp_path,
) -> None:
    _write_text(tmp_path / "README.md", "persisted metadata but transient chunks")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200
    vector_store.clear_workspace(workspace["id"])

    response = _ask(workspace["id"], "What is this project?")

    assert response.status_code == 200
    result = response.json()
    assert result["answer"] == "No context chunks were found in the active vector store."
    assert result["diagnostic_code"] == "index_metadata_exists_but_no_chunks_found"
    assert "reindex after API restart" in result["diagnostic_message"]
    assert "verify VECTOR_STORE, EMBEDDING_PROVIDER" in result["diagnostic_message"]
    assert result["sources"] == []
    assert result["used_context_chunks"] == 0
    assert result["quality_warnings"] == []


def test_ask_response_contains_llm_usage_metrics(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "metricstoken describes local context.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = _ask(workspace["id"], "Explain metricstoken")

    assert response.status_code == 200
    usage = response.json()["usage"]
    assert usage["provider"] == "fake"
    assert usage["model"] == "fake-llm"
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert usage["latency_ms"] >= 0
    assert usage["estimated"] is True


def test_ask_after_indexing_returns_sources_and_fake_answer(tmp_path) -> None:
    _write_text(
        tmp_path / "README.md",
        "raganswertoken describes the workspace architecture and indexing flow.",
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = _ask(workspace["id"], "Explain raganswertoken")

    assert response.status_code == 200
    result = response.json()
    assert "Fake answer" in result["answer"]
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm"
    assert result["used_context_chunks"] >= 1
    assert result["sources"]
    assert result["diagnostic_code"] is None
    assert result["diagnostic_message"] is None
    assert any(
        warning["code"] == "answer_missing_source_paths"
        for warning in result["quality_warnings"]
    )
    assert result["sources"][0]["source_path"] == "README.md"
    assert "raganswertoken" in result["sources"][0]["preview"]


def test_ask_with_fake_override_works(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "overridecontexttoken")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = _ask(
        workspace["id"],
        "Explain overridecontexttoken",
        llm_provider="fake",
        llm_model="fake-llm-alt",
    )

    assert response.status_code == 200
    result = response.json()
    assert "Fake answer" in result["answer"]
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm-alt"


def test_ask_override_reports_selected_ollama_model_without_generation(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)

    response = _ask(
        workspace["id"],
        "What is this project?",
        llm_provider="ollama",
        llm_model="qwen2.5-coder",
    )

    assert response.status_code == 200
    result = response.json()
    assert result["diagnostic_code"] == "workspace_not_indexed"
    assert result["llm_provider"] == "ollama"
    assert result["llm_model"] == "qwen2.5-coder"


def test_ask_uses_requested_provider_and_model_for_generation(
    tmp_path,
    monkeypatch,
) -> None:
    _write_text(tmp_path / "README.md", "selectedprovidertoken")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    factory = _RecordingLLMProviderFactory()
    monkeypatch.setattr(workspace_routes, "llm_provider_factory", factory)

    response = _ask(
        workspace["id"],
        "Explain selectedprovidertoken",
        llm_provider="ollama",
        llm_model="qwen2.5-coder",
    )

    assert response.status_code == 200
    result = response.json()
    assert factory.selection == ("ollama", "qwen2.5-coder")
    assert result["answer"] == "Recorded override answer from README.md."
    assert result["llm_provider"] == "ollama"
    assert result["llm_model"] == "qwen2.5-coder"


def test_ask_rejects_unsupported_llm_provider(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _ask(
        workspace["id"],
        "What is this project?",
        llm_provider="custom",
        llm_model="private-model",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported LLM provider: custom"


def test_ask_source_preview_is_limited_to_200_characters(tmp_path) -> None:
    content = "previewtoken " + ("a" * 400)
    _write_text(tmp_path / "README.md", content)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = _ask(workspace["id"], "previewtoken")

    assert response.status_code == 200
    source = response.json()["sources"][0]
    assert source["source_path"] == "README.md"
    assert len(source["preview"]) == 200


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "RAG Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _ask(
    workspace_id: str,
    question: str,
    llm_provider: str | None = None,
    llm_model: str | None = None,
):
    return client.post(
        f"/workspaces/{workspace_id}/ask",
        json={
            "question": question,
            "limit": 5,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        },
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class _RecordingLLMProvider:
    provider_name = "ollama"
    model_name = "qwen2.5-coder"

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
    ) -> str:
        assert "selectedprovidertoken" in prompt
        assert "README.md" in prompt
        return "Recorded override answer from README.md."


class _RecordingLLMProviderFactory:
    def __init__(self) -> None:
        self.selection: tuple[str | None, str | None] | None = None

    def create(self, provider: str | None = None, model: str | None = None):
        self.selection = (provider, model)
        return _RecordingLLMProvider()
