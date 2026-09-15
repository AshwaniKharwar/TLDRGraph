from conftest import complete_response
from tldrgraph.feature_workflow_handoff import apply_feature_workflow_response
from tldrgraph.payload import atomic_write
from tldrgraph.source_inventory import build_source_inventory
from tldrgraph.visualizer import generate_visualizer_html, prepare_visualizer_data


def _apply(source_repo):
    inventory = build_source_inventory(str(source_repo))
    state = source_repo / ".tldrgraph"
    state.mkdir(exist_ok=True)
    atomic_write(str(state / "feature_workflows_response.yaml"),
                 complete_response(source_repo, inventory["source_hash"]))
    manifest, error = apply_feature_workflow_response(str(source_repo), inventory)
    assert not error
    return inventory, manifest


def test_payload_contains_only_workflow_surface(source_repo):
    _apply(source_repo)
    payload = prepare_visualizer_data(str(source_repo))
    assert set(payload) == {"root", "workflow_areas", "workflows", "workflow_state", "source_files"}
    assert payload["source_files"][0]["path"] == "app.py"
    assert payload["workflows"][0]["steps"][0]["evidence"][0]["symbol"] == "run"


def test_stale_catalog_remains_visible_with_warning_state(source_repo):
    _apply(source_repo)
    (source_repo / "app.py").write_text("# moved\ndef start():\n    return True\n", encoding="utf-8")
    payload = prepare_visualizer_data(str(source_repo))
    assert payload["workflow_state"]["state"] == "stale_features"
    assert payload["workflows"]


def test_generated_html_is_standalone_and_graph_free(source_repo):
    _apply(source_repo)
    html = open(generate_visualizer_html(str(source_repo)), encoding="utf-8").read()
    assert "Workflow Explorer" in html
    assert "source_files" in html
    assert "Connect project" not in html
    assert "Architecture Map" not in html
    assert "module_edges" not in html
    assert "child_edges" not in html
    assert "https://" not in html
