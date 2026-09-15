import pytest

from conftest import complete_catalog
from tldrgraph.feature_workflow_schema import validate_catalog_artifacts


def _catalog(source_repo, source_hash):
    return complete_catalog(source_repo, source_hash)


def _branch_catalog(source_repo, source_hash):
    manifest, workflows = _catalog(source_repo, source_hash)
    start = {"file": "app.py", "symbol": "start", "line": 1, "code_start": 1, "code_end": 2}
    run = {"file": "app.py", "symbol": "run", "line": 4, "code_start": 4, "code_end": 5}
    workflows["run_application"]["steps"][1]["options"] = [
        {"phase": "backend", "title": "Docker path", "text": "The Docker runtime is bootstrapped.", "evidence": [start]},
        {"phase": "backend", "title": "Kubernetes path", "text": "The Kubernetes runtime is provisioned.", "evidence": [run]},
    ]
    return manifest, workflows


def test_direct_catalog_validates_file_evidence(source_repo, inventory):
    manifest, workflows = _catalog(source_repo, inventory["source_hash"])
    result, validated = validate_catalog_artifacts(
        str(source_repo), inventory["source_hash"], inventory["files"], manifest, workflows,
    )
    assert result["schema"] == "tldrgraph/features@4"
    assert validated["run_application"]["steps"][0]["evidence"][0]["file"] == "app.py"


@pytest.mark.parametrize("file_name", ["../app.py", "/tmp/app.py", "missing.py"])
def test_direct_catalog_rejects_unsafe_or_missing_evidence(source_repo, inventory, file_name):
    manifest, workflows = _catalog(source_repo, inventory["source_hash"])
    workflows["run_application"]["evidence"][0]["file"] = file_name
    with pytest.raises(ValueError, match="evidence file"):
        validate_catalog_artifacts(str(source_repo), inventory["source_hash"], inventory["files"], manifest, workflows)


def test_direct_catalog_rejects_stale_hash_and_invalid_range(source_repo, inventory):
    manifest, workflows = _catalog(source_repo, "stale")
    with pytest.raises(ValueError, match="source_hash"):
        validate_catalog_artifacts(str(source_repo), inventory["source_hash"], inventory["files"], manifest, workflows)
    manifest, workflows = _catalog(source_repo, inventory["source_hash"])
    workflows["run_application"]["steps"][0]["evidence"][0]["code_end"] = 999
    with pytest.raises(ValueError, match="exceeds"):
        validate_catalog_artifacts(str(source_repo), inventory["source_hash"], inventory["files"], manifest, workflows)


def test_direct_catalog_validates_branch_options(source_repo, inventory):
    manifest, workflows = _branch_catalog(source_repo, inventory["source_hash"])
    _, validated = validate_catalog_artifacts(str(source_repo), inventory["source_hash"], inventory["files"], manifest, workflows)
    assert [option["title"] for option in validated["run_application"]["steps"][1]["options"]] == ["Docker path", "Kubernetes path"]


def test_direct_catalog_rejects_missing_workflow(source_repo, inventory):
    manifest, _ = _catalog(source_repo, inventory["source_hash"])
    with pytest.raises(ValueError, match="workflow file is missing"):
        validate_catalog_artifacts(str(source_repo), inventory["source_hash"], inventory["files"], manifest, {})


def test_direct_catalog_reports_every_missing_workflow(source_repo, inventory):
    manifest, workflows = _catalog(source_repo, inventory["source_hash"])
    duplicate = dict(manifest["features"][0])
    duplicate.update(id="second_feature", title="Second feature", workflow_path=".tldrgraph/workflows/second_feature.yaml")
    manifest["features"].append(duplicate)
    with pytest.raises(ValueError, match="run_application.*second_feature"):
        validate_catalog_artifacts(str(source_repo), inventory["source_hash"], inventory["files"], manifest, {})
