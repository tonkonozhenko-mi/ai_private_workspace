from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ask_creates_persistent_conversation(tmp_path: Path) -> None:
    _write_text(tmp_path / "README.md", "conversationtoken documents persistent chat history.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    ask_response = client.post(
        f"/workspaces/{workspace['id']}/ask",
        json={"question": "Explain conversationtoken", "limit": 5},
    )

    assert ask_response.status_code == 200
    conversation_id = ask_response.json()["conversation_id"]
    assert conversation_id

    conversation_response = client.get(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}"
    )
    assert conversation_response.status_code == 200
    conversation = conversation_response.json()
    assert conversation["messages_count"] == 2
    assert conversation["messages"][0]["role"] == "user"
    assert conversation["messages"][1]["role"] == "assistant"
    assert conversation["messages"][1]["total_tokens"] > 0


def test_ask_appends_to_existing_conversation(tmp_path: Path) -> None:
    _write_text(tmp_path / "README.md", "appendconversationtoken")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    created = client.post(
        f"/workspaces/{workspace['id']}/conversations",
        json={"title": "Manual thread"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    for _ in range(2):
        response = client.post(
            f"/workspaces/{workspace['id']}/ask",
            json={
                "question": "Explain appendconversationtoken",
                "limit": 5,
                "conversation_id": conversation_id,
            },
        )
        assert response.status_code == 200
        assert response.json()["conversation_id"] == conversation_id

    conversation = client.get(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}"
    ).json()
    assert conversation["messages_count"] == 4


def test_delete_conversation_removes_history(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    created = client.post(
        f"/workspaces/{workspace['id']}/conversations",
        json={"title": "Delete me"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    delete_response = client.delete(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}"
    )
    assert delete_response.status_code == 204
    assert client.get(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}"
    ).status_code == 404


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Conversation Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
