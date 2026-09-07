"""
Tests for TLDRGraph Standalone Interactive Visualizer (Phase 4).
"""

import os
from tldrgraph.layers import default_registry, set_registry, use_registry
from tldrgraph.visualizer import build_layers_config, generate_visualizer_html


def test_build_layers_config_default_registry():
    # An unconfigured repo now has a single "Unclassified" bucket, so the layer
    # set under test has to be named explicitly.
    with use_registry(default_registry()):
        cfg = build_layers_config()
    assert len(cfg) == 6  # 6 non-utility layers in the example registry
    assert cfg[0]["id"] == "ui"
    assert "color" in cfg[0]
    assert "border" in cfg[0]
    assert "bg" in cfg[0]


def test_build_layers_config_custom_registry():
    r = default_registry().replacing("ui", name="Frontend Layer")
    with use_registry(r):
        cfg = build_layers_config()
        assert cfg[0]["name"] == "Frontend Layer"


def test_generate_visualizer_html_file(mini_repo):
    html_path = generate_visualizer_html(str(mini_repo.root))
    assert os.path.isfile(html_path)
    assert html_path.endswith("TLDRGRAPH_VISUALIZER.html")

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Zero external CDN scripts or fonts
    assert "http://" not in content
    assert "https://" not in content
    assert "unpkg.com" not in content
    assert "cdnjs.cloudflare.com" not in content
    assert "fonts.googleapis.com" not in content

    # Self contained
    assert "<!DOCTYPE html>" in content
    assert "HIERARCHY =" in content
    assert "LAYERS_CONFIG =" in content
    assert "TLDRGraph" in content


def test_payload_carries_source_pointers_not_source_text(mini_repo):
    """Content is read live by the app; the payload only points at it."""
    from tldrgraph.visualizer import prepare_visualizer_data

    data = prepare_visualizer_data(str(mini_repo.root))

    assert data["root"] == os.path.abspath(str(mini_repo.root))
    assert data["nodes"], "expected at least one symbol node"

    for node in data["nodes"]:
        assert "code" not in node, "source text must not be inlined"
        assert node["path"], "every node needs a path to load from"
        assert node["name"], "every node needs a symbol name to re-resolve with"
        assert isinstance(node["code_start"], int)

    for module in data["modules"]:
        assert module["path"]


def test_file_less_pseudo_nodes_are_dropped(mini_repo):
    """Imported names and bare decorators have no file and no navigable target."""
    from tldrgraph.visualizer import prepare_visualizer_data

    data = prepare_visualizer_data(str(mini_repo.root))

    assert not any(m["label"] == "root_fixtures" for m in data["modules"])
    assert all(n["file"] not in ("", "project root") for n in data["nodes"])


def test_generated_html_contains_no_project_source(mini_repo):
    """A generated page must not smuggle file contents into the payload."""
    from tldrgraph.visualizer import generate_visualizer_html

    html_path = generate_visualizer_html(str(mini_repo.root))
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # A distinctive line from the fixture sources must not appear anywhere.
    for source_file in mini_repo.root.rglob("*.py"):
        for line in source_file.read_text(encoding="utf-8").split("\n"):
            stripped = line.strip()
            if len(stripped) > 40 and "def " in stripped:
                assert stripped not in content


def test_workflows_payload_structure(mini_repo):
    """Payload includes extracted workflow sequences mapping methods to files and layers."""
    from tldrgraph.visualizer import prepare_visualizer_data

    data = prepare_visualizer_data(str(mini_repo.root))
    assert "workflows" in data
    assert isinstance(data["workflows"], list)

    for wf in data["workflows"]:
        assert "id" in wf
        assert "title" in wf
        assert "root_node" in wf
        assert "file" in wf
        assert "layer" in wf
        assert "steps" in wf
        assert isinstance(wf["steps"], list)
        for s in wf["steps"]:
            assert "step_number" in s
            assert "symbol" in s
            assert "file" in s
            assert "layer" in s
            assert "node_id" in s


def test_workflow_extraction_is_not_capped_at_twenty(monkeypatch):
    """Every distinct discovered journey is retained after curated workflows."""
    import networkx as nx
    from tldrgraph.visualizer.flows_data import extract_visualizer_workflows

    graph = nx.DiGraph()
    nodes_by_id = {}
    for index in range(21):
        root = f"root_{index}"
        service = f"service_{index}"
        store = f"store_{index}"
        for node_id, label, path in (
            (root, f"handleOrder{index}()", f"src/routes/orders_{index}.py"),
            (service, f"processOrder{index}()", f"src/services/orders_{index}.py"),
            (store, f"saveOrder{index}()", f"src/data/orders_{index}.py"),
        ):
            nodes_by_id[node_id] = {
                "label": label, "file": path, "layer_id": "app",
                "layer": "Application", "is_test": False,
            }
            graph.add_node(node_id, label=label, file=path)
        graph.add_edge(root, service, relation="calls")
        graph.add_edge(root, store, relation="calls")
        graph.add_edge(service, store, relation="calls")

    monkeypatch.setattr("tldrgraph.visualizer.flows_data.CURATED_BLUEPRINTS", [])
    workflows = extract_visualizer_workflows(graph, nodes_by_id, sources=None)  # type: ignore[arg-type]

    assert len(workflows) == 21


def test_next_root_page_is_a_workflow_entry_with_one_component_edge():
    """``src/app/page.tsx`` must not be lost because it is a thin page wrapper."""
    import networkx as nx
    from tldrgraph.visualizer.flows_discover import discover_workflows, rank_entry_points

    graph = nx.DiGraph()
    nodes = {
        "home": {
            "label": "Projects()", "file": "src/app/page.tsx", "layer_id": "ui",
            "layer": "UI", "is_test": False,
        },
        "projects": {
            "label": "ProjectsPage()", "file": "src/app/projects/components/ProjectsPage.tsx",
            "layer_id": "ui", "layer": "UI", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("home", "projects", relation="calls")

    assert rank_entry_points(graph, nodes) == [("home", "Web request")]

    def format_step(node_id, step_number):
        node = nodes[node_id]
        return {"node_id": node_id, "step_number": step_number, **node}

    workflows = discover_workflows(graph, nodes, format_step, lambda steps: [])

    assert len(workflows) == 1
    assert [step["node_id"] for step in workflows[0]["steps"]] == ["home", "projects"]


def test_two_step_discovered_workflow_is_retained():
    """A short but real entry-to-service journey should still appear."""
    import networkx as nx
    from tldrgraph.visualizer.flows_discover import discover_workflows

    graph = nx.DiGraph()
    nodes = {
        "handler": {
            "label": "handleInvite()", "file": "src/routes/invite.py", "layer_id": "api",
            "layer": "API", "is_test": False,
        },
        "service": {
            "label": "sendInvite()", "file": "src/services/invite.py", "layer_id": "service",
            "layer": "Service", "is_test": False,
        },
        "audit": {
            "label": "recordInvite()", "file": "src/audit/invite.py", "layer_id": "data",
            "layer": "Data", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("handler", "service", relation="calls")
    graph.add_edge("handler", "audit", relation="calls")

    def format_step(node_id, step_number):
        node = nodes[node_id]
        return {"node_id": node_id, "step_number": step_number, **node}

    workflows = discover_workflows(graph, nodes, format_step, lambda steps: [])

    assert len(workflows) == 1
    assert [step["node_id"] for step in workflows[0]["steps"]] == ["handler", "service"]
