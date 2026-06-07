from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
api_inventory_path = Path(__file__).resolve().parents[2] / "docs" / "API_INVENTORY.md"

IMPORTANT_PATHS = {
    "/health",
    "/runtime/health",
    "/runtime/setup-guide",
    "/assistant-profiles",
    "/models/catalog",
    "/models/catalog/details",
    "/models/catalog/reload",
    "/models/recommend",
    "/models/switching-plan",
    "/onboarding/plan",
    "/onboarding/bootstrap-workspace",
    "/projects/scan",
    "/workspaces",
    "/workspaces/overview",
    "/workspaces/{workspace_id}",
    "/workspaces/{workspace_id}/dashboard",
    "/workspaces/{workspace_id}/scan",
    "/workspaces/{workspace_id}/index",
    "/workspaces/{workspace_id}/ask",
    "/workspaces/{workspace_id}/analysis/summary",
    "/workspaces/{workspace_id}/commands",
    "/commands/{command_id}/execute",
    "/workspaces/{workspace_id}/timeline",
}


def test_important_routes_are_present_in_openapi() -> None:
    openapi_paths = set(app.openapi()["paths"])

    assert IMPORTANT_PATHS <= openapi_paths


def test_api_inventory_documents_every_openapi_path() -> None:
    inventory = api_inventory_path.read_text(encoding="utf-8")

    assert all(path in inventory for path in app.openapi()["paths"])


def test_public_routes_have_openapi_tags() -> None:
    untagged_routes = [
        route.path
        for route in app.routes
        if getattr(route, "include_in_schema", False) and not getattr(route, "tags", [])
    ]

    assert untagged_routes == []


def test_workspaces_overview_does_not_conflict_with_workspace_id_route() -> None:
    route_paths = [route.path for route in app.routes]

    assert route_paths.index("/workspaces/overview") < route_paths.index(
        "/workspaces/{workspace_id}"
    )
    response = client.get("/workspaces/overview")
    assert response.status_code == 200
