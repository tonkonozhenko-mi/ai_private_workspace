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


def test_rename_conversation_and_list_includes_answer_history_metadata(tmp_path: Path) -> None:
    _write_text(tmp_path / "README.md", "renametoken is documented here.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    ask_response = client.post(
        f"/workspaces/{workspace['id']}/ask",
        json={"question": "Explain renametoken", "limit": 5},
    )
    assert ask_response.status_code == 200
    conversation_id = ask_response.json()["conversation_id"]

    rename_response = client.patch(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}",
        json={"title": "Renamed local answer history"},
    )

    assert rename_response.status_code == 200
    renamed = rename_response.json()
    assert renamed["title"] == "Renamed local answer history"
    assert renamed["user_messages_count"] == 1
    assert renamed["assistant_messages_count"] == 1
    assert renamed["total_tokens"] > 0
    assert renamed["last_question"] == "Explain renametoken"
    assert renamed["last_answer_preview"]

    listed = client.get(f"/workspaces/{workspace['id']}/conversations").json()
    assert listed[0]["title"] == "Renamed local answer history"
    assert listed[0]["assistant_messages_count"] == 1
    assert listed[0]["last_answer_preview"]


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


def test_conversation_pin_archive_and_search_filters(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    alpha = client.post(
        f"/workspaces/{workspace['id']}/conversations",
        json={"title": "Alpha deployment review"},
    ).json()
    beta = client.post(
        f"/workspaces/{workspace['id']}/conversations",
        json={"title": "Beta incident notes"},
    ).json()

    pin_response = client.patch(
        f"/workspaces/{workspace['id']}/conversations/{beta['id']}/pin",
        json={"pinned": True},
    )
    assert pin_response.status_code == 200
    assert pin_response.json()["is_pinned"] is True
    assert pin_response.json()["pinned_at"]

    listed = client.get(f"/workspaces/{workspace['id']}/conversations").json()
    assert listed[0]["id"] == beta["id"]
    assert listed[0]["is_pinned"] is True

    pinned_only = client.get(
        f"/workspaces/{workspace['id']}/conversations?pinned_only=true"
    ).json()
    assert [conversation["id"] for conversation in pinned_only] == [beta["id"]]

    search_results = client.get(
        f"/workspaces/{workspace['id']}/conversations?search=deployment"
    ).json()
    assert [conversation["id"] for conversation in search_results] == [alpha["id"]]

    archive_response = client.patch(
        f"/workspaces/{workspace['id']}/conversations/{alpha['id']}/archive",
        json={"archived": True},
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["is_archived"] is True

    active_only = client.get(f"/workspaces/{workspace['id']}/conversations").json()
    assert alpha["id"] not in {conversation["id"] for conversation in active_only}

    with_archived = client.get(
        f"/workspaces/{workspace['id']}/conversations?include_archived=true"
    ).json()
    assert alpha["id"] in {conversation["id"] for conversation in with_archived}


def test_conversation_export_and_answer_notes(tmp_path: Path) -> None:
    _write_text(tmp_path / "README.md", "exportnotetoken documents answer export and notes.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    ask_response = client.post(
        f"/workspaces/{workspace['id']}/ask",
        json={"question": "Explain exportnotetoken", "limit": 5},
    )
    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    conversation_id = ask_payload["conversation_id"]
    message_id = ask_payload["conversation_message_id"]
    assert message_id

    export_response = client.get(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}/export?format=markdown"
    )
    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported["filename"].endswith(".md")
    assert "Explain exportnotetoken" in exported["content"]
    assert "Assistant" in exported["content"]

    note_response = client.post(
        f"/workspaces/{workspace['id']}/conversations/{conversation_id}/messages/{message_id}/note",
        json={"title": "Useful export note"},
    )
    assert note_response.status_code == 200
    note = note_response.json()
    assert note["title"] == "Useful export note"
    assert note["source_question"] == "Explain exportnotetoken"
    assert note["content"]

    notes = client.get(f"/workspaces/{workspace['id']}/answer-notes?search=export").json()
    assert [item["id"] for item in notes] == [note["id"]]

    delete_response = client.delete(f"/workspaces/{workspace['id']}/answer-notes/{note['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/workspaces/{workspace['id']}/answer-notes").json() == []
