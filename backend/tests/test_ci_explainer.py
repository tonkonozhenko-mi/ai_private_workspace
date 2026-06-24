"""CI trigger explainer: GH Actions trigger parsing → plain-language scenarios."""

import json

from app.core.domain.analysis import (
    GitHubActionsAnalysisResult,
    GitHubActionsWorkflow,
)
from app.core.domain.project_graph import EntityType
from app.core.domain.project_graph_builder import build_project_graph
from app.core.domain.project_intelligence_view import present_ci
from app.core.use_cases.analyze_github_actions import AnalyzeGitHubActionsUseCase


def _parse_on(on_yaml: dict) -> list:
    return AnalyzeGitHubActionsUseCase._parse_trigger_rules(on_yaml)


def test_parse_trigger_rules_variants():
    # Shorthand list form.
    rules = _parse_on({"on": ["push", "pull_request"]})
    assert {r.event for r in rules} == {"push", "pull_request"}

    # Detailed dict form with branch and tag filters + schedule.
    rules = _parse_on(
        {
            "on": {
                "push": {"branches": ["main"], "tags": ["v*"]},
                "pull_request": {"branches": ["main"]},
                "schedule": [{"cron": "0 6 * * *"}],
                "workflow_dispatch": None,
            }
        }
    )
    by_event = {r.event: r for r in rules}
    assert by_event["push"].branches == ["main"]
    assert by_event["push"].tags == ["v*"]
    assert by_event["schedule"].cron == ["0 6 * * *"]
    assert "workflow_dispatch" in by_event


def _workflow(name, rules):
    return GitHubActionsWorkflow(
        path=f".github/workflows/{name}.yml",
        name=name,
        triggers=[r.event for r in rules],
        jobs_count=1,
        uses_reusable_workflows=False,
        uses_matrix=False,
        uses_permissions=True,
        has_secrets_reference=False,
        job_names=["build"],
        trigger_rules=rules,
    )


def _graph_with(workflows):
    result = GitHubActionsAnalysisResult(
        workspace_id="w1",
        project_path="/p",
        workflow_files_count=len(workflows),
        workflows=workflows,
        total_jobs_count=len(workflows),
        findings=[],
    )
    return build_project_graph("w1", github_actions=result)


def test_present_ci_scenarios():
    rules_test = _parse_on({"on": {"push": {}, "pull_request": {"branches": ["main"]}}})
    rules_deploy = _parse_on({"on": {"push": {"branches": ["main"]}}})
    rules_release = _parse_on({"on": {"push": {"tags": ["v*"]}}})
    graph = _graph_with(
        [
            _workflow("test", rules_test),
            _workflow("deploy", rules_deploy),
            _workflow("release", rules_release),
        ]
    )
    ci = present_ci(graph)
    assert ci["has_data"] is True
    by_key = {s["key"]: [w["name"] for w in s["workflows"]] for s in ci["scenarios"]}

    # `push: {}` (no filters) fires on both feature and default branches.
    assert "test" in by_key["push_feature"]
    assert "test" in by_key["push_default"]
    # deploy is gated to main only → default branch, not feature.
    assert "deploy" in by_key["push_default"]
    assert "deploy" not in by_key.get("push_feature", [])
    # PR scenario picks up the test workflow.
    assert "test" in by_key["pull_request"]
    # tag scenario picks up the release workflow.
    assert "release" in by_key["tag"]
    # Pipeline metadata carries the serialized triggers.
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    assert all(json.loads(p.metadata["triggers_json"]) is not None for p in pipelines)


def test_present_ci_empty_when_no_triggers():
    assert present_ci(build_project_graph("w1"))["has_data"] is False
