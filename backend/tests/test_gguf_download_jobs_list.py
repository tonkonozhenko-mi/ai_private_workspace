"""The GGUF downloads list endpoint lets the UI re-attach to a download that is
still running after its panel was remounted (e.g. after toggling the engine)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_gguf_downloads_returns_a_list() -> None:
    response = client.get("/models/gguf-downloads")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_started_download_appears_in_the_list() -> None:
    start = client.post("/models/gguf-downloads", json={"model_id": "nomic-embed-text"})
    assert start.status_code == 200
    job = start.json()

    listed = client.get("/models/gguf-downloads")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert job["id"] in ids
    by_id = {item["id"]: item for item in listed.json()}
    assert by_id[job["id"]]["model_id"] == "nomic-embed-text"

    # Clean up so the job doesn't keep running against the network during tests.
    client.post(f"/models/gguf-downloads/{job['id']}/cancel")
