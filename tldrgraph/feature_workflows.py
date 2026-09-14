"""Saved feature workflow generation and loading."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, List, Tuple

import networkx as nx

from .feature_workflow_bridges import endpoint_aware_walk, endpoint_context
from .feature_workflow_validation import validate_workflow
from .layers import layer_id_of

FEATURES_FILENAME = "features.yaml"
WORKFLOWS_DIRNAME = "workflows"
FEATURE_SCHEMA = "codechakra/features@1"
WORKFLOW_SCHEMA = "codechakra/feature-workflow@1"
WORKFLOW_GENERATOR = "feature-workflow-subagent@1"
BANNED_WORKFLOW_RELATIONS = {"llm_http_route_link", "http_route_link", "calls_endpoint"}
SKIP_DIRS = (".tldrgraph/", "tests/", "test/", "spec/", "__tests__/", "node_modules/", "dist/", "build/", "vendor/", "migrations/")


def features_path(root: str) -> str:
    return os.path.join(root, ".tldrgraph", FEATURES_FILENAME)


def workflows_dir(root: str) -> str:
    return os.path.join(root, ".tldrgraph", WORKFLOWS_DIRNAME)


def workflow_path(root: str, feature_id: str) -> str:
    return os.path.join(workflows_dir(root), f"{feature_id}.yaml")


def relative_workflow_path(feature_id: str) -> str:
    return os.path.join(".tldrgraph", WORKFLOWS_DIRNAME, f"{feature_id}.yaml")


def graph_hash(graph: nx.DiGraph) -> str:
    """Stable content-ish hash for deciding when feature files are stale."""
    parts: List[str] = []
    for nid, node in sorted(graph.nodes(data=True), key=lambda item: str(item[0])):
        parts.append("|".join([
            str(nid),
            str(node.get("label") or ""),
            str(node.get("file") or ""),
            str(node.get("source_location") or ""),
            str(node.get("intent") or ""),
        ]))
    for src, dst, data in sorted(graph.edges(data=True), key=lambda item: (str(item[0]), str(item[1]))):
        relation = str(data.get("relation") or "calls")
        if relation in BANNED_WORKFLOW_RELATIONS:
            continue
        parts.append(f"{src}>{dst}:{relation}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _clean_path(path: str) -> str:
    return (path or "").replace("\\", "/")


def _is_candidate_node(node: Dict[str, Any]) -> bool:
    file_path = _clean_path(node.get("file")).lower()
    if not file_path or any(part in file_path for part in SKIP_DIRS):
        return False
    if node.get("is_test"):
        return False
    if node.get("dead_code_status") in {"not_code", "dead"}:
        return False
    label = str(node.get("label") or "")
    return bool(label.strip())


def _source_line(node: Dict[str, Any]) -> int:
    raw = node.get("source_location") or node.get("code_start") or ""
    if isinstance(raw, int):
        return raw
    match = re.search(r"\d+", str(raw))
    return int(match.group(0)) if match else 0


def _evidence(node_id: str, node: Dict[str, Any]) -> Dict[str, Any]:
    line = _source_line(node)
    return {
        "node_id": str(node_id), "symbol": node.get("label") or str(node_id),
        "file": node.get("file") or "", "line": line, "code_start": int(node.get("code_start") or line or 0),
        "code_end": int(node.get("code_end") or line or 0),
    }


def _humanize(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", str(text or ""))
    text = text.split(".")[-1]
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ").strip()
    return " ".join(text.split()).title() or "Project Feature"


def _node_summary(node: Dict[str, Any]) -> str:
    intent = str(node.get("intent") or "").strip()
    if intent and not intent.lower().startswith("the symbol "):
        return intent.split(".")[0].strip() + "."
    return f"Follow how {_humanize(node.get('label'))} works through the project."


def _usable_out_degree(graph: nx.DiGraph, node_id: str) -> int:
    ignored = BANNED_WORKFLOW_RELATIONS | {"contains", "rationale_for", "imports", "imports_from"}
    return sum(1 for _, _, data in graph.out_edges(node_id, data=True) if data.get("relation") not in ignored)


def _root_score(graph: nx.DiGraph, node_id: str, node: Dict[str, Any]) -> Tuple[int, str]:
    path = _clean_path(node.get("file")).lower()
    label = str(node.get("label") or "")
    score = _usable_out_degree(graph, node_id) * 3 - graph.in_degree(node_id)
    audience = "developer"
    if any(part in path for part in ("cli", "commands", ".github", "installer", "agent")):
        score += 8
    if any(part in path for part in ("app/", "pages/", "components/", "controller", "routes", "api")):
        score += 10
        audience = "user"
    if re.search(r"^(main|run|init|scan|serve|start|build|generate)", label, re.IGNORECASE):
        score += 7
    if _usable_out_degree(graph, node_id) < 1:
        score -= 5
    return score, audience


def _candidate_roots(graph: nx.DiGraph, limit: int = 12) -> List[Tuple[str, str]]:
    scored: List[Tuple[int, str, str]] = []
    for node_id, node in graph.nodes(data=True):
        if not _is_candidate_node(node):
            continue
        score, audience = _root_score(graph, str(node_id), node)
        if score <= 0:
            continue
        scored.append((score, str(node_id), audience))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(node_id, audience) for _, node_id, audience in scored[:limit]]


def _evidence_node(graph: nx.DiGraph, node_id: str) -> Dict[str, Any]:
    node = graph.nodes[node_id]
    record = {
        "evidence": _evidence(node_id, node),
        "label": node.get("label"),
        "intent": node.get("intent"),
        "layer": node.get("layer"),
        "layer_id": node.get("layer_id"),
        "outgoing": [
            {
                "relation": d.get("relation"),
                "target": _evidence(str(t), graph.nodes[t]),
                "intent": graph.nodes[t].get("intent"),
                "layer": graph.nodes[t].get("layer"),
            }
            for _, t, d in graph.out_edges(node_id, data=True)
            if (
                t in graph
                and d.get("relation") not in BANNED_WORKFLOW_RELATIONS
                and d.get("relation") not in {"contains", "rationale_for", "imports", "imports_from"}
                and _is_candidate_node(graph.nodes[t])
            )
        ][:24],
    }
    context = endpoint_context(graph, node_id)
    if context:
        record["endpoint_context"] = context
    return record


def _workflow_evidence(graph: nx.DiGraph, feature: Dict[str, Any]) -> List[Dict[str, Any]]:
    root_id = str((feature.get("evidence") or [{}])[0].get("node_id") or "")
    return [_evidence_node(graph, node_id) for node_id in endpoint_aware_walk(graph, root_id) if node_id in graph]


def generate_feature_workflow_files(
    root: str,
    graph: nx.DiGraph,
) -> Dict[str, Any]:
    """Apply a host-subagent response or request one without heuristic output."""
    from .feature_workflow_handoff import (
        apply_feature_workflow_response,
        clear_feature_workflow_request,
        current_manifest,
        write_feature_workflow_request,
    )

    root = os.path.abspath(root)
    current_hash = graph_hash(graph)
    manifest, error = apply_feature_workflow_response(root, graph, current_hash)
    if error:
        request_path = write_feature_workflow_request(root, graph, current_hash, error)
        return {"features": 0, "generated": 0, "pending": 1,
                "graph_hash": current_hash, "agent_reason": error, "request_path": request_path}
    manifest = manifest or current_manifest(root, current_hash)
    if manifest is not None:
        clear_feature_workflow_request(root)
        count = len(manifest.get("features") or [])
        return {"features": count, "generated": count, "pending": 0,
                "graph_hash": current_hash, "agent_reason": "", "request_path": ""}
    request_path = write_feature_workflow_request(root, graph, current_hash, error)
    return {"features": 0, "generated": 0, "pending": 1,
            "graph_hash": current_hash, "agent_reason": error, "request_path": request_path}


def load_feature_manifest(root: str) -> Tuple[Optional[Dict[str, Any]], str]:
    from . import feature_workflow_loader as loader; return loader.load_feature_manifest(root)

def load_saved_feature_workflows(root: str) -> Dict[str, Any]:
    from . import feature_workflow_loader as loader; return loader.load_saved_feature_workflows(root)
