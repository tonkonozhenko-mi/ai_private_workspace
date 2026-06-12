from app.core.domain.command_risk import classify_command_risk


def test_risk_classifier_readonly() -> None:
    assert classify_command_risk("git status --short") == "readonly"
    assert classify_command_risk("terraform plan") == "readonly"
    assert classify_command_risk("helm lint ./chart") == "readonly"


def test_risk_classifier_write() -> None:
    assert classify_command_risk("git checkout feature-branch") == "write"
    assert classify_command_risk("mkdir reports") == "write"
    assert classify_command_risk("mv old new") == "write"


def test_risk_classifier_destructive_wins() -> None:
    assert classify_command_risk("git status && rm -rf build") == "destructive"
    assert classify_command_risk("git checkout main && git reset --hard") == "destructive"
    assert classify_command_risk("terraform apply") == "destructive"


def test_risk_classifier_unknown_fallback() -> None:
    assert classify_command_risk("python scripts/check.py") == "unknown"
