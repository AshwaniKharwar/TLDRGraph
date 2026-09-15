import pytest

from conftest import complete_response
from tldrgraph.feature_workflow_schema import normalize_response


def _branch_response(source_repo, source_hash):
    payload = complete_response(source_repo, source_hash)
    start = {"file": "app.py", "symbol": "start", "line": 1,
             "code_start": 1, "code_end": 2}
    run = {"file": "app.py", "symbol": "run", "line": 4,
           "code_start": 4, "code_end": 5}
    payload["features"][0]["workflow"]["steps"][1]["options"] = [
        {"title": "Docker path", "text": "The Docker runtime is bootstrapped.",
         "evidence": [start]},
        {"title": "Kubernetes path", "text": "The Kubernetes runtime is provisioned.",
         "evidence": [run]},
    ]
    return payload


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


def test_response_normalizes_branch_options(source_repo, inventory):
    manifest, workflows = normalize_response(
        str(source_repo), inventory["source_hash"], inventory["files"],
        _branch_response(source_repo, inventory["source_hash"]),
    )
    options = workflows["run_application"]["steps"][1]["options"]
    assert manifest["features"][0]["status"] == "generated"
    assert [option["title"] for option in options] == ["Docker path", "Kubernetes path"]
    assert options[0]["phase"] == "backend"
    assert options[1]["evidence"][0]["symbol"] == "run"


def test_response_rejects_invalid_branch_options(source_repo, inventory):
    payload = _branch_response(source_repo, inventory["source_hash"])
    payload["features"][0]["workflow"]["steps"][1]["options"][0]["title"] = ""
    with pytest.raises(ValueError, match="incomplete or invalid workflow"):
        normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)

    payload = _branch_response(source_repo, inventory["source_hash"])
    payload["features"][0]["workflow"]["steps"][1]["options"][0]["evidence"][0]["file"] = "../app.py"
    with pytest.raises(ValueError, match="evidence file"):
        normalize_response(str(source_repo), inventory["source_hash"], inventory["files"], payload)
