from fastapi.testclient import TestClient

from app.main import app


def test_release_candidate_audit_is_read_only_and_structured():
    client = TestClient(app)

    response = client.get("/runtime/release-candidate-audit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Release candidate audit"
    assert payload["release_label"] == "v0.1 release candidate"
    assert payload["audit_script"] == "scripts/audit_release_candidate.sh"
    assert payload["status"] in {"ready", "review", "blocked"}
    assert isinstance(payload["readiness_score"], int)
    assert payload["validation_commands"]
    assert any("Frontend never executes shell" in rule for rule in payload["safety_rules"])
    assert any("backend/.ai-workbench" in policy for policy in payload["source_archive_policy"])
