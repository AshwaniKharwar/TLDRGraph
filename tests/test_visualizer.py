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
    assert "findRouteRegistration" in content
    assert "route_path" in content
    assert "normalizeFileHighlight" in content
    assert "openFileViewer(hit.file, { start: start, end: end });" in content


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


def test_endpoint_payload_retains_route_metadata_without_overwriting_file_path(tmp_path):
    from tldrgraph.visualizer.data import _build_single_node_record
    from tldrgraph.visualizer.source import SourceIndex

    source_file = tmp_path / "routes.ts"
    source_file.write_text('router.post("/containers/create", handler);\n', encoding="utf-8")

    node, *_ = _build_single_node_record(
        {
            "id": "endpoint_post_containers_create",
            "label": "POST /containers/create",
            "display_label": "POST /containers/create",
            "file": "routes.ts",
            "source_location": "L1",
            "layer_id": "api_workflows",
            "layer": "API Workflows",
            "kind": "API Endpoint",
            "method": "post",
            "path": "/containers/create",
        },
        {
            "api_workflows": {
                "name": "API Workflows",
                "color": "#fff",
                "border": "#fff",
                "bg": "#000",
            }
        },
        SourceIndex(str(tmp_path)),
    )

    assert node["path"] == "routes.ts"
    assert node["route_path"] == "/containers/create"
    assert node["method"] == "post"
    assert node["kind"] == "API Endpoint"
    assert node["code_start"] == 1


def test_route_handler_payload_derives_route_metadata_from_handler_label(tmp_path):
    from tldrgraph.visualizer.data import _build_single_node_record
    from tldrgraph.visualizer.source import SourceIndex

    (tmp_path / "routes.ts").write_text('router.post("/create", handler);\n', encoding="utf-8")
    node, *_ = _build_single_node_record(
        {
            "id": "route_handler_endpoint_post_containers_create_backend_src_routes_containers_ts_176",
            "label": "POST /containers/create handler",
            "file": "routes.ts",
            "source_location": "L176",
            "layer_id": "api_workflows",
            "layer": "API Workflows",
            "type": "route_handler",
        },
        {
            "api_workflows": {
                "name": "API Workflows", "color": "#fff", "border": "#fff", "bg": "#000",
            }
        },
        SourceIndex(str(tmp_path)),
    )

    assert node["method"] == "post"
    assert node["route_path"] == "/containers/create"
    assert node["code_start"] == 1


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
    """Workflow Explorer reads only saved feature workflow files."""
    from tldrgraph.visualizer import prepare_visualizer_data
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflows import FEATURE_SCHEMA, WORKFLOW_SCHEMA

    data = prepare_visualizer_data(str(mini_repo.root))
    assert "workflows" in data
    assert data["workflows"] == []
    assert data["workflow_state"]["state"] == "missing_features"

    write_payload(str(mini_repo.tldrgraph_dir / "features.yaml"), {
        "schema": FEATURE_SCHEMA,
        "graph_hash": "test",
        "features": [{
            "id": "submit_case",
            "title": "Submit Case",
            "audience": "user",
            "summary": "Send a case through the project.",
            "status": "generated",
            "workflow_path": ".tldrgraph/workflows/submit_case.yaml",
            "evidence": [{
                "node_id": mini_repo.nid("ui_page"),
                "symbol": mini_repo.label("ui_page"),
                "file": mini_repo.source_file("ui_page"),
                "line": 1,
            }],
        }],
    })
    write_payload(str(mini_repo.tldrgraph_dir / "workflows" / "submit_case.yaml"), {
        "schema": WORKFLOW_SCHEMA,
        "graph_hash": "test",
        "feature_id": "submit_case",
        "title": "Submit Case",
        "summary": "Send a case through the project.",
        "status": "generated",
        "steps": [{
            "number": 1,
            "title": "Open the case page",
            "text": "The user starts from the case page.",
            "evidence": [{
                "node_id": mini_repo.nid("ui_page"),
                "symbol": mini_repo.label("ui_page"),
                "file": mini_repo.source_file("ui_page"),
                "line": 1,
            }],
        }],
    })

    data = prepare_visualizer_data(str(mini_repo.root))
    assert len(data["workflows"]) == 1

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


def test_workflow_explorer_does_not_call_discovery_or_bpmn(monkeypatch, mini_repo):
    """The tab is file-driven, not discovered from routes, blueprints, or BPMN."""
    from tldrgraph.visualizer import prepare_visualizer_data
    import tldrgraph.visualizer.bpmn_data
    import tldrgraph.visualizer.flows_data
    import tldrgraph.visualizer.flows_discover

    def boom(*_args, **_kwargs):
        raise AssertionError("old Workflow Explorer discovery path was called")

    monkeypatch.setattr("tldrgraph.visualizer.flows_discover.discover_workflows", boom)
    monkeypatch.setattr("tldrgraph.visualizer.flows_data.extract_visualizer_workflows", boom)
    monkeypatch.setattr("tldrgraph.visualizer.bpmn_data.attach_bpmn_processes", boom)

    data = prepare_visualizer_data(str(mini_repo.root))

    assert data["workflows"] == []
    assert data["workflow_state"]["state"] == "missing_features"


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


def test_discovered_workflow_prioritizes_llm_http_route_links():
    import networkx as nx
    from tldrgraph.visualizer.flows_discover import discover_workflows

    graph = nx.DiGraph()
    nodes = {
        "page": {
            "label": "OrdersPage()", "file": "src/app/orders/page.tsx", "layer_id": "ui",
            "layer": "UI", "is_test": False,
        },
        "widget": {
            "label": "OrdersWidget()", "file": "src/app/orders/Widget.tsx", "layer_id": "ui",
            "layer": "UI", "is_test": False,
        },
        "handler": {
            "label": "findAll()", "file": "backend/src/orders.controller.ts", "layer_id": "api",
            "layer": "API", "is_test": False,
        },
        "fallback_handler": {
            "label": "findLegacy()", "file": "backend/src/legacy-orders.controller.ts", "layer_id": "api",
            "layer": "API", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("page", "widget", relation="calls")
    graph.add_edge("page", "fallback_handler", relation="http_route_link", confidence=1.0)
    graph.add_edge("page", "handler", relation="llm_http_route_link", confidence=0.86)
    for index in range(8):
        sink = f"fallback_sink_{index}"
        graph.add_node(sink, label=f"fallbackSink{index}()", file=f"backend/src/fallback/{index}.ts")
        graph.add_edge("fallback_handler", sink, relation="calls")

    def format_step(node_id, step_number):
        node = nodes[node_id]
        return {"node_id": node_id, "step_number": step_number, **node}

    workflows = discover_workflows(graph, nodes, format_step, lambda steps: [])

    assert workflows[0]["steps"][1]["node_id"] == "handler"
    assert workflows[0]["steps"][1]["via_relation"] == "llm_http_route_link"


def test_route_linked_frontend_component_can_start_a_feature_flow():
    import networkx as nx
    from tldrgraph.visualizer.flows_discover import discover_workflows, rank_entry_points

    graph = nx.DiGraph()
    nodes = {
        "page": {
            "label": "ProjectPage()", "file": "frontend/src/app/projects/page.tsx",
            "layer_id": "client_experience", "layer": "Client Experience", "is_test": False,
        },
        "hook": {
            "label": "useDeployment()", "file": "frontend/src/app/projects/hooks/useDeployment.ts",
            "layer_id": "client_experience", "layer": "Client Experience", "is_test": False,
        },
        "endpoint": {
            "label": "GET /deployment-config/:id", "file": "backend/src/routes/deployment.ts",
            "layer_id": "api_delivery", "layer": "API Delivery", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("page", "hook", relation="calls")
    graph.add_edge("hook", "endpoint", relation="llm_http_route_link")

    def format_step(node_id, step_number):
        node = nodes[node_id]
        return {"node_id": node_id, "step_number": step_number, **node}

    assert ("hook", "Feature flow") in rank_entry_points(graph, nodes)

    workflows = discover_workflows(graph, nodes, format_step, lambda steps: [])
    hook_flow = next(w for w in workflows if w["root_id"] == "hook")
    assert [step["node_id"] for step in hook_flow["steps"]] == ["hook", "endpoint"]


def test_frontend_component_beats_api_wrapper_as_feature_flow_root():
    import networkx as nx
    from tldrgraph.visualizer.flows_discover import discover_workflows, rank_entry_points

    graph = nx.DiGraph()
    nodes = {
        "prompt": {
            "label": "ProjectPromptInterface()", "file": "frontend/src/app/projects/components/ProjectPromptInterface.tsx",
            "layer_id": "frontend_experience", "layer": "Frontend Experience", "is_test": False,
        },
        "api": {
            "label": "createContainer()", "file": "frontend/src/services/api.ts",
            "layer_id": "client_integrations", "layer": "Client API & Integrations", "is_test": False,
        },
        "endpoint": {
            "label": "POST /containers/create", "file": "backend/src/routes/containers.ts",
            "layer_id": "api_workflows", "layer": "API Workflows", "is_test": False,
        },
        "handler": {
            "label": "POST /containers/create handler", "file": "backend/src/routes/containers.ts",
            "layer_id": "api_workflows", "layer": "API Workflows", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("prompt", "api", relation="calls")
    graph.add_edge("api", "endpoint", relation="calls_endpoint")
    graph.add_edge("endpoint", "handler", relation="handled_by")

    def format_step(node_id, step_number):
        node = nodes[node_id]
        return {"node_id": node_id, "step_number": step_number, **node}

    assert rank_entry_points(graph, nodes)[0] == ("prompt", "Feature flow")

    workflows = discover_workflows(graph, nodes, format_step, lambda steps: [])

    assert workflows[0]["root_id"] == "prompt"
    assert [step["node_id"] for step in workflows[0]["steps"]] == ["prompt", "api", "endpoint", "handler"]


def test_saved_feature_generation_ignores_route_link_relations():
    import networkx as nx
    import yaml
    from tldrgraph.feature_workflows import generate_feature_workflow_files

    graph = nx.DiGraph()
    nodes = {
        "page": {
            "label": "OrdersPage()", "file": "frontend/src/app/orders/page.tsx",
            "layer_id": "ui", "layer": "UI", "is_test": False,
        },
        "handler": {
            "label": "listOrders()", "file": "backend/src/orders.controller.ts",
            "layer_id": "api", "layer": "API", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("page", "handler", relation="http_route_link")
    graph.add_edge("handler", "store", relation="calls")

    import tempfile

    with tempfile.TemporaryDirectory() as root:
        stats = generate_feature_workflow_files(root, graph)
        request = yaml.safe_load(open(stats["request_path"], encoding="utf-8"))

    page = next(item for item in request["candidates"] if item["root"]["node_id"] == "page")
    outgoing = page["evidence_nodes"][0]["outgoing"]
    assert all(item["target"]["node_id"] != "handler" for item in outgoing)
