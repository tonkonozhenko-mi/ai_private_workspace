from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_final_product_status_is_clear_about_source_rc_and_v1() -> None:
    response = client.get("/runtime/final-product-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "v0.1-source-rc-ready"
    assert "source release candidate" in payload["summary"]
    assert "15-25" in payload["honest_v1_estimate"]
    assert any(stage["id"] == "installers" for stage in payload["stages"])
    assert any(command["label"] == "Release audit" for command in payload["publication_checks"])
    assert any("Frontend must never run shell" in rule for rule in payload["safety_rules"])


def test_final_product_status_route_is_documented_in_openapi() -> None:
    assert "/runtime/final-product-status" in app.openapi()["paths"]
