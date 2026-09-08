import networkx as nx

from tldrgraph import extractors
from tldrgraph.llm_route_inference import (
    LLM_HTTP_ROUTE_RELATION,
    apply_route_link_items,
    build_route_link_payload,
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _graph():
    graph = nx.DiGraph()
    graph.add_node(
        "ui_orders", id="ui_orders", label="OrdersPage()", file="frontend/src/orders/page.tsx",
        source_location="L1", layer_id="ui", layer="Layer 1: UI",
    )
    graph.add_node(
        "ctl_orders", id="ctl_orders", label=".findAll()", file="backend/src/orders.controller.ts",
        source_location="L4", layer_id="api", layer="Layer 2: API",
    )
    graph.add_node(
        "ctl_users", id="ctl_users", label=".findUsers()", file="backend/src/users.controller.ts",
        source_location="L4", layer_id="api", layer="Layer 2: API",
    )
    return graph


def test_payload_excludes_deterministic_duplicates_but_keeps_candidates(tmp_path):
    _write(tmp_path / "frontend/src/orders/page.tsx", "export function OrdersPage() { api.get('/orders') }\n")
    _write(tmp_path / "backend/src/orders.controller.ts", """
@Controller('orders')
export class OrdersController {
  @Get()
  findAll() { return [] }
}
""")
    _write(tmp_path / "backend/src/users.controller.ts", """
@Controller('orders')
export class UsersController {
  @Get('summary')
  findUsers() { return [] }
}
""")
    graph = _graph()
    graph.add_edge("ui_orders", "ctl_orders", relation=extractors.HTTP_ROUTE_RELATION, confidence=1.0)

    payload = build_route_link_payload(str(tmp_path), graph)

    pairs = {(p["source"], p["target"]) for p in payload["candidate_pairs"]}
    assert ("ui_orders", "ctl_orders") not in pairs
    assert ("ui_orders", "ctl_users") in pairs
    assert payload["frontend_nodes"]
    assert payload["backend_nodes"]


def test_payload_ranks_path_matches_above_same_method_noise(tmp_path):
    _write(
        tmp_path / "frontend/src/deployment/page.tsx",
        "export function Deployments() { return api.get(`/api/deployment-config/${id}/deployment-status/${dep}`) }\n",
    )
    _write(
        tmp_path / "backend/src/index.ts",
        'import deploymentRoutes from "./routes/deployment";\n'
        'app.use("/api/deployment-config", deploymentRoutes);\n'
        'app.get("/health", (_req, res) => res.json({ ok: true }));\n',
    )
    _write(
        tmp_path / "backend/src/routes/deployment.ts",
        "const router = express.Router();\n"
        "router.get('/:projectId/deployment-status/:deploymentId', requireAuth, async () => {});\n",
    )
    graph = nx.DiGraph()
    graph.add_node(
        "ui_deployment", id="ui_deployment", label="Deployments()", file="frontend/src/deployment/page.tsx",
        source_location="L1", layer_id="ui", layer="Layer 1: UI",
    )
    graph.add_node(
        "api_health", id="api_health", label="health()", file="backend/src/index.ts",
        source_location="L2", layer_id="api", layer="Layer 2: API",
    )
    graph.add_node(
        "api_deployment", id="api_deployment", label="deploymentStatus()", file="backend/src/routes/deployment.ts",
        source_location="L2", layer_id="api", layer="Layer 2: API",
    )
    endpoint_id = extractors.endpoint_node_id("get", "/deployment-config/:param/deployment-status/:param")
    graph.add_node(
        endpoint_id, id=endpoint_id, label="GET /deployment-config/:param/deployment-status/:param",
        file="backend/src/routes/deployment.ts", source_location="L2", layer_id="api", layer="Layer 2: API",
    )

    payload = build_route_link_payload(str(tmp_path), graph)

    pairs = [(p["target"], p["match_score"]) for p in payload["candidate_pairs"]]
    assert pairs[0] == (endpoint_id, 100)
    assert all(target != "api_health" for target, _ in pairs)


def test_apply_route_link_items_requires_strict_evidence():
    graph = _graph()
    items = [
        {"source": "ui_orders", "target": "ctl_orders", "confidence": 0.7},
        {
            "source": "ui_orders",
            "target": "ctl_users",
            "confidence": 0.8,
            "frontend_evidence": {"file": "frontend/src/orders/page.tsx", "line": 1},
            "backend_evidence": {"file": "backend/src/users.controller.ts", "line": 4},
            "explanation": "Orders UI semantically depends on the users endpoint in the source.",
        },
        {
            "source": "ui_orders",
            "target": "missing",
            "confidence": 0.8,
            "frontend_evidence": {"file": "frontend/src/orders/page.tsx", "line": 1},
            "backend_evidence": {"file": "backend/src/users.controller.ts", "line": 4},
            "explanation": "Bad target.",
        },
        {
            "source": "ui_orders",
            "target": "ctl_orders",
            "confidence": 1.5,
            "frontend_evidence": {"file": "frontend/src/orders/page.tsx", "line": 1},
            "backend_evidence": {"file": "backend/src/orders.controller.ts", "line": 4},
            "explanation": "Bad confidence.",
        },
    ]

    stats = apply_route_link_items(graph, items)

    assert stats["applied"] == [("ui_orders", "ctl_users")]
    assert len(stats["rejected"]) == 3
    edge = graph.edges["ui_orders", "ctl_users"]
    assert edge["relation"] == LLM_HTTP_ROUTE_RELATION
    assert edge["frontend_line"] == 1
    assert edge["backend_file"] == "backend/src/users.controller.ts"


def test_apply_route_link_items_accepts_agent_evidence_strings():
    graph = _graph()
    items = [{
        "source": "ui_orders",
        "target": "ctl_users",
        "confidence": "high",
        "frontend_evidence": "frontend/src/orders/page.tsx:1 fetches GET /orders/summary.",
        "backend_evidence": "backend/src/users.controller.ts:4 registers the endpoint.",
        "explanation": "Orders UI loads data served by the users controller.",
    }]

    stats = apply_route_link_items(graph, items)

    assert stats["rejected"] == []
    assert stats["applied"] == [("ui_orders", "ctl_users")]
    edge = graph.edges["ui_orders", "ctl_users"]
    assert edge["confidence"] == 0.9
    assert edge["frontend_file"] == "frontend/src/orders/page.tsx"
    assert edge["backend_line"] == 4


def test_apply_route_link_items_upgrades_deterministic_endpoint_edges():
    graph = _graph()
    graph.add_edge("ui_orders", "ctl_users", relation="calls_endpoint", confidence=1.0)
    items = [{
        "source": "ui_orders",
        "target": "ctl_users",
        "confidence": "high",
        "frontend_evidence": "frontend/src/orders/page.tsx:1 fetches GET /orders/summary.",
        "backend_evidence": "backend/src/users.controller.ts:4 registers the endpoint.",
        "explanation": "Orders UI loads data served by the users controller.",
    }]

    stats = apply_route_link_items(graph, items)

    assert stats["applied"] == [("ui_orders", "ctl_users")]
    edge = graph.edges["ui_orders", "ctl_users"]
    assert edge["relation"] == LLM_HTTP_ROUTE_RELATION
    assert edge["fallback_relation"] == "calls_endpoint"
