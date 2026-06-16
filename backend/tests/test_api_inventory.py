from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
api_inventory_path = Path(__file__).resolve().parents[2] / "docs" / "API_INVENTORY.md"

IMPORTANT_PATHS = {
    "/health",
    "/runtime/health",
    "/runtime/setup-guide",
    "/runtime/desktop-supervisor-contract",
    "/assistant-profiles",
    "/models/catalog",
    "/models/catalog/details",
    "/models/catalog/reload",
    "/models/recommend",
    "/models/switching-plan",
    "/models/experiments/plan",
    "/models/experiments/run",
    "/models/experiments/{experiment_id}",
    "/models/experiments/{experiment_id}/comparison",
    "/models/experiments/{experiment_id}/ratings",
    "/onboarding/plan",
    "/onboarding/bootstrap-workspace",
    "/projects/scan",
    "/workspaces",
    "/workspaces/overview",
    "/workspaces/{workspace_id}",
    "/workspaces/{workspace_id}/dashboard",
    "/workspaces/{workspace_id}/ui-actions",
    "/workspaces/{workspace_id}/local-ai/activation-guide",
    "/workspaces/{workspace_id}/scan",
    "/workspaces/{workspace_id}/index",
    "/workspaces/{workspace_id}/ask",
    "/workspaces/{workspace_id}/ask-selected",
    "/workspaces/{workspace_id}/analysis/summary",
    "/workspaces/{workspace_id}/commands",
    "/commands/{command_id}/execute",
    "/workspaces/{workspace_id}/timeline",
    "/workspaces/{workspace_id}/model-experiments",
    "/workspaces/{workspace_id}/model-performance",
    "/workspaces/{workspace_id}/models/recommend",
    "/workspaces/{workspace_id}/models/explain",
    "/workspaces/{workspace_id}/models/selection",
    "/workspaces/{workspace_id}/models/selection/status",
    "/workspaces/{workspace_id}/models/usage-plan",
    "/workspaces/{workspace_id}/models/embedding-indexing-plan",
    "/workspaces/{workspace_id}/models/dashboard",
    "/workspaces/{workspace_id}/models/dashboard/summary",
}


def test_important_routes_are_present_in_openapi() -> None:
    openapi_paths = set(app.openapi()["paths"])

    assert openapi_paths >= IMPORTANT_PATHS


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
    # Both routes must be registered.
    openapi_paths = set(app.openapi()["paths"])
    assert "/workspaces/overview" in openapi_paths
    assert "/workspaces/{workspace_id}" in openapi_paths

    # The literal /workspaces/overview route must take precedence over the
    # /workspaces/{workspace_id} parameter route. Verify behaviorally (robust
    # across FastAPI/Starlette versions): if precedence were wrong, this would
    # be captured by the {workspace_id} handler and not return 200.
    response = client.get("/workspaces/overview")
    assert response.status_code == 200
