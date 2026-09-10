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
    """Every distinct feature journey is retained after curated workflows."""
    import networkx as nx
    from tldrgraph.visualizer.flows_data import extract_visualizer_workflows

    graph = nx.DiGraph()
    nodes_by_id = {}
    for index in range(21):
        root = f"root_{index}"
        handler = f"handler_{index}"
        store = f"store_{index}"
        for node_id, label, path in (
            (root, f"OrdersPage{index}()", f"frontend/src/app/orders_{index}/page.tsx"),
            (handler, f"handleOrder{index}()", f"backend/src/orders_{index}.controller.ts"),
            (store, f"saveOrder{index}()", f"src/data/orders_{index}.py"),
        ):
            nodes_by_id[node_id] = {
                "label": label, "file": path,
                "layer_id": "ui" if node_id == root else ("api" if node_id == handler else "data"),
                "layer": "UI" if node_id == root else ("API" if node_id == handler else "Data"),
                "is_test": False,
            }
            graph.add_node(node_id, label=label, file=path)
        graph.add_edge(root, handler, relation="llm_http_route_link")
        graph.add_edge(handler, store, relation="calls")

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


def test_visualizer_keeps_only_complete_frontend_to_backend_flows(monkeypatch):
    import networkx as nx
    from tldrgraph.visualizer.flows_data import extract_visualizer_workflows

    graph = nx.DiGraph()
    nodes = {
        "page": {
            "label": "CasesPage()", "file": "frontend/src/app/cases/page.tsx",
            "layer_id": "client_experience", "layer": "Client Experience", "is_test": False,
        },
        "handler": {
            "label": "createCase()", "file": "backend/src/cases.controller.ts",
            "layer_id": "api_delivery", "layer": "API Delivery", "is_test": False,
        },
        "service": {
            "label": "createCaseRecord()", "file": "backend/src/cases.service.ts",
            "layer_id": "application_services", "layer": "Application Services", "is_test": False,
        },
        "backend_only": {
            "label": "nightlySync()", "file": "backend/src/jobs/sync.ts",
            "layer_id": "async", "layer": "Async", "is_test": False,
        },
        "backend_service": {
            "label": "syncCases()", "file": "backend/src/cases.service.ts",
            "layer_id": "service", "layer": "Service", "is_test": False,
        },
        "backend_endpoint": {
            "label": "GET /cases/sync", "file": "backend/src/routes/cases.ts",
            "layer_id": "api_delivery", "layer": "API Delivery", "is_test": False,
        },
        "ui_only": {
            "label": "HelpPage()", "file": "frontend/src/app/help/page.tsx",
            "layer_id": "ui", "layer": "UI", "is_test": False,
        },
        "component": {
            "label": "HelpContent()", "file": "frontend/src/app/help/HelpContent.tsx",
            "layer_id": "ui", "layer": "UI", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("page", "handler", relation="llm_http_route_link")
    graph.add_edge("handler", "service", relation="calls")
    graph.add_edge("backend_only", "backend_service", relation="calls_endpoint")
    graph.add_edge("backend_service", "backend_endpoint", relation="calls")
    graph.add_edge("ui_only", "component", relation="calls")

    monkeypatch.setattr("tldrgraph.visualizer.flows_data.CURATED_BLUEPRINTS", [])
    workflows = extract_visualizer_workflows(graph, nodes, sources=None)  # type: ignore[arg-type]

    assert [w["root_id"] for w in workflows] == ["page"]
    assert workflows[0]["feature_flow"] is True
    assert workflows[0]["completeness"] == "frontend_to_backend"
    assert workflows[0]["route_link_relation"] == "llm_http_route_link"


def test_visualizer_uses_deterministic_route_link_as_fallback(monkeypatch):
    import networkx as nx
    from tldrgraph.visualizer.flows_data import extract_visualizer_workflows

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

    monkeypatch.setattr("tldrgraph.visualizer.flows_data.CURATED_BLUEPRINTS", [])
    workflows = extract_visualizer_workflows(graph, nodes, sources=None)  # type: ignore[arg-type]

    assert len(workflows) == 1
    assert workflows[0]["route_link_relation"] == "http_route_link"


def test_visualizer_accepts_legacy_endpoint_calls_as_route_fallback(monkeypatch):
    import networkx as nx
    from tldrgraph.visualizer.flows_data import extract_visualizer_workflows

    graph = nx.DiGraph()
    nodes = {
        "page": {
            "label": "BillingPage()", "file": "frontend/src/app/billing/page.tsx",
            "layer_id": "client_experience", "layer": "Client Experience", "is_test": False,
        },
        "endpoint": {
            "label": "GET /billing/pricing", "file": "backend/src/routes/billing.ts",
            "layer_id": "api_delivery", "layer": "API Delivery", "is_test": False,
        },
    }
    graph.add_nodes_from((node_id, data) for node_id, data in nodes.items())
    graph.add_edge("page", "endpoint", relation="calls_endpoint")

    monkeypatch.setattr("tldrgraph.visualizer.flows_data.CURATED_BLUEPRINTS", [])
    workflows = extract_visualizer_workflows(graph, nodes, sources=None)  # type: ignore[arg-type]

    assert len(workflows) == 1
    assert workflows[0]["route_link_relation"] == "calls_endpoint"
