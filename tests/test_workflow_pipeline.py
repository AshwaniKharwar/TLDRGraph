import json

from click.testing import CliRunner

from conftest import complete_catalog
from tldrgraph.cli import cli
from tldrgraph.cli_pipeline import init_pipeline
from tldrgraph.feature_workflow_loader import load_feature_manifest
from tldrgraph.payload import atomic_write
from tldrgraph.source_inventory import build_source_inventory


def _write_catalog(root, source_hash):
    manifest, workflows = complete_catalog(root, source_hash)
    state = root / ".tldrgraph"
    (state / "workflows").mkdir(parents=True, exist_ok=True)
    atomic_write(str(state / "features.yaml"), manifest)
    for feature_id, workflow in workflows.items():
        atomic_write(str(state / "workflows" / f"{feature_id}.yaml"), workflow)


def _write_index(root, source_hash):
    manifest, _ = complete_catalog(root, source_hash)
    state = root / ".tldrgraph"
    state.mkdir(parents=True, exist_ok=True)
    atomic_write(str(state / "features.yaml"), manifest)


def test_direct_artifacts_and_unchanged_source(source_repo):
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    state = source_repo / ".tldrgraph"
    assert not (state / "feature_workflows_request.yaml").exists()
    assert not (state / "feature_workflows_response.yaml").exists()

    inventory = build_source_inventory(str(source_repo))
    _write_catalog(source_repo, inventory["source_hash"])
    assert init_pipeline(str(source_repo), as_json=True) == "done"
    assert (state / "TLDRGRAPH_VISUALIZER.html").is_file()
    assert init_pipeline(str(source_repo), as_json=True) == "done"


def test_completed_init_does_not_request_ui_server(source_repo, capsys):
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    inventory = build_source_inventory(str(source_repo))
    _write_catalog(source_repo, inventory["source_hash"])
    assert init_pipeline(str(source_repo)) == "done"
    assert "ui --serve" not in capsys.readouterr().out


def test_catalog_index_is_accepted_before_its_worker_writes_a_workflow(source_repo, capsys):
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    capsys.readouterr()
    inventory = build_source_inventory(str(source_repo))
    _write_index(source_repo, inventory["source_hash"])
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    output = json.loads(capsys.readouterr().out)
    assert "workflow file is missing or invalid for run_application" in " ".join(output["next_action"])


def test_changed_source_requests_regeneration(source_repo):
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    inventory = build_source_inventory(str(source_repo))
    _write_catalog(source_repo, inventory["source_hash"])
    assert init_pipeline(str(source_repo), as_json=True) == "done"
    (source_repo / "app.py").write_text("def changed():\n    return True\n", encoding="utf-8")
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"


def test_invalid_direct_artifacts_are_reported_without_handshake_files(source_repo, capsys):
    state = source_repo / ".tldrgraph"
    state.mkdir()
    atomic_write(str(state / "features.yaml"), {"schema": "old"})
    assert init_pipeline(str(source_repo), as_json=True) == "needs_feature_workflows"
    output = json.loads(capsys.readouterr().out)
    assert "features schema must be" in " ".join(output["next_action"])
    assert not (state / "feature_workflows_request.yaml").exists()
    assert not (state / "feature_workflows_response.yaml").exists()


def test_v2_manifest_is_rejected_with_regeneration_message(source_repo):
    state = source_repo / ".tldrgraph"
    state.mkdir()
    atomic_write(str(state / "features.yaml"), {"schema": "codechakra/features@2", "features": []})
    manifest, status = load_feature_manifest(str(source_repo), "hash")
    assert manifest is None
    assert "regenerate" in status


def test_v3_manifest_is_rejected_with_v4_regeneration_message(source_repo):
    state = source_repo / ".tldrgraph"
    state.mkdir()
    atomic_write(str(state / "features.yaml"), {"schema": "tldrgraph/features@3", "features": []})
    manifest, status = load_feature_manifest(str(source_repo), "hash")
    assert manifest is None
    assert "v3" in status


def test_json_status_is_machine_readable(source_repo, capsys):
    init_pipeline(str(source_repo), as_json=True)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "needs_feature_workflows"
    assert output["progress"]["source_files"] > 0
    assert output["progress"]["source_hash"]


def test_refresh_matches_init_pipeline_and_uses_refresh_text(source_repo):
    runner = CliRunner()

    result = runner.invoke(cli, ["refresh", str(source_repo)])
    assert result.exit_code == 0
    assert "TLDRGRAPH REFRESH — NEXT ACTION REQUIRED" in result.output
    assert "Run: tldrgraph refresh" in result.output

    init_result = runner.invoke(cli, ["init", str(source_repo), "--json"])
    assert init_result.exit_code == 0
    json_result = runner.invoke(cli, ["refresh", str(source_repo), "--json"])
    assert json_result.exit_code == 0
    output = json.loads(json_result.output)
    assert output == json.loads(init_result.output)
    assert output["status"] == "needs_feature_workflows"
    assert output["phase"] == "feature_workflows"
    assert set(output) == {"status", "phase", "next_action", "progress"}

    inventory = build_source_inventory(str(source_repo))
    _write_catalog(source_repo, inventory["source_hash"])
    done_result = runner.invoke(cli, ["refresh", str(source_repo), "--json"])
    assert done_result.exit_code == 0
    assert json.loads(done_result.output)["status"] == "done"

    (source_repo / "app.py").write_text("def changed():\n    return True\n", encoding="utf-8")
    stale_result = runner.invoke(cli, ["refresh", str(source_repo), "--json"])
    assert stale_result.exit_code == 0
    assert json.loads(stale_result.output)["status"] == "needs_feature_workflows"


def test_expected_cli_commands_are_exposed():
    runner = CliRunner()
    help_result = runner.invoke(cli, ["--help"])
    for command in ("init", "refresh", "ui", "install"):
        assert command in help_result.output
    for removed in ("query", "trace", "scan", "enrich", "layers", "dead-code", "doctor"):
        assert runner.invoke(cli, [removed]).exit_code == 2
