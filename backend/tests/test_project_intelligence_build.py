from types import SimpleNamespace

from app.adapters.project_graph.sqlite_project_graph_repository import (
    SQLiteProjectGraphRepository,
)
from app.core.domain.project_graph import EntityType
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphScanRequiredError,
    BuildProjectGraphUseCase,
    BuildProjectGraphWorkspaceNotFoundError,
)

_WS = SimpleNamespace(id="w1", project_path="/p")
_CONTENTS = {
    "accounts/dev/ca/app/main.tf": 'provider "aws" {}\nvariable "x" {}\nmodule "m" {}',
    "accounts/prod/ca/app/backend.tf": 'backend "s3" {}\noutput "o" {}',
    "accounts/stg/terragrunt.hcl": 'remote_state {}\ninclude {}\ndependency "d" {}\ninputs = {}\nterraform { source = "x" }',
}


def _scan():
    mk = lambda p, dt: SimpleNamespace(path=p, detected_type=dt)  # noqa: E731
    return SimpleNamespace(
        files=[
            mk("accounts/dev/ca/app/main.tf", "terraform"),
            mk("accounts/prod/ca/app/backend.tf", "terraform"),
            mk("accounts/stg/terragrunt.hcl", "terragrunt"),
        ]
    )


class _WSRepo:
    def get(self, workspace_id):
        return _WS if workspace_id == "w1" else None


class _ScanRepo:
    def __init__(self, scan):
        self._scan = scan

    def get_latest_scan(self, workspace_id):
        return self._scan


class _FS:
    def read_text_file(self, root_path, relative_path):
        return _CONTENTS.get(relative_path, "")


def _use_case(tmp_path, scan):
    repo = SQLiteProjectGraphRepository(tmp_path / "pi.db")
    uc = BuildProjectGraphUseCase(_WSRepo(), _ScanRepo(scan), _FS(), repo)
    return uc, repo


def test_build_orchestrates_detected_analyzers_and_persists(tmp_path):
    uc, repo = _use_case(tmp_path, _scan())
    meta = uc.execute(BuildProjectGraphInput(workspace_id="w1"))
    assert "terraform" in meta.analyzers_run and "terragrunt" in meta.analyzers_run
    assert {"gitlab_ci", "github_actions"} <= set(meta.analyzers_skipped)
    # Signature is now a content+version hash; still encodes the file count.
    assert meta.scan_signature.startswith("sha256:")
    assert meta.scan_signature.endswith(":files:3")


def test_build_skips_rebuild_when_unchanged(tmp_path):
    uc, repo = _use_case(tmp_path, _scan())
    first = uc.execute(BuildProjectGraphInput(workspace_id="w1"))
    # Same files → second build is skipped and returns the same snapshot.
    second = uc.execute(BuildProjectGraphInput(workspace_id="w1"))
    assert second.id == first.id
    # force=True rebuilds → a new snapshot id.
    forced = uc.execute(BuildProjectGraphInput(workspace_id="w1", force=True))
    assert forced.id != first.id

    graph = repo.get_latest_graph("w1")
    assert graph is not None
    envs = sorted(e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT))
    infra = sorted(e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT))
    assert envs == ["dev", "prod", "staging"]
    assert infra == ["Terraform", "Terragrunt"]


def test_build_requires_workspace_and_scan(tmp_path):
    repo = SQLiteProjectGraphRepository(tmp_path / "pi.db")

    missing_ws = BuildProjectGraphUseCase(
        type("R", (), {"get": lambda self, w: None})(), _ScanRepo(_scan()), _FS(), repo
    )
    try:
        missing_ws.execute(BuildProjectGraphInput(workspace_id="nope"))
        raise AssertionError("expected workspace-not-found")
    except BuildProjectGraphWorkspaceNotFoundError:
        pass

    no_scan = BuildProjectGraphUseCase(_WSRepo(), _ScanRepo(None), _FS(), repo)
    try:
        no_scan.execute(BuildProjectGraphInput(workspace_id="w1"))
        raise AssertionError("expected scan-required")
    except BuildProjectGraphScanRequiredError:
        pass


def test_snapshot_round_trip_preserves_findings(tmp_path):
    uc, repo = _use_case(tmp_path, _scan())
    uc.execute(BuildProjectGraphInput(workspace_id="w1"))
    graph = repo.get_latest_graph("w1")
    # Terraform "local state" + missing remote backend should surface a finding.
    assert any(f.analyzer == "terraform" for f in graph.findings)
