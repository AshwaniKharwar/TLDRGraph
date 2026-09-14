"""Endpoint-aware evidence expansion for saved feature workflows."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

import networkx as nx

from .layers import layer_id_of

BANNED_WORKFLOW_RELATIONS = {"llm_http_route_link", "http_route_link", "calls_endpoint"}
SKIP_DIRS = (".tldrgraph/", "tests/", "test/", "spec/", "__tests__/", "node_modules/", "dist/", "build/", "vendor/", "migrations/")
STRUCTURAL_RELATIONS = {"contains", "rationale_for", "imports", "imports_from"}
ENDPOINT_CONTEXT_RELATIONS = {"calls_endpoint"}
HANDLER_RELATIONS = {"handled_by"}
MAX_EVIDENCE_NODES = 18
MAX_CONTINUATION_STEPS = 5


def endpoint_aware_walk(graph: nx.DiGraph, root_id: str) -> List[str]:
    """Return source nodes that make a feature authoring prompt end-to-end."""
    chain = _walk_without_endpoint_shortcuts(graph, root_id)
    ordered = list(chain)
    seen = set(ordered)

    for node_id in chain:
        for endpoint_id, handler_id in _endpoint_pairs(graph, node_id):
            for candidate in (endpoint_id, handler_id):
                if candidate and candidate not in seen:
                    ordered.append(candidate)
                    seen.add(candidate)
            if handler_id:
                for backend_id in _backend_continuation(graph, handler_id, seen):
                    ordered.append(backend_id)
                    seen.add(backend_id)
        if len(ordered) >= MAX_EVIDENCE_NODES:
            break

    return ordered[:MAX_EVIDENCE_NODES]


def endpoint_context(graph: nx.DiGraph, node_id: str) -> List[Dict[str, Any]]:
    """Describe endpoint bridges without exposing banned relations as evidence."""
    items: List[Dict[str, Any]] = []
    for endpoint_id, handler_id in _endpoint_pairs(graph, node_id):
        endpoint = graph.nodes.get(endpoint_id, {})
        handler = graph.nodes.get(handler_id, {}) if handler_id else {}
        item = {
            "endpoint": _evidence(endpoint_id, endpoint),
            "bridge": "endpoint_context",
        }
        if handler_id and handler:
            item["handler"] = _evidence(handler_id, handler)
        items.append(item)
    return items


def _evidence(node_id: str, node: Dict[str, Any]) -> Dict[str, Any]:
    line = _source_line(node)
    return {
        "node_id": str(node_id),
        "symbol": node.get("label") or str(node_id),
        "file": node.get("file") or "",
        "line": line,
        "code_start": int(node.get("code_start") or line or 0),
        "code_end": int(node.get("code_end") or line or 0),
    }


def _source_line(node: Dict[str, Any]) -> int:
    raw = node.get("source_location") or node.get("code_start") or ""
    if isinstance(raw, int):
        return raw
    import re

    match = re.search(r"\d+", str(raw))
    return int(match.group(0)) if match else 0


def _is_candidate_node(node: Dict[str, Any]) -> bool:
    file_path = str(node.get("file") or "").replace("\\", "/").lower()
    if not file_path or any(part in file_path for part in SKIP_DIRS):
        return False
    if node.get("is_test") or node.get("dead_code_status") in {"not_code", "dead"}:
        return False
    return bool(str(node.get("label") or "").strip())


def _walk_without_endpoint_shortcuts(graph: nx.DiGraph, root_id: str) -> List[str]:
    chain = [root_id]
    seen = {root_id}
    current = root_id
    while len(chain) < MAX_CONTINUATION_STEPS:
        nxt = _best_successor(graph, current, seen)
        if not nxt:
            break
        chain.append(nxt)
        seen.add(nxt)
        current = nxt
    return chain


def _best_successor(graph: nx.DiGraph, current: str, seen: Set[str]) -> str:
    ranked: List[Tuple[int, str]] = []
    current_node = graph.nodes.get(current, {})
    current_layer = layer_id_of(current_node)
    for _, target, data in graph.out_edges(current, data=True):
        target = str(target)
        relation = data.get("relation") or "calls"
        if target in seen or relation in BANNED_WORKFLOW_RELATIONS or relation in STRUCTURAL_RELATIONS:
            continue
        node = graph.nodes.get(target, {})
        if not _is_candidate_node(node):
            continue
        score = graph.out_degree(target) + 2
        if layer_id_of(node) != current_layer:
            score += 10
        if node.get("file") != current_node.get("file"):
            score += 4
        ranked.append((score, target))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][1] if ranked else ""


def _endpoint_pairs(graph: nx.DiGraph, node_id: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for _, endpoint_id, data in graph.out_edges(node_id, data=True):
        if data.get("relation") not in ENDPOINT_CONTEXT_RELATIONS:
            continue
        if endpoint_id not in graph:
            continue
        handler_id = _handler_for_endpoint(graph, str(endpoint_id))
        pairs.append((str(endpoint_id), handler_id))
    return pairs


def _handler_for_endpoint(graph: nx.DiGraph, endpoint_id: str) -> str:
    for _, target, data in graph.out_edges(endpoint_id, data=True):
        if data.get("relation") in HANDLER_RELATIONS and target in graph:
            return str(target)
    return ""


def _backend_continuation(graph: nx.DiGraph, start: str, seen: Set[str]) -> List[str]:
    ordered: List[str] = []
    current = start
    local_seen = set(seen) | {start}
    while len(ordered) < MAX_CONTINUATION_STEPS:
        nxt = _best_successor(graph, current, local_seen)
        if not nxt:
            break
        node = graph.nodes.get(nxt, {})
        if _is_frontend_file(node.get("file")):
            break
        ordered.append(nxt)
        local_seen.add(nxt)
        current = nxt
    return ordered


def _is_frontend_file(file_path: str) -> bool:
    path = str(file_path or "").replace("\\", "/").lower()
    return any(part in path for part in ("frontend/", "/app/", "/pages/", "/components/"))
