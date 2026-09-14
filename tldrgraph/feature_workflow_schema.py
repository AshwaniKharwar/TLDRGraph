"""Version 2 response normalization for source-backed feature catalogs."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import networkx as nx

from .feature_workflow_validation import validate_workflow

RESPONSE_SCHEMA = "codechakra/feature-workflows-response@2"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
PERSPECTIVES = {"product", "technical"}
AUDIENCES = {"user", "admin", "developer", "operator"}
STATUSES = {"generated", "partial", "pending"}


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


def _evidence_list(graph: nx.DiGraph, raw: Any, *, required: bool = True) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or (required and not raw):
        raise ValueError("a non-empty evidence list is required")
    return [_canonical_evidence(graph, item) for item in raw]


def _normalize_areas(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("response must contain at least one feature area")
    areas: List[Dict[str, Any]] = []
    used_ids: set[str] = set()
    used_orders: set[Tuple[str, int]] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each feature area must be an object")
        area_id = str(item.get("id") or "")
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        perspective = str(item.get("perspective") or "").strip()
        order = item.get("order")
        if not ID_RE.fullmatch(area_id) or area_id in used_ids:
            raise ValueError(f"invalid or duplicate area id: {area_id or '<missing>'}")
        if not title or not summary or perspective not in PERSPECTIVES:
            raise ValueError(
                f"area {area_id} requires title, summary, and product/technical perspective"
            )
        if not isinstance(order, int) or order < 0 or (perspective, order) in used_orders:
            raise ValueError(
                f"area {area_id} requires a unique non-negative order within its perspective"
            )
        used_ids.add(area_id)
        used_orders.add((perspective, order))
        areas.append({
            "id": area_id, "title": title, "summary": summary,
            "perspective": perspective, "order": order,
        })
    rank = {"product": 0, "technical": 1}
    return sorted(areas, key=lambda area: (rank[area["perspective"]], area["order"], area["id"]))


def _normalize_steps(graph: nx.DiGraph, raw: Any, status: str) -> List[Dict[str, Any]]:
    if status == "pending":
        if raw not in (None, []):
            raise ValueError("pending workflows cannot contain steps")
        return []
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{status} workflows require at least one step")
    steps: List[Dict[str, Any]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"workflow step {index} must be an object")
        steps.append({
            "number": item.get("number"),
            "phase": item.get("phase"),
            "title": item.get("title"),
            "text": item.get("text"),
            "evidence": _evidence_list(graph, item.get("evidence")),
        })
    return steps


def _normalize_feature(
    graph: nx.DiGraph,
    current_hash: str,
    raw: Any,
    area_ids: set[str],
    used_ids: set[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from .feature_workflows import relative_workflow_path

    feature_id, area_id, title, summary, audience = _feature_metadata(
        raw, area_ids, used_ids
    )
    evidence = _evidence_list(graph, raw.get("evidence"))
    workflow = _workflow_record(graph, current_hash, raw, feature_id, title, summary, evidence)
    feature = {
        "id": feature_id, "area_id": area_id, "title": title, "audience": audience,
        "summary": summary, "status": workflow["status"],
        "workflow_path": relative_workflow_path(feature_id), "evidence": evidence,
    }
    if not validate_workflow(workflow):
        raise ValueError(f"feature {feature_id} has an incomplete or invalid workflow")
    return feature, workflow


def _feature_metadata(
    raw: Any, area_ids: set[str], used_ids: set[str]
) -> Tuple[str, str, str, str, str]:
    if not isinstance(raw, dict):
        raise ValueError("each feature must be an object")
    feature_id = str(raw.get("id") or "")
    area_id = str(raw.get("area_id") or "")
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    audience = str(raw.get("audience") or "").strip()
    if not ID_RE.fullmatch(feature_id) or feature_id in used_ids:
        raise ValueError(f"invalid or duplicate feature id: {feature_id or '<missing>'}")
    if area_id not in area_ids:
        raise ValueError(f"feature {feature_id} references unknown area: {area_id or '<missing>'}")
    if not title or not summary or audience not in AUDIENCES:
        raise ValueError(f"feature {feature_id} requires title, summary, and a supported audience")
    used_ids.add(feature_id)
    return feature_id, area_id, title, summary, audience


def _workflow_record(
    graph: nx.DiGraph,
    current_hash: str,
    raw: Dict[str, Any],
    feature_id: str,
    title: str,
    summary: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from .feature_workflows import WORKFLOW_GENERATOR, WORKFLOW_SCHEMA, _workflow_evidence

    raw_workflow = raw.get("workflow")
    if not isinstance(raw_workflow, dict):
        raise ValueError(f"feature {feature_id} requires a workflow object")
    status = str(raw_workflow.get("status") or "")
    if status not in STATUSES:
        raise ValueError(f"feature {feature_id} has unsupported workflow status: {status or '<missing>'}")
    missing = str(raw_workflow.get("missing_coverage") or "").strip()
    if status in {"partial", "pending"} and not missing:
        raise ValueError(f"feature {feature_id} requires missing_coverage for {status} status")
    steps = _normalize_steps(graph, raw_workflow.get("steps"), status)
    evidence_seed = {"evidence": evidence}
    return {
        "schema": WORKFLOW_SCHEMA, "graph_hash": current_hash, "generator": WORKFLOW_GENERATOR,
        "feature_id": feature_id, "title": title,
        "summary": str(raw_workflow.get("summary") or summary).strip(),
        "status": status, "missing_coverage": missing, "evidence": evidence,
        "evidence_nodes": _workflow_evidence(graph, evidence_seed), "steps": steps,
    }


def normalize_response(
    graph: nx.DiGraph, current_hash: str, payload: Any
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    from .feature_workflows import FEATURE_SCHEMA

    if not isinstance(payload, dict) or payload.get("schema") != RESPONSE_SCHEMA:
        raise ValueError(f"response schema must be {RESPONSE_SCHEMA}")
    if payload.get("graph_hash") != current_hash:
        raise ValueError("response graph_hash does not match the current graph")
    areas = _normalize_areas(payload.get("areas"))
    raw_features = payload.get("features")
    if not isinstance(raw_features, list) or not raw_features:
        raise ValueError("response must contain at least one feature")
    area_ids = {area["id"] for area in areas}
    used_ids: set[str] = set()
    features: List[Dict[str, Any]] = []
    workflows: Dict[str, Dict[str, Any]] = {}
    for raw in raw_features:
        feature, workflow = _normalize_feature(graph, current_hash, raw, area_ids, used_ids)
        features.append(feature)
        workflows[feature["id"]] = workflow
    manifest = {
        "schema": FEATURE_SCHEMA, "graph_hash": current_hash,
        "generator": "feature-catalog-subagent@2", "areas": areas, "features": features,
    }
    return manifest, workflows
