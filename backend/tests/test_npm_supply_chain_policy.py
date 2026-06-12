from pathlib import Path


def test_npm_supply_chain_policy_is_explicit_and_public_registry_only() -> None:
    root = Path(__file__).resolve().parents[2]
    package_json = (root / "frontend/package.json").read_text(encoding="utf-8")
    package_lock = (root / "frontend/package-lock.json").read_text(encoding="utf-8")
    check_script = root / "scripts/check_npm_supply_chain_policy.sh"

    assert check_script.exists()
    assert '"allowScripts"' in package_json
    assert '"esbuild": true' in package_json
    assert '"fsevents": true' in package_json
    assert "packages.applied-caas-gateway" not in package_lock
    assert "internal.api.openai" not in package_lock
    assert "artifactory" not in package_lock
