import pytest

from conftest import complete_response
from tldrgraph.feature_workflow_schema import normalize_response


def test_response_normalizes_file_evidence(source_repo, inventory):
    manifest, workflows = normalize_response(
        str(source_repo), inventory["source_hash"], inventory["files"],
        complete_response(source_repo, inventory["source_hash"]),
    )
    assert manifest["schema"] == "tldrgraph/features@3"
    assert workflows["run_application"]["steps"][0]["evidence"][0]["file"] == "app.py"


@pytest.mark.parametrize("file_name", ["../app.py", "/tmp/app.py", "missing.py"])
def test_response_rejects_unsafe_or_missing_evidence(source_repo, inventory, file_name):
    payload = complete_response(source_repo, inventory["source_hash"])
    payload["features"][0]["evidence"][0]["file"] = file_name
    with pytest.raises(ValueError, match="evidence file"):
        normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)


def test_response_rejects_stale_hash_and_invalid_range(source_repo, inventory):
    payload = complete_response(source_repo, "stale")
    with pytest.raises(ValueError, match="source_hash"):
        normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)
    payload = complete_response(source_repo, inventory["source_hash"])
    payload["features"][0]["workflow"]["steps"][0]["evidence"][0]["code_end"] = 999
    with pytest.raises(ValueError, match="exceeds"):
        normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)


def test_partial_and_pending_rules(source_repo, inventory):
    payload = complete_response(source_repo, inventory["source_hash"])
    workflow = payload["features"][0]["workflow"]
    workflow.update(status="partial", missing_coverage="UI result is not present.")
    normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)
    workflow.update(status="pending", steps=[], missing_coverage="No reliable sequence found.")
    normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)
