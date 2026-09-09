"""
LLM-assisted frontend/backend route link inference.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import networkx as nx

from . import extractors
from .layers import LAYER_API, LAYER_UI, layer_id_of

LLM_HTTP_ROUTE_RELATION = "llm_http_route_link"
DETERMINISTIC_ROUTE_RELATIONS = {extractors.HTTP_ROUTE_RELATION, "calls_endpoint"}


def _node_label(graph: nx.DiGraph, node_id: str) -> str:
    return str(graph.nodes[node_id].get("display_label") or graph.nodes[node_id].get("label") or node_id)


def _line(value: Any) -> Optional[int]:
    try:
        line = int(value)
    except (TypeError, ValueError):
        return None
    return line if line > 0 else None


CONFIDENCE_WORDS = {
    "low": 0.35,
    "medium": 0.65,
    "high": 0.9,
}


def _confidence(value: Any) -> Optional[float]:
    word = str(value or "").strip().lower()
    if word in CONFIDENCE_WORDS:
        return CONFIDENCE_WORDS[word]
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return confidence if 0.0 <= confidence <= 1.0 else None


def _line_from_source_location(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    if text[:1].lower() == "l":
        text = text[1:]
    return _line(text.split("-")[0].split(":")[0].strip())


def _frontend_node(data: Mapping[str, Any]) -> bool:
    file_path = str(data.get("file") or "").lower()
    return layer_id_of(data) == LAYER_UI or (
        file_path.endswith((".ts", ".tsx", ".js", ".jsx"))
        and any(part in file_path for part in ("frontend/", "/app/", "/pages/", "/components/"))
    )


def _backend_node(data: Mapping[str, Any]) -> bool:
    file_path = str(data.get("file") or "").lower()
    return layer_id_of(data) == LAYER_API or any(
        part in file_path for part in ("backend/", "/server/", "/api/", "controller", "route")
    )


def _compact_node(graph: nx.DiGraph, node_id: str) -> Dict[str, Any]:
    data = graph.nodes[node_id]
    return {
        "id": node_id,
        "label": _node_label(graph, node_id),
        "file": data.get("file", ""),
        "line": _line_from_source_location(data.get("source_location")),
        "layer": data.get("layer", ""),
        "intent": data.get("intent", ""),
    }


def _collect_candidates(graph: nx.DiGraph, predicate: Any, limit: int) -> List[Dict[str, Any]]:
    nodes = [_compact_node(graph, nid) for nid, data in graph.nodes(data=True) if predicate(data)]
    nodes.sort(key=lambda n: (n.get("file") or "", n.get("line") or 0, n["id"]))
    return nodes[:limit]


def _literal_segments(path: Any) -> Set[str]:
    return {
        segment
        for segment in str(path or "").strip("/").split("/")
        if segment and not segment.startswith(":")
    }


def _paths_compatible(left: Any, right: Any) -> bool:
    left_parts = [part for part in str(left or "").strip("/").split("/") if part]
    right_parts = [part for part in str(right or "").strip("/").split("/") if part]
    if len(left_parts) != len(right_parts):
        return False
    for left_part, right_part in zip(left_parts, right_parts):
        if left_part == right_part or left_part.startswith(":") or right_part.startswith(":"):
            continue
        return False
    return bool(left_parts or right_parts)


def _route_pair_score(call: Mapping[str, Any], route: Mapping[str, Any]) -> int:
    call_path = call.get("path") or call.get("raw_path") or ""
    route_path = route.get("path") or route.get("raw_path") or ""
    if call_path == route_path:
        return 100
    if _paths_compatible(call_path, route_path):
        return 90
    shared = len(_literal_segments(call_path) & _literal_segments(route_path))
    return 10 + shared if shared else 0


def build_route_link_payload(root_dir: str, graph: nx.DiGraph, limit: int = 120) -> Dict[str, Any]:
    """Build the compact source-backed context an agent needs to infer route links."""
    calls = extractors.collect_frontend_calls(root_dir)
    routes = extractors.collect_backend_routes(root_dir)
    index = extractors.NodeIndex([{"id": nid, **data} for nid, data in graph.nodes(data=True)])
    deterministic = {
        (str(u), str(v))
        for u, v, data in graph.edges(data=True)
        if data.get("relation") == extractors.HTTP_ROUTE_RELATION
    }

    frontend_calls: List[Dict[str, Any]] = []
    for call in calls:
        owner = index.owner_of(call["file"], call["line"])
        if owner and graph.has_node(owner) and _frontend_node(graph.nodes[owner]):
            frontend_calls.append({**dict(call), "source": owner, "source_label": _node_label(graph, owner)})

    backend_routes: List[Dict[str, Any]] = []
    for route in routes:
        target = extractors.resolve_route_handler(index, route)
        if not target:
            endpoint_id = extractors.endpoint_node_id(route["method"], route["path"])
            target = endpoint_id if graph.has_node(endpoint_id) else None
        if target and graph.has_node(target):
            backend_routes.append({**dict(route), "target": target, "target_label": _node_label(graph, target)})

    scored_pairs = []
    for call in frontend_calls:
        for route in backend_routes:
            if (
                call["source"] == route["target"]
                or (call["source"], route["target"]) in deterministic
                or graph.has_edge(call["source"], route["target"])
            ):
                continue
            if call.get("method") and route.get("method") and call["method"] != route["method"]:
                continue
            score = _route_pair_score(call, route)
            if score <= 0:
                continue
            scored_pairs.append((score, {
                "source": call["source"],
                "target": route["target"],
                "frontend": {"file": call["file"], "line": call["line"], "path": call.get("raw_path", "")},
                "backend": {"file": route["file"], "line": route["line"], "path": route.get("raw_path", "")},
                "method": call.get("method") or route.get("method"),
                "match_score": score,
            }))
    scored_pairs.sort(key=lambda item: (-item[0], item[1]["source"], item[1]["target"]))
    candidate_pairs = [pair for _, pair in scored_pairs]

    return {
        "schema": "codechakra/llm-route-links-request@1",
        "frontend_calls": frontend_calls[:limit],
        "backend_routes": backend_routes[:limit],
        "frontend_nodes": _collect_candidates(graph, _frontend_node, limit),
        "backend_nodes": _collect_candidates(graph, _backend_node, limit),
        "candidate_pairs": candidate_pairs[:limit],
        "existing_http_links": [
            {"source": src, "target": tgt} for src, tgt in sorted(deterministic)
        ][:limit],
    }


def payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_route_link_prompt(root: str, payload: Mapping[str, Any]) -> str:
    return f"""You are inferring frontend-to-backend API links for this repository.

Open and read the referenced source files before returning links. Only return a
link when source evidence supports that the frontend node calls or depends on
the backend handler/API node. Do not repeat deterministic http_route_link pairs.

Return ONLY a JSON array, no prose and no markdown fence, with this shape:

[
  {{
    "source": "<frontend graph node id>",
    "target": "<backend graph node id>",
    "confidence": 0.0,
    "frontend_evidence": {{"file": "path/from/repo", "line": 1}},
    "backend_evidence": {{"file": "path/from/repo", "line": 1}},
    "explanation": "Short source-backed reason for the link."
  }}
]

Repository root: {root}

Candidate context:
{json.dumps(payload, indent=2, default=str)}
"""


def coerce_link_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("links", "edges", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _evidence(item: Mapping[str, Any], primary: str, prefix: str) -> Optional[Tuple[str, int]]:
    ev = item.get(primary)
    if isinstance(ev, str):
        match = re.search(r"([A-Za-z0-9_./@()[\]{}$:+\\-]+):(\d+)", ev)
        if not match:
            return None
        ev = {"file": match.group(1), "line": match.group(2)}
    elif not isinstance(ev, Mapping):
        ev = {"file": item.get(f"{prefix}_file"), "line": item.get(f"{prefix}_line")}
    file_path = str(ev.get("file") or "").strip()
    line = _line(ev.get("line"))
    if not file_path or line is None:
        return None
    return file_path, line


def apply_route_link_items(graph: nx.DiGraph, items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    applied: List[Tuple[str, str]] = []
    rejected: List[str] = []
    for item in items:
        source = str(item.get("source") or item.get("source_id") or "")
        target = str(item.get("target") or item.get("target_id") or "")
        if not source or not target or source == target:
            rejected.append("missing_or_self_link")
            continue
        if not graph.has_node(source) or not graph.has_node(target):
            rejected.append(f"unknown_node:{source}->{target}")
            continue
        confidence = _confidence(item.get("confidence"))
        if confidence is None:
            rejected.append(f"bad_confidence:{source}->{target}")
            continue
        frontend = _evidence(item, "frontend_evidence", "frontend")
        backend = _evidence(item, "backend_evidence", "backend")
        explanation = str(item.get("explanation") or "").strip()
        if not frontend or not backend or not explanation:
            rejected.append(f"missing_evidence:{source}->{target}")
            continue
        edge_data = {
            "relation": LLM_HTTP_ROUTE_RELATION,
            "confidence": confidence,
            "frontend_file": frontend[0],
            "frontend_line": frontend[1],
            "backend_file": backend[0],
            "backend_line": backend[1],
            "explanation": explanation,
            "inference_source": "agent",
        }
        if graph.has_edge(source, target):
            existing = graph.edges[source, target]
            relation = existing.get("relation")
            if relation not in DETERMINISTIC_ROUTE_RELATIONS:
                rejected.append(f"duplicate:{source}->{target}")
                continue
            edge_data["fallback_relation"] = relation
            existing.update(edge_data)
        else:
            graph.add_edge(source, target, **edge_data)
        applied.append((source, target))

    return {"applied": applied, "rejected": rejected}
