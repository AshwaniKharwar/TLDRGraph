import json

import yaml
from click.testing import CliRunner

from conftest import complete_response
from tldrgraph.cli import cli
from tldrgraph.cli_pipeline import init_pipeline
from tldrgraph.feature_workflow_loader import load_feature_manifest
from tldrgraph.payload import atomic_write
from tldrgraph.source_inventory import build_source_inventory


def test_two_run_handoff_and_unchanged_source(source_repo):
    first = init_pipeline(str(source_repo), as_json=True)
    assert first == "needs_feature_workflows"
    request = yaml.safe_load((source_repo / ".tldrgraph/feature_workflows_request.yaml").read_text())
    assert request["schema"] == "tldrgraph/feature-workflows-request@3"
    assert "investigation_leads" not in request
    response = complete_response(source_repo, request["source_hash"])
    atomic_write(str(source_repo / ".tldrgraph/feature_workflows_response.yaml"), response)
    assert init_pipeline(str(source_repo), as_json=True) == "done"
    assert (source_repo / ".tldrgraph/TLDRGRAPH_VISUALIZER.html").is_file()
    assert init_pipeline(str(source_repo), as_json=True) == "done"


def test_completed_init_does_not_request_ui_server(source_repo, capsys):
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    request = yaml.safe_load((source_repo / ".tldrgraph/feature_workflows_request.yaml").read_text())
    atomic_write(
        str(source_repo / ".tldrgraph/feature_workflows_response.yaml"),
        complete_response(source_repo, request["source_hash"]),
    )

    assert init_pipeline(str(source_repo)) == "done"
    assert "ui --serve" not in capsys.readouterr().out


def test_changed_source_requests_regeneration(source_repo):
    inventory = build_source_inventory(str(source_repo))
    payload = complete_response(source_repo, inventory["source_hash"])
    atomic_write(str(source_repo / ".tldrgraph/feature_workflows_response.yaml"), payload)
    init_pipeline(str(source_repo), as_json=True)
    (source_repo / "app.py").write_text("def changed():\n    return True\n", encoding="utf-8")
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"


def test_invalid_response_is_preserved_and_reported(source_repo):
    state = source_repo / ".tldrgraph"
    state.mkdir()
    atomic_write(str(state / "feature_workflows_response.yaml"), {"schema": "old"})
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    assert (state / "feature_workflows_response.yaml").exists()
    request = yaml.safe_load((state / "feature_workflows_request.yaml").read_text())
    assert "response schema must be" in request["previous_response_error"]


def test_v2_manifest_is_rejected_with_regeneration_message(source_repo):
    state = source_repo / ".tldrgraph"
    state.mkdir()
    atomic_write(str(state / "features.yaml"), {"schema": "codechakra/features@2", "features": []})
    manifest, status = load_feature_manifest(str(source_repo), "hash")
    assert manifest is None
    assert "regenerate" in status


def test_json_status_is_machine_readable(source_repo, capsys):
    init_pipeline(str(source_repo), as_json=True)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "needs_feature_workflows"
    assert output["progress"]["source_files"] > 0


def test_only_three_cli_commands_are_exposed():
    runner = CliRunner()
    help_result = runner.invoke(cli, ["--help"])
    for command in ("init", "ui", "install"):
        assert command in help_result.output
    for removed in ("query", "trace", "scan", "enrich", "layers", "dead-code", "doctor"):
        assert runner.invoke(cli, [removed]).exit_code == 2
