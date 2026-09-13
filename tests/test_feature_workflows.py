"""Feature Workflow Explorer saved-file contract."""

import yaml


def test_feature_workflow_files_are_written_from_source_evidence(loader, mini_repo):
    from tldrgraph.feature_workflows import (
        FEATURES_FILENAME,
        WORKFLOW_SCHEMA,
        generate_feature_workflow_files,
        load_saved_feature_workflows,
    )

    graph = loader.load_or_extract(enrich_llm=False)
    stats = generate_feature_workflow_files(str(mini_repo.root), graph, use_agent=False)

    assert stats["features"] > 0
    features_path = mini_repo.tldrgraph_dir / FEATURES_FILENAME
    assert features_path.exists()

    manifest = yaml.safe_load(features_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "codechakra/features@1"
    assert manifest["features"]

    for feature in manifest["features"]:
        workflow_file = mini_repo.root / feature["workflow_path"]
        assert workflow_file.exists()
        workflow = yaml.safe_load(workflow_file.read_text(encoding="utf-8"))
        assert workflow["schema"] == WORKFLOW_SCHEMA
        assert workflow["feature_id"] == feature["id"]
        assert workflow["status"] == "pending"
        assert workflow["steps"] == []
        assert "current coding agent" in workflow["pending_reason"]
        assert workflow["evidence"]
        assert workflow["evidence_nodes"]
        assert "required_step_shape" in workflow
        assert any("Open every source file" in line for line in workflow["instructions"])

    payload = load_saved_feature_workflows(str(mini_repo.root))
    assert payload["state"] == "ready"
    assert payload["ready_count"] == 0
    assert payload["pending_count"] == len(manifest["features"])
    assert all(wf["process"]["elements"] for wf in payload["workflows"])


def test_feature_workflow_validation_rejects_steps_without_evidence():
    from tldrgraph.feature_workflows import WORKFLOW_SCHEMA, validate_workflow

    assert not validate_workflow({
        "schema": WORKFLOW_SCHEMA,
        "feature_id": "missing_evidence",
        "status": "generated",
        "steps": [{"number": 1, "title": "Guess", "text": "No backing source."}],
    })


def test_feature_workflows_do_not_spawn_agent_cli(monkeypatch, loader, mini_repo):
    from tldrgraph import feature_workflow_agent
    from tldrgraph.feature_workflows import generate_feature_workflow_files, workflow_path

    monkeypatch.setattr(feature_workflow_agent, "generate_feature_manifest", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned feature agent")))
    monkeypatch.setattr(feature_workflow_agent, "generate_feature_workflow", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned feature agent")))

    graph = loader.load_or_extract(enrich_llm=False)
    stats = generate_feature_workflow_files(str(mini_repo.root), graph, use_agent=True)
    workflow = yaml.safe_load(open(workflow_path(str(mini_repo.root), "submitcasebutton"), encoding="utf-8"))

    assert stats["agent_reason"] == ""
    assert workflow["status"] == "pending"
    assert "current coding agent" in workflow["pending_reason"]


def test_missing_workflow_file_becomes_pending_state(mini_repo):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflows import FEATURE_SCHEMA, load_saved_feature_workflows

    write_payload(str(mini_repo.tldrgraph_dir / "features.yaml"), {
        "schema": FEATURE_SCHEMA,
        "graph_hash": "test",
        "features": [{
            "id": "not_generated",
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
    assert payload["workflows"]
    assert payload["ready_count"] == 0
    assert payload["pending_count"] == len(payload["workflows"])


def test_existing_generated_workflow_is_preserved(mini_repo):
    from tldrgraph.feature_workflows import generate_feature_workflow_files, workflow_path
    import yaml

    from tldrgraph.graph_loader import GraphLoader
    graph = GraphLoader(str(mini_repo.root)).load_or_extract(enrich_llm=False)
    stats = generate_feature_workflow_files(str(mini_repo.root), graph, use_agent=False)
    path = workflow_path(str(mini_repo.root), "submitcasebutton")
    workflow = yaml.safe_load(open(path, encoding="utf-8"))
    workflow["status"] = "generated"
    workflow["steps"] = [{
        "number": 1,
        "title": "Use the page",
        "text": "The user starts from the case page.",
        "evidence": [workflow["evidence_nodes"][0]["evidence"]],
    }]
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(workflow, f, sort_keys=False)

    stats = generate_feature_workflow_files(str(mini_repo.root), graph, use_agent=False)
    workflow = yaml.safe_load(open(path, encoding="utf-8"))

    assert stats["generated"] == 1
    assert workflow["status"] == "generated"
    assert workflow["steps"][0]["evidence"][0]["symbol"] == "SubmitCaseButton"


def test_stale_workflows_without_current_generator_are_regenerated_or_pending(mini_repo):
    from tldrgraph.cli_enrichment import write_payload
    from tldrgraph.feature_workflows import generate_feature_workflow_files, graph_hash, workflow_path, WORKFLOW_SCHEMA
    from tldrgraph.graph_loader import GraphLoader

    graph = GraphLoader(str(mini_repo.root)).load_or_extract(enrich_llm=False)
    current_hash = graph_hash(graph)
    write_payload(workflow_path(str(mini_repo.root), "submitcasebutton"), {
        "schema": WORKFLOW_SCHEMA,
        "graph_hash": current_hash,
        "feature_id": "submitcasebutton",
        "title": "Submit Case Button",
        "summary": "Old shallow workflow.",
        "status": "generated",
        "steps": [{"number": 1, "title": "Old", "text": "Old.", "evidence": [{
            "node_id": mini_repo.nid("ui_page"),
            "symbol": mini_repo.label("ui_page"),
            "file": mini_repo.source_file("ui_page"),
            "line": 1,
        }]}],
    })

    generate_feature_workflow_files(str(mini_repo.root), graph, use_agent=False)
    workflow = yaml.safe_load(open(workflow_path(str(mini_repo.root), "submitcasebutton"), encoding="utf-8"))

    assert workflow["status"] == "pending"
    assert workflow["steps"] == []
