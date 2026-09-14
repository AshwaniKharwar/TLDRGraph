"""Host-agent handoff for source-backed feature workflow generation."""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import yaml

from .cli_enrichment import read_payload, write_payload
from .feature_workflow_validation import validate_workflow

REQUEST_FILENAME = "feature_workflows_request.yaml"
RESPONSE_FILENAME = "feature_workflows_response.yaml"
APPLIED_RESPONSE_FILENAME = "feature_workflows_response.applied.yaml"
REQUEST_SCHEMA = "codechakra/feature-workflows-request@1"
RESPONSE_SCHEMA = "codechakra/feature-workflows-response@1"
FEATURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


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
        return ["Feature workflow files are complete."]
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
        "features": [{
            "id": "lowercase_snake_case",
            "title": "Feature title",
            "audience": "user | developer",
            "summary": "Source-backed feature goal.",
            "evidence": ["copy evidence objects from candidates/evidence_nodes"],
            "workflow": {
                "status": "generated",
                "summary": "Complete end-to-end flow.",
                "steps": [{
                    "number": 1,
                    "phase": "user_action | frontend | request | backend | persistence | response | ui_update",
                    "title": "Short step title",
                    "text": "Plain-language source-backed behavior.",
                    "evidence": ["copy evidence objects from candidates/evidence_nodes"],
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
            "The subagent must inspect the repository source and generate both the feature manifest and every workflow.",
            "Select major end-to-end user-facing and developer-facing goals, not isolated helpers.",
            "Start each workflow at the exact user action or command and follow every proven hop through the final response or UI update.",
            "Every feature and step must copy source evidence from candidates/evidence_nodes; do not guess missing flows.",
            "Do not use curated workflows, BPMN, route-link discovery, llm_http_route_link, http_route_link, or calls_endpoint as evidence.",
            f"Write YAML matching response_shape to .tldrgraph/{RESPONSE_FILENAME}, then run tldrgraph init again.",
        ],
        "banned_evidence_relations": ["llm_http_route_link", "http_route_link", "calls_endpoint"],
        "response_shape": _response_shape(),
        "candidates": _candidate_payload(graph),
    }
    if error:
        payload["previous_response_error"] = error
    return write_payload(_state_path(root, REQUEST_FILENAME), payload)


def _canonical_evidence(graph: nx.DiGraph, raw: Any) -> Dict[str, Any]:
    from .feature_workflows import _evidence

    if not isinstance(raw, dict):
        raise ValueError("evidence entries must be objects")
    node_id = str(raw.get("node_id") or "")
    if not node_id or node_id not in graph:
        raise ValueError(f"unknown evidence node_id: {node_id or '<missing>'}")
    relation = str(raw.get("relation") or "")
    if relation in {"llm_http_route_link", "http_route_link", "calls_endpoint"}:
        raise ValueError(f"banned workflow evidence relation: {relation}")
    evidence = _evidence(node_id, graph.nodes[node_id])
    if relation:
        evidence["relation"] = relation
    return evidence


def _canonical_evidence_list(graph: nx.DiGraph, raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("a non-empty evidence list is required")
    return [_canonical_evidence(graph, item) for item in raw]


def _normalized_steps(graph: nx.DiGraph, raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("workflow steps must be a non-empty list")
    steps: List[Dict[str, Any]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"workflow step {index} must be an object")
        steps.append({
            "number": item.get("number"),
            "phase": item.get("phase"),
            "title": item.get("title"),
            "text": item.get("text"),
            "evidence": _canonical_evidence_list(graph, item.get("evidence")),
        })
    return steps


def _feature_record(graph: nx.DiGraph, raw: Any, used_ids: set[str]) -> Dict[str, Any]:
    from .feature_workflows import relative_workflow_path

    if not isinstance(raw, dict):
        raise ValueError("each feature must be an object")
    feature_id = str(raw.get("id") or "")
    if not FEATURE_ID_RE.fullmatch(feature_id):
        raise ValueError(f"invalid feature id: {feature_id or '<missing>'}")
    if feature_id in used_ids:
        raise ValueError(f"duplicate feature id: {feature_id}")
    used_ids.add(feature_id)
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    audience = str(raw.get("audience") or "").strip()
    if not title or not summary or audience not in {"user", "developer"}:
        raise ValueError(f"feature {feature_id} requires title, summary, and user/developer audience")
    evidence = _canonical_evidence_list(graph, raw.get("evidence"))
    return {
        "id": feature_id,
        "title": title,
        "audience": audience,
        "summary": summary,
        "status": "generated",
        "workflow_path": relative_workflow_path(feature_id),
        "evidence": evidence,
    }


def _normalize_feature(
    graph: nx.DiGraph, current_hash: str, raw: Any, used_ids: set[str]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from .feature_workflows import (
        WORKFLOW_GENERATOR,
        WORKFLOW_SCHEMA,
        _workflow_evidence,
    )

    feature = _feature_record(graph, raw, used_ids)
    feature_id = feature["id"]
    title = feature["title"]
    summary = feature["summary"]
    evidence = feature["evidence"]
    raw_workflow = raw.get("workflow")
    if not isinstance(raw_workflow, dict) or raw_workflow.get("status") != "generated":
        raise ValueError(f"feature {feature_id} requires a generated workflow")
    workflow = {
        "schema": WORKFLOW_SCHEMA,
        "graph_hash": current_hash,
        "generator": WORKFLOW_GENERATOR,
        "feature_id": feature_id,
        "title": title,
        "summary": str(raw_workflow.get("summary") or summary).strip(),
        "status": "generated",
        "evidence": evidence,
        "evidence_nodes": _workflow_evidence(graph, feature),
        "steps": _normalized_steps(graph, raw_workflow.get("steps")),
    }
    if not validate_workflow(workflow):
        raise ValueError(f"feature {feature_id} has an incomplete or invalid workflow")
    return feature, workflow


def normalize_feature_workflow_response(
    graph: nx.DiGraph, current_hash: str, payload: Any
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    from .feature_workflows import FEATURE_SCHEMA

    if not isinstance(payload, dict) or payload.get("schema") != RESPONSE_SCHEMA:
        raise ValueError(f"response schema must be {RESPONSE_SCHEMA}")
    if payload.get("graph_hash") != current_hash:
        raise ValueError("response graph_hash does not match the current graph")
    raw_features = payload.get("features")
    if not isinstance(raw_features, list) or not raw_features:
        raise ValueError("response must contain at least one feature")
    features: List[Dict[str, Any]] = []
    workflows: Dict[str, Dict[str, Any]] = {}
    used_ids: set[str] = set()
    for raw in raw_features:
        feature, workflow = _normalize_feature(graph, current_hash, raw, used_ids)
        features.append(feature)
        workflows[feature["id"]] = workflow
    manifest = {"schema": FEATURE_SCHEMA, "graph_hash": current_hash, "features": features}
    return manifest, workflows


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
    features = manifest.get("features")
    if manifest.get("graph_hash") != current_hash or not isinstance(features, list) or not features:
        return None
    feature_ids: set[str] = set()
    for feature in features:
        if not isinstance(feature, dict) or feature.get("status") != "generated":
            return None
        feature_id = str(feature.get("id") or "")
        if not FEATURE_ID_RE.fullmatch(feature_id) or feature_id in feature_ids:
            return None
        feature_ids.add(feature_id)
        if feature.get("workflow_path") != os.path.join(".tldrgraph", "workflows", f"{feature_id}.yaml"):
            return None
        workflow = read_payload(workflow_path(root, feature_id))
        if (
            not isinstance(workflow, dict)
            or workflow.get("graph_hash") != current_hash
            or workflow.get("generator") != WORKFLOW_GENERATOR
            or workflow.get("feature_id") != feature_id
            or workflow.get("status") != "generated"
            or not validate_workflow(workflow)
        ):
            return None
    return manifest
