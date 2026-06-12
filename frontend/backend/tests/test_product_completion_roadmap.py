from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_product_completion_roadmap_is_honest_about_v1() -> None:
    response = client.get("/runtime/product-completion-roadmap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "v0.1-source-rc"
    assert "15-25" in payload["honest_completion_estimate"]
    assert any(stage["id"] == "desktop-runtime" for stage in payload["stages"])
    assert any("Signed/notarized" in item for item in payload["not_done_yet"])
    assert any("frontend shell execution" in rule for rule in payload["safety_rules"])


def test_product_completion_roadmap_route_is_documented_in_openapi() -> None:
    assert "/runtime/product-completion-roadmap" in app.openapi()["paths"]
