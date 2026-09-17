from conftest import complete_catalog
from tldrgraph.payload import atomic_write
from tldrgraph.source_inventory import build_source_inventory
from tldrgraph.visualizer import generate_visualizer_html, prepare_visualizer_data


def _apply(source_repo):
    inventory = build_source_inventory(str(source_repo))
    state = source_repo / ".tldrgraph"
    (state / "workflows").mkdir(parents=True, exist_ok=True)
    manifest, workflows = complete_catalog(source_repo, inventory["source_hash"])
    atomic_write(str(state / "features.yaml"), manifest)
    for feature_id, workflow in workflows.items():
        atomic_write(str(state / "workflows" / f"{feature_id}.yaml"), workflow)
    return inventory, manifest


def _apply_with_branch(source_repo):
    inventory = build_source_inventory(str(source_repo))
    state = source_repo / ".tldrgraph"
    (state / "workflows").mkdir(parents=True, exist_ok=True)
    manifest, workflows = complete_catalog(source_repo, inventory["source_hash"])
    workflows["run_application"]["steps"][1]["options"] = [
        {"phase": "backend", "title": "Docker path", "text": "The Docker runtime is bootstrapped.",
         "evidence": [{"file": "app.py", "symbol": "start", "line": 1,
                       "code_start": 1, "code_end": 2}]},
        {"phase": "backend", "title": "Kubernetes path", "text": "The Kubernetes runtime is provisioned.",
         "evidence": [{"file": "app.py", "symbol": "run", "line": 4,
                       "code_start": 4, "code_end": 5}]},
    ]
    atomic_write(str(state / "features.yaml"), manifest)
    atomic_write(str(state / "workflows" / "run_application.yaml"), workflows["run_application"])
    return inventory, manifest


def test_payload_contains_only_workflow_surface(source_repo):
    _apply(source_repo)
    payload = prepare_visualizer_data(str(source_repo))
    assert set(payload) == {"root", "workflow_areas", "workflows", "workflow_state", "source_files"}
    assert payload["source_files"][0]["path"] == "app.py"
    assert payload["workflows"][0]["steps"][0]["evidence"][0]["symbol"] == "run"


def test_payload_preserves_branch_options(source_repo):
    _apply_with_branch(source_repo)
    payload = prepare_visualizer_data(str(source_repo))
    options = payload["workflows"][0]["steps"][1]["options"]
    assert [option["title"] for option in options] == ["Docker path", "Kubernetes path"]
    assert options[0]["evidence"][0]["symbol"] == "start"
    assert options[1]["phase"] == "backend"


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
    assert "options" in html
    assert "Connect project" not in html
    assert "Architecture Map" not in html
    assert "module_edges" not in html
    assert "child_edges" not in html
    assert "https://" not in html


def test_generated_html_uses_vertical_flowchart_renderer(source_repo):
    _apply_with_branch(source_repo)
    html = open(generate_visualizer_html(str(source_repo)), encoding="utf-8").read()
    assert "let direction = 'vertical'" in html
    assert "function drawDecision" in html
    assert "function buildVerticalGroups" in html
    assert "function contains(shape, point)" in html
    assert 'id="direction-vertical" class="active"' in html


def test_generated_html_starts_workflows_below_the_header_at_fifty_percent(source_repo):
    _apply(source_repo)
    html = open(generate_visualizer_html(str(source_repo)), encoding="utf-8").read()
    assert "const DEFAULT_ZOOM = 0.5" in html
    assert "function resetWorkflowView()" in html
    assert "const protectedTop = Math.max(170, headerBox.bottom - box.top + 32)" in html
    assert '<span id="zoom-label">50%</span>' in html
