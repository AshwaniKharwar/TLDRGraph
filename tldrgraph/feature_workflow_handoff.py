"""Host-agent handoff for source-backed feature workflow generation."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import yaml

from .cli_enrichment import read_payload, write_payload
from .feature_workflow_schema import ID_RE as FEATURE_ID_RE
from .feature_workflow_schema import RESPONSE_SCHEMA, normalize_response
from .feature_workflow_validation import validate_workflow

REQUEST_FILENAME = "feature_workflows_request.yaml"
RESPONSE_FILENAME = "feature_workflows_response.yaml"
APPLIED_RESPONSE_FILENAME = "feature_workflows_response.applied.yaml"
REQUEST_SCHEMA = "codechakra/feature-workflows-request@2"


def _state_path(root: str, filename: str) -> str:
    return os.path.join(os.path.abspath(root), ".tldrgraph", filename)


def clear_feature_workflow_request(root: str) -> None:
    try:
        os.remove(_state_path(root, REQUEST_FILENAME))
    except FileNotFoundError:
        pass


def feature_workflow_status_lines(root: str, stats: Optional[Dict[str, Any]]) -> List[str]:
    values = stats or {}
    if not int(values.get("pending") or 0):
        return ["Feature catalog and workflow files are complete."]
    request_path = str(values.get("request_path") or _state_path(root, REQUEST_FILENAME))
    lines = [
        "Feature discovery and workflow generation require the active coding agent:",
        f"  1. Read {os.path.relpath(request_path, os.path.abspath(root))}",
        "  2. Delegate the entire request to a source-reading subagent.",
        f"  3. Have the subagent write .tldrgraph/{RESPONSE_FILENAME}.",
        "  4. Run: tldrgraph init",
    ]
    if values.get("agent_reason"):
        lines.insert(1, f"  Previous response rejected: {values['agent_reason']}")
    return lines


def _candidate_payload(graph: nx.DiGraph) -> List[Dict[str, Any]]:
    from .feature_workflows import (
        _candidate_roots,
        _evidence,
        _node_summary,
        _workflow_evidence,
    )

    candidates: List[Dict[str, Any]] = []
    for rank, (node_id, audience) in enumerate(_candidate_roots(graph), 1):
        node = graph.nodes[node_id]
        feature_seed = {"evidence": [_evidence(node_id, node)]}
        candidates.append({
            "rank": rank,
            "audience": audience,
            "summary": _node_summary(node),
            "root": _evidence(node_id, node),
            "label": node.get("label"),
            "intent": node.get("intent"),
            "layer_id": node.get("layer_id"),
            "layer": node.get("layer"),
            "evidence_nodes": _workflow_evidence(graph, feature_seed),
        })
    return candidates


def _response_shape() -> Dict[str, Any]:
    return {
        "schema": RESPONSE_SCHEMA,
        "graph_hash": "copy graph_hash from this request",
        "areas": [{
            "id": "lowercase_snake_case",
            "title": "Repository-specific capability area",
            "summary": "Plain-language description of this area.",
            "perspective": "product | technical",
            "order": 0,
        }],
        "features": [{
            "id": "lowercase_snake_case",
            "area_id": "copy an id from areas",
            "title": "Human capability title",
            "audience": "user | admin | developer | operator",
            "summary": "Source-backed outcome, not a code symbol description.",
            "evidence": ["copy exact node IDs from investigation_leads or .tldrgraph/graph.json"],
            "workflow": {
                "status": "generated | partial | pending",
                "summary": "Complete or known portion of the flow.",
                "missing_coverage": "required for partial or pending; omit for generated",
                "steps": [{
                    "number": 1,
                    "phase": "user_action | frontend | request | backend | persistence | external | response | ui_update",
                    "title": "Short step title",
                    "text": "Plain-language source-backed behavior.",
                    "evidence": ["exact graph node IDs; every displayed step needs evidence"],
                }],
            },
        }],
    }


def write_feature_workflow_request(
    root: str, graph: nx.DiGraph, current_hash: str, error: str = ""
) -> str:
    payload = {
        "schema": REQUEST_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "graph_hash": current_hash,
        "response_file": os.path.join(".tldrgraph", RESPONSE_FILENAME),
        "instructions": [
            "The coding agent running tldrgraph init must delegate this entire request to a source-reading subagent.",
            "Build a repository-wide capability catalog; investigation_leads are starting points, not the feature list.",
            "Inspect README and docs, UI routes/actions, API registration, services, persistence, integrations, deployment/configuration, and administration surfaces.",
            "Infer repository-specific product areas and list concrete capabilities beneath them; put product areas before technical/internal areas.",
            "A feature is a meaningful user, admin, developer, or operator outcome, never merely a class, hook, helper, service, endpoint, or page symbol.",
            "Good: Natural-language project creation. Bad: OpencodeService. Use OpencodeService only as supporting evidence.",
            "Start each workflow at the exact user action or command and follow every proven hop through the final response or UI update.",
            "Use generated only for a complete proven journey, partial for a proven fragment with missing_coverage, and pending when no reliable sequence can be drawn.",
            "List meaningful source-backed capabilities even when their workflow is partial or pending; never fabricate missing steps.",
            "Every feature and displayed step must use exact node IDs from investigation_leads or .tldrgraph/graph.json and be verified against source.",
            "Do not use curated workflows, BPMN, route-link discovery, llm_http_route_link, http_route_link, or calls_endpoint as evidence.",
            f"Write YAML matching response_shape to .tldrgraph/{RESPONSE_FILENAME}, then run tldrgraph init again.",
        ],
        "repository_discovery": {
            "root": ".",
            "graph_file": ".tldrgraph/graph.json",
            "note": "Read the repository and graph directly; do not limit the catalog to the ranked leads below.",
        },
        "banned_evidence_relations": ["llm_http_route_link", "http_route_link", "calls_endpoint"],
        "response_shape": _response_shape(),
        "investigation_leads": _candidate_payload(graph),
    }
    if error:
        payload["previous_response_error"] = error
    return write_payload(_state_path(root, REQUEST_FILENAME), payload)


def normalize_feature_workflow_response(
    graph: nx.DiGraph, current_hash: str, payload: Any
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    return normalize_response(graph, current_hash, payload)


def _atomic_write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=os.path.dirname(path), delete=False)
    try:
        with handle:
            yaml.safe_dump(payload, handle, default_flow_style=False, sort_keys=False)
        os.replace(handle.name, path)
    except Exception:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def apply_feature_workflow_response(
    root: str, graph: nx.DiGraph, current_hash: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    from .feature_workflows import features_path, workflow_path

    response_path = _state_path(root, RESPONSE_FILENAME)
    if not os.path.isfile(response_path):
        return None, ""
    try:
        manifest, workflows = normalize_feature_workflow_response(
            graph, current_hash, read_payload(response_path)
        )
        for feature_id, workflow in workflows.items():
            _atomic_write(workflow_path(root, feature_id), workflow)
        _atomic_write(features_path(root), manifest)
        os.replace(response_path, _state_path(root, APPLIED_RESPONSE_FILENAME))
        try:
            os.remove(_state_path(root, REQUEST_FILENAME))
        except FileNotFoundError:
            pass
        return manifest, ""
    except (OSError, ValueError, TypeError, yaml.YAMLError) as err:
        return None, str(err)


def current_manifest(root: str, current_hash: str) -> Optional[Dict[str, Any]]:
    from .feature_workflows import FEATURE_SCHEMA, WORKFLOW_GENERATOR, features_path, workflow_path

    manifest = read_payload(features_path(root))
    if not isinstance(manifest, dict) or manifest.get("schema") != FEATURE_SCHEMA:
        return None
    areas = manifest.get("areas")
    features = manifest.get("features")
    if (
        manifest.get("graph_hash") != current_hash
        or manifest.get("generator") != "feature-catalog-subagent@2"
        or not isinstance(areas, list) or not areas
        or not isinstance(features, list) or not features
    ):
        return None
    area_ids = {str(area.get("id") or "") for area in areas if isinstance(area, dict)}
    if len(area_ids) != len(areas) or any(
        not FEATURE_ID_RE.fullmatch(str(area.get("id") or ""))
        or area.get("perspective") not in {"product", "technical"}
        or not isinstance(area.get("order"), int)
        for area in areas if isinstance(area, dict)
    ):
        return None
    feature_ids: set[str] = set()
    for feature in features:
        if not isinstance(feature, dict) or feature.get("status") not in {"generated", "partial", "pending"}:
            return None
        feature_id = str(feature.get("id") or "")
        if not FEATURE_ID_RE.fullmatch(feature_id) or feature_id in feature_ids:
            return None
        feature_ids.add(feature_id)
        if feature.get("area_id") not in area_ids:
            return None
        if feature.get("workflow_path") != os.path.join(".tldrgraph", "workflows", f"{feature_id}.yaml"):
            return None
        workflow = read_payload(workflow_path(root, feature_id))
        if (
            not isinstance(workflow, dict)
            or workflow.get("graph_hash") != current_hash
            or workflow.get("generator") != WORKFLOW_GENERATOR
            or workflow.get("feature_id") != feature_id
            or workflow.get("status") != feature.get("status")
            or not validate_workflow(workflow)
        ):
            return None
    return manifest
