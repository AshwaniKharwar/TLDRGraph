"""Feature Workflow Explorer saved-file contract."""

import copy

import pytest
import yaml


def _step(number, phase, key, mini_repo, title=None, text=None, relation=None):
    evidence = {
        "node_id": mini_repo.nid(key),
        "symbol": mini_repo.label(key),
        "file": mini_repo.source_file(key),
        "line": 1,
    }
    if relation:
        evidence["relation"] = relation
    return {
        "number": number,
        "phase": phase,
        "title": title or f"{phase} step",
        "text": text or f"Source-backed {phase} behavior.",
        "evidence": [evidence],
    }


def _write_valid_response(mini_repo, graph, **feature_overrides):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflow_handoff import RESPONSE_FILENAME, RESPONSE_SCHEMA
    from tldrgraph.feature_workflows import graph_hash

    feature = {
        "id": "submit_case",
        "area_id": "case_management",
        "title": "Submit Case",
        "audience": "user",
        "summary": "Submit and persist a case.",
        "evidence": [_step(1, "user_action", "ui_page", mini_repo)["evidence"][0]],
        "workflow": {
            "status": "generated",
            "summary": "Submit a case and render the response.",
            "steps": [
                _step(1, "user_action", "ui_page", mini_repo, "Click submit"),
                _step(2, "frontend", "ui_page", mini_repo, "Build request"),
                _step(3, "request", "ui_page", mini_repo, "Send case"),
                _step(4, "backend", "api_controller", mini_repo, "Receive case"),
                _step(5, "backend", "svc_workflow", mini_repo, "Run workflow"),
                _step(6, "persistence", "data_prisma", mini_repo, "Persist case"),
                _step(7, "response", "api_controller", mini_repo, "Return payload"),
                _step(8, "ui_update", "ui_page", mini_repo, "Render result"),
            ],
        },
    }
    feature.update(feature_overrides)
    return write_payload(str(mini_repo.tldrgraph_dir / RESPONSE_FILENAME), {
        "schema": RESPONSE_SCHEMA,
        "graph_hash": graph_hash(graph),
        "areas": [{
            "id": "case_management",
            "title": "Case management",
            "summary": "Submit and manage pension cases.",
            "perspective": "product",
            "order": 0,
        }],
        "features": [feature],
    })


def test_missing_feature_artifacts_create_host_subagent_request(loader, mini_repo):
    from tldrgraph.feature_workflow_handoff import REQUEST_SCHEMA
    from tldrgraph.feature_workflows import FEATURES_FILENAME, generate_feature_workflow_files

    graph = loader.load_or_extract(enrich_llm=False)
    stats = generate_feature_workflow_files(str(mini_repo.root), graph)

    assert stats["features"] == 0
    assert stats["pending"] == 1
    features_path = mini_repo.tldrgraph_dir / FEATURES_FILENAME
    assert not features_path.exists()
    request = yaml.safe_load(open(stats["request_path"], encoding="utf-8"))
    assert request["schema"] == REQUEST_SCHEMA
    assert request["graph_hash"] == stats["graph_hash"]
    assert request["investigation_leads"]
    assert request["investigation_leads"][0]["root"]["node_id"]
    assert request["investigation_leads"][0]["evidence_nodes"]
    assert "not the feature list" in "\n".join(request["instructions"])
    assert request["repository_discovery"]["graph_file"] == ".tldrgraph/graph.json"
    assert "delegate this entire request" in "\n".join(request["instructions"])


def test_feature_workflow_validation_rejects_steps_without_evidence():
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    assert not validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "missing_evidence",
        "status": "generated",
        "steps": [{"number": 1, "title": "Guess", "text": "No backing source."}],
    })


def test_partial_and_pending_workflow_validation_requires_honest_coverage(mini_repo):
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    partial_step = _step(1, "frontend", "ui_page", mini_repo)
    assert validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "status": "partial",
        "missing_coverage": "The backend handoff is not present in the graph.",
        "steps": [partial_step],
    })
    assert not validate_workflow({
        "schema": WORKFLOW_SCHEMA, "status": "partial", "steps": [partial_step],
    })
    assert validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "status": "pending",
        "missing_coverage": "No reliable sequence can be drawn.",
        "steps": [],
    })
    assert not validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "status": "pending",
        "missing_coverage": "A sequence is not proven.",
        "steps": [partial_step],
    })


def test_v2_catalog_normalizes_areas_and_incomplete_capabilities(loader, mini_repo):
    from tldrgraph.feature_workflow_handoff import RESPONSE_SCHEMA, normalize_feature_workflow_response
    from tldrgraph.feature_workflows import graph_hash

    graph = loader.load_or_extract(enrich_llm=False)
    evidence = _step(1, "frontend", "ui_page", mini_repo)["evidence"]
    payload = {
        "schema": RESPONSE_SCHEMA,
        "graph_hash": graph_hash(graph),
        "areas": [
            {"id": "operations", "title": "Operations", "summary": "Internal operation.",
             "perspective": "technical", "order": 0},
            {"id": "case_management", "title": "Case management", "summary": "Manage cases.",
             "perspective": "product", "order": 0},
        ],
        "features": [
            {"id": "review_case", "area_id": "case_management", "title": "Review a case",
             "audience": "admin", "summary": "Review an existing case.", "evidence": evidence,
             "workflow": {"status": "partial", "summary": "Open the review page.",
                          "missing_coverage": "The save response is not proven.",
                          "steps": [_step(1, "frontend", "ui_page", mini_repo)]}},
            {"id": "operate_pipeline", "area_id": "operations", "title": "Operate the pipeline",
             "audience": "operator", "summary": "Operate the internal pipeline.", "evidence": evidence,
             "workflow": {"status": "pending", "summary": "Pipeline operation.",
                          "missing_coverage": "No reliable sequence can be drawn.", "steps": []}},
        ],
    }

    manifest, workflows = normalize_feature_workflow_response(graph, graph_hash(graph), payload)

    assert [area["id"] for area in manifest["areas"]] == ["case_management", "operations"]
    assert [feature["status"] for feature in manifest["features"]] == ["partial", "pending"]
    assert workflows["review_case"]["missing_coverage"]
    assert workflows["operate_pipeline"]["steps"] == []


def test_v2_catalog_rejects_unknown_feature_area(loader, mini_repo):
    from tldrgraph.feature_workflow_handoff import RESPONSE_SCHEMA, normalize_feature_workflow_response
    from tldrgraph.feature_workflows import graph_hash

    graph = loader.load_or_extract(enrich_llm=False)
    payload = {
        "schema": RESPONSE_SCHEMA, "graph_hash": graph_hash(graph),
        "areas": [{"id": "known", "title": "Known", "summary": "Known area.",
                   "perspective": "product", "order": 0}],
        "features": [{"id": "orphan", "area_id": "missing", "title": "Orphan feature",
                      "audience": "user", "summary": "Has no valid area.",
                      "evidence": _step(1, "frontend", "ui_page", mini_repo)["evidence"],
                      "workflow": {"status": "pending", "summary": "Unknown.",
                                   "missing_coverage": "No flow.", "steps": []}}],
    }

    with pytest.raises(ValueError, match="unknown area"):
        normalize_feature_workflow_response(graph, graph_hash(graph), payload)


def test_v1_manifest_loads_in_legacy_area(mini_repo):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflows import LEGACY_FEATURE_SCHEMA, load_saved_feature_workflows

    write_payload(str(mini_repo.tldrgraph_dir / "features.yaml"), {
        "schema": LEGACY_FEATURE_SCHEMA, "graph_hash": "old",
        "features": [{"id": "old_service", "title": "Old Service", "audience": "developer",
                      "summary": "A legacy symbol-oriented feature.", "status": "pending",
                      "workflow_path": ".tldrgraph/workflows/old_service.yaml", "evidence": []}],
    })

    payload = load_saved_feature_workflows(str(mini_repo.root))

    assert payload["state"] == "ready"
    assert payload["legacy"] is True
    assert payload["areas"][0]["id"] == "legacy_features"
    assert payload["workflows"][0]["area_title"] == "Legacy features"


def test_v1_manifest_is_not_current_for_generation(loader, mini_repo):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflow_handoff import REQUEST_SCHEMA
    from tldrgraph.feature_workflows import LEGACY_FEATURE_SCHEMA, generate_feature_workflow_files, graph_hash

    graph = loader.load_or_extract(enrich_llm=False)
    write_payload(str(mini_repo.tldrgraph_dir / "features.yaml"), {
        "schema": LEGACY_FEATURE_SCHEMA, "graph_hash": graph_hash(graph),
        "features": [{"id": "old", "title": "Old", "status": "generated"}],
    })

    stats = generate_feature_workflow_files(str(mini_repo.root), graph)
    request = yaml.safe_load(open(stats["request_path"], encoding="utf-8"))

    assert stats["pending"] == 1
    assert request["schema"] == REQUEST_SCHEMA


def test_user_workflow_validation_rejects_shallow_generated_steps(mini_repo):
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    assert not validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "submit_case",
        "status": "generated",
        "evidence": [_step(1, "frontend", "ui_page", mini_repo)["evidence"][0]],
        "steps": [
            _step(1, "frontend", "ui_page", mini_repo),
            _step(2, "request", "ui_page", mini_repo),
            _step(3, "ui_update", "ui_page", mini_repo),
        ],
    })


def test_user_workflow_requires_backend_step_when_backend_evidence_exists(mini_repo):
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    workflow = {
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "submit_case",
        "status": "generated",
        "evidence": [_step(1, "frontend", "ui_page", mini_repo)["evidence"][0]],
        "evidence_nodes": [{
            "evidence": _step(1, "frontend", "ui_page", mini_repo)["evidence"][0],
            "outgoing": [{
                "relation": "calls",
                "target": _step(2, "backend", "api_controller", mini_repo)["evidence"][0],
            }],
        }],
        "steps": [
            _step(1, "user_action", "ui_page", mini_repo),
            _step(2, "frontend", "ui_page", mini_repo),
            _step(3, "request", "ui_page", mini_repo),
            _step(4, "ui_update", "ui_page", mini_repo),
        ],
    }

    assert not validate_workflow(workflow)


def test_backend_only_generated_workflow_can_pass(mini_repo):
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    assert validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "case_workflow",
        "status": "generated",
        "evidence": [_step(1, "backend", "svc_workflow", mini_repo)["evidence"][0]],
        "steps": [
            _step(1, "backend", "api_controller", mini_repo, "Receive command"),
            _step(2, "backend", "svc_workflow", mini_repo, "Run service work"),
            _step(3, "persistence", "data_prisma", mini_repo, "Persist case"),
            _step(4, "response", "api_controller", mini_repo, "Return result"),
        ],
    })


def test_generated_workflow_with_scaffold_markers_is_incomplete(mini_repo):
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    assert not validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "submit_case",
        "status": "generated",
        "pending_reason": "Feature workflow is pending for the current coding agent.",
        "evidence": [_step(1, "frontend", "ui_page", mini_repo)["evidence"][0]],
        "steps": [
            _step(1, "user_action", "ui_page", mini_repo),
            _step(2, "frontend", "ui_page", mini_repo),
            _step(3, "request", "ui_page", mini_repo),
            _step(4, "backend", "api_controller", mini_repo),
            _step(5, "response", "api_controller", mini_repo),
            _step(6, "ui_update", "ui_page", mini_repo),
        ],
    })


def test_route_link_relations_are_not_valid_workflow_evidence(mini_repo):
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    workflow = {
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "submit_case",
        "status": "generated",
        "evidence": [_step(1, "frontend", "ui_page", mini_repo)["evidence"][0]],
        "steps": [
            _step(1, "user_action", "ui_page", mini_repo),
            _step(2, "frontend", "ui_page", mini_repo),
            _step(3, "request", "ui_page", mini_repo, relation="http_route_link"),
            _step(4, "backend", "api_controller", mini_repo),
            _step(5, "response", "api_controller", mini_repo),
            _step(6, "ui_update", "ui_page", mini_repo),
        ],
    }

    assert not validate_workflow(workflow)


def test_feature_request_evidence_crosses_endpoint_context(tmp_path):
    import networkx as nx
    from tldrgraph.feature_workflows import generate_feature_workflow_files

    graph = nx.DiGraph()
    graph.add_nodes_from([
        ("page", {
            "label": "ChatPanel()", "file": "frontend/src/app/projects/page.tsx",
            "layer_id": "ui", "layer": "UI", "source_location": "L10",
        }),
        ("api", {
            "label": "streamBuildProgress()", "file": "frontend/src/services/api.ts",
            "layer_id": "ui", "layer": "UI", "source_location": "L40",
        }),
        ("endpoint", {
            "label": "POST /containers/:id/stream", "file": "backend/src/routes/containers.ts",
            "layer_id": "api", "layer": "API", "source_location": "L80",
        }),
        ("handler", {
            "label": "streamContainer()", "file": "backend/src/routes/containers.ts",
            "layer_id": "api", "layer": "API", "source_location": "L90",
        }),
        ("service", {
            "label": "streamMessage()", "file": "backend/src/services/opencode/OpencodeService.ts",
            "layer_id": "service", "layer": "Service", "source_location": "L120",
        }),
        ("checkpoint", {
            "label": "createPromptRollbackCheckpoint()",
            "file": "backend/src/services/checkpoints.ts",
            "layer_id": "data", "layer": "Data", "source_location": "L150",
        }),
    ])
    graph.add_edge("page", "api", relation="calls")
    graph.add_edge("api", "endpoint", relation="calls_endpoint")
    graph.add_edge("endpoint", "handler", relation="handled_by")
    graph.add_edge("handler", "service", relation="calls")
    graph.add_edge("service", "checkpoint", relation="calls")

    stats = generate_feature_workflow_files(str(tmp_path), graph)
    request = yaml.safe_load(open(stats["request_path"], encoding="utf-8"))
    candidate = next(item for item in request["investigation_leads"] if item["root"]["node_id"] == "page")
    node_ids = [node["evidence"]["node_id"] for node in candidate["evidence_nodes"]]

    assert node_ids[:6] == ["page", "api", "endpoint", "handler", "service", "checkpoint"]
    api_node = next(node for node in candidate["evidence_nodes"] if node["evidence"]["node_id"] == "api")
    assert api_node["endpoint_context"][0]["endpoint"]["node_id"] == "endpoint"
    assert api_node["endpoint_context"][0]["handler"]["node_id"] == "handler"
    assert all(
        outgoing["relation"] not in {"llm_http_route_link", "http_route_link", "calls_endpoint"}
        for node in candidate["evidence_nodes"]
        for outgoing in node.get("outgoing", [])
    )


def test_feature_workflows_do_not_spawn_agent_cli(monkeypatch, loader, mini_repo):
    from tldrgraph import agent_runner
    from tldrgraph.feature_workflows import generate_feature_workflow_files

    monkeypatch.setattr(agent_runner, "find_agent_cli", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned feature agent")))

    graph = loader.load_or_extract(enrich_llm=False)
    stats = generate_feature_workflow_files(str(mini_repo.root), graph)

    assert stats["agent_reason"] == ""
    assert stats["pending"] == 1
    assert stats["request_path"]


def test_missing_workflow_file_becomes_pending_state(mini_repo):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflows import FEATURE_SCHEMA, load_saved_feature_workflows

    write_payload(str(mini_repo.tldrgraph_dir / "features.yaml"), {
        "schema": FEATURE_SCHEMA,
        "graph_hash": "test",
        "areas": [{
            "id": "operations", "title": "Operations", "summary": "Operational capabilities.",
            "perspective": "technical", "order": 0,
        }],
        "features": [{
            "id": "not_generated",
            "area_id": "operations",
            "title": "Not Generated",
            "audience": "developer",
            "summary": "A feature without a workflow file.",
            "status": "pending",
            "workflow_path": ".tldrgraph/workflows/not_generated.yaml",
            "evidence": [{
                "node_id": mini_repo.nid("devops_ci"),
                "symbol": mini_repo.label("devops_ci"),
                "file": mini_repo.source_file("devops_ci"),
                "line": 1,
            }],
        }],
    })

    payload = load_saved_feature_workflows(str(mini_repo.root))

    assert payload["state"] == "ready"
    assert payload["ready_count"] == 0
    assert payload["pending_count"] == 1
    assert payload["workflows"][0]["status"] == "pending"
    assert "not been generated" in payload["workflows"][0]["pending_reason"]


def test_init_pipeline_writes_all_feature_workflows(monkeypatch, mini_repo):
    from tldrgraph.cli_pipeline import init_pipeline
    from tldrgraph.feature_workflow_handoff import REQUEST_FILENAME
    from tldrgraph.feature_workflows import load_saved_feature_workflows

    monkeypatch.setattr("tldrgraph.graph_loader.GraphLoader._run_graphify", lambda self: None)

    status = init_pipeline(
        str(mini_repo.root),
        assume_yes=True,
        batch_size=200,
        max_nodes=0,
        rebuild=False,
        relayer=False,
        agent_cli=False,
        agent_model=None,
        embeddings="off",
        llm_links=False,
        as_json=True,
    )

    payload = load_saved_feature_workflows(str(mini_repo.root))
    assert status == "needs_feature_workflows"
    assert payload["state"] == "missing_features"
    assert not payload["workflows"]
    assert (mini_repo.tldrgraph_dir / REQUEST_FILENAME).exists()


def test_existing_generated_workflow_is_preserved(mini_repo):
    from tldrgraph.feature_workflow_handoff import APPLIED_RESPONSE_FILENAME, RESPONSE_FILENAME
    from tldrgraph.feature_workflows import generate_feature_workflow_files, workflow_path

    from tldrgraph.graph_loader import GraphLoader
    graph = GraphLoader(str(mini_repo.root)).load_or_extract(enrich_llm=False)
    _write_valid_response(mini_repo, graph)
    stats = generate_feature_workflow_files(str(mini_repo.root), graph)
    path = workflow_path(str(mini_repo.root), "submit_case")
    original = yaml.safe_load(open(path, encoding="utf-8"))
    assert (mini_repo.tldrgraph_dir / APPLIED_RESPONSE_FILENAME).exists()
    assert not (mini_repo.tldrgraph_dir / RESPONSE_FILENAME).exists()

    stats = generate_feature_workflow_files(str(mini_repo.root), graph)
    workflow = yaml.safe_load(open(path, encoding="utf-8"))

    assert stats["generated"] == 1
    assert workflow == original
    assert workflow["steps"][0]["evidence"][0]["symbol"] == "SubmitCaseButton"


@pytest.mark.parametrize("invalid_case", [
    "malformed", "wrong_hash", "duplicate_id", "unknown_evidence", "shallow_workflow",
    "banned_relation",
])
def test_invalid_subagent_response_never_overwrites_valid_artifacts(mini_repo, invalid_case):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflow_handoff import REQUEST_FILENAME, RESPONSE_FILENAME
    from tldrgraph.feature_workflows import features_path, generate_feature_workflow_files
    from tldrgraph.graph_loader import GraphLoader

    graph = GraphLoader(str(mini_repo.root)).load_or_extract(enrich_llm=False)
    _write_valid_response(mini_repo, graph)
    generate_feature_workflow_files(str(mini_repo.root), graph)
    original = open(features_path(str(mini_repo.root)), encoding="utf-8").read()

    _write_valid_response(mini_repo, graph)
    response_path = mini_repo.tldrgraph_dir / RESPONSE_FILENAME
    if invalid_case == "malformed":
        response_path.write_text("features: [", encoding="utf-8")
    else:
        response = yaml.safe_load(response_path.read_text(encoding="utf-8"))
        feature = response["features"][0]
        if invalid_case == "wrong_hash":
            response["graph_hash"] = "stale"
        elif invalid_case == "duplicate_id":
            response["features"].append(copy.deepcopy(feature))
        elif invalid_case == "unknown_evidence":
            feature["evidence"][0]["node_id"] = "missing-node"
        elif invalid_case == "shallow_workflow":
            feature["workflow"]["steps"] = feature["workflow"]["steps"][:2]
        else:
            feature["workflow"]["steps"][0]["evidence"][0]["relation"] = "http_route_link"
        write_payload(str(response_path), response)

    stats = generate_feature_workflow_files(str(mini_repo.root), graph)
    request = yaml.safe_load((mini_repo.tldrgraph_dir / REQUEST_FILENAME).read_text(encoding="utf-8"))

    assert stats["pending"] == 1
    assert stats["agent_reason"]
    assert request["previous_response_error"] == stats["agent_reason"]
    assert open(features_path(str(mini_repo.root)), encoding="utf-8").read() == original


def test_stale_generated_workflows_are_preserved_but_not_exposed(mini_repo):
    from tldrgraph.feature_workflows import generate_feature_workflow_files, load_saved_feature_workflows, workflow_path
    from tldrgraph.graph_loader import GraphLoader

    graph = GraphLoader(str(mini_repo.root)).load_or_extract(enrich_llm=False)
    _write_valid_response(mini_repo, graph)
    generate_feature_workflow_files(str(mini_repo.root), graph)
    path = workflow_path(str(mini_repo.root), "submit_case")
    original = open(path, encoding="utf-8").read()

    graph.nodes[mini_repo.nid("ui_page")]["intent"] = "Changed source-backed intent."
    stats = generate_feature_workflow_files(str(mini_repo.root), graph)
    payload = load_saved_feature_workflows(str(mini_repo.root))

    assert stats["pending"] == 1
    assert open(path, encoding="utf-8").read() == original
    assert payload["state"] == "stale_features"
    assert payload["workflows"] == []
