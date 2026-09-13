"""Saved feature workflow generation and loading."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, List, Tuple

import networkx as nx

from .cli_enrichment import read_payload, write_payload
from .layers import layer_id_of

FEATURES_FILENAME = "features.yaml"
WORKFLOWS_DIRNAME = "workflows"
FEATURE_SCHEMA = "codechakra/features@1"
WORKFLOW_SCHEMA = "codechakra/feature-workflow@1"
WORKFLOW_GENERATOR = "feature-workflow-agent-owned@3"
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


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (slug or fallback)[:64]


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


def _walk_feature_steps(graph: nx.DiGraph, root_id: str, max_steps: int = 12) -> List[str]:
    chain = [root_id]
    seen = {root_id}
    current = root_id
    while len(chain) < max_steps:
        ranked: List[Tuple[int, str]] = []
        current_layer = layer_id_of(graph.nodes.get(current, {}))
        for _, target, data in graph.out_edges(current, data=True):
            target = str(target)
            if target in seen or not _is_candidate_node(graph.nodes.get(target, {})):
                continue
            relation = data.get("relation") or "calls"
            if relation in BANNED_WORKFLOW_RELATIONS:
                continue
            if relation in {"contains", "rationale_for", "imports", "imports_from"}:
                continue
            node = graph.nodes[target]
            score = graph.out_degree(target) + 2
            if layer_id_of(node) != current_layer:
                score += 10
            if node.get("file") != graph.nodes[current].get("file"):
                score += 4
            ranked.append((score, target))
        if not ranked:
            break
        ranked.sort(key=lambda item: (-item[0], item[1]))
        current = ranked[0][1]
        chain.append(current)
        seen.add(current)
    return chain


def _fallback_features(graph: nx.DiGraph, current_hash: str) -> Dict[str, Any]:
    features: List[Dict[str, Any]] = []
    used_ids = set()
    for root_id, audience in _candidate_roots(graph):
        node = graph.nodes[root_id]
        base_id = _slug(str(node.get("label") or root_id), f"feature_{len(features) + 1}")
        feature_id = base_id
        counter = 2
        while feature_id in used_ids:
            feature_id = f"{base_id}_{counter}"
            counter += 1
        used_ids.add(feature_id)
        title = _humanize(node.get("display_label") or node.get("label") or root_id)
        features.append({
            "id": feature_id,
            "title": title,
            "audience": audience,
            "summary": _node_summary(node),
            "status": "pending",
            "workflow_path": relative_workflow_path(feature_id),
            "evidence": [_evidence(root_id, node)],
        })
    return {"schema": FEATURE_SCHEMA, "graph_hash": current_hash, "features": features}


def _evidence_node(graph: nx.DiGraph, node_id: str) -> Dict[str, Any]:
    node = graph.nodes[node_id]
    return {
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


def _workflow_evidence(graph: nx.DiGraph, feature: Dict[str, Any]) -> List[Dict[str, Any]]:
    root_id = str((feature.get("evidence") or [{}])[0].get("node_id") or "")
    return [_evidence_node(graph, node_id) for node_id in _walk_feature_steps(graph, root_id) if node_id in graph]


def _pending_workflow(feature: Dict[str, Any], graph: nx.DiGraph, current_hash: str, reason: str) -> Dict[str, Any]:
    return {
        "schema": WORKFLOW_SCHEMA,
        "graph_hash": current_hash,
        "generator": WORKFLOW_GENERATOR,
        "feature_id": feature.get("id"),
        "title": feature.get("title") or _humanize(feature.get("id")),
        "summary": feature.get("summary") or reason,
        "status": "pending",
        "pending_reason": reason,
        "evidence": feature.get("evidence") or [],
        "evidence_nodes": _workflow_evidence(graph, feature),
        "instructions": [
            "The same coding agent running `tldrgraph init` must complete this file.",
            "Open every source file referenced in evidence_nodes before writing steps.",
            "Start at the user's button/menu/form action when present.",
            "Continue through request, backend work, response payload, client handling, and final UI update when proven.",
            "Use only source-backed evidence; leave status pending if a hop is not proven.",
        ],
        "required_step_shape": {"number": 1, "title": "...", "text": "...", "evidence": ["copy evidence objects from evidence_nodes"]},
        "steps": [],
    }


def validate_workflow(workflow: Dict[str, Any]) -> bool:
    if workflow.get("schema") != WORKFLOW_SCHEMA:
        return False
    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        return workflow.get("status") == "pending"
    for step in steps:
        if not isinstance(step, dict):
            return False
        evidence = step.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            return False
        for ev in evidence:
            if not isinstance(ev, dict):
                return False
            if not ev.get("node_id") or not ev.get("file") or not ev.get("symbol"):
                return False
    return True


def generate_feature_workflow_files(
    root: str,
    graph: nx.DiGraph,
    agent_model: Any = None,
    use_agent: bool = True,
) -> Dict[str, Any]:
    """Writes features.yaml and all stale/missing workflow files."""
    root = os.path.abspath(root)
    current_hash = graph_hash(graph)
    manifest = _fallback_features(graph, current_hash)
    reason = "Feature workflow is pending for the current coding agent to complete from source evidence."

    os.makedirs(workflows_dir(root), exist_ok=True)
    generated = 0
    pending = 0
    updated_features = []
    for feature in manifest.get("features", []):
        if not isinstance(feature, dict) or not feature.get("id"):
            continue
        feature_id = _slug(str(feature["id"]), f"feature_{len(updated_features) + 1}")
        feature = {**feature, "id": feature_id, "workflow_path": relative_workflow_path(feature_id)}
        existing = read_payload(workflow_path(root, feature_id))
        stale = (
            not isinstance(existing, dict)
            or existing.get("graph_hash") != current_hash
            or existing.get("generator") != WORKFLOW_GENERATOR
        )
        workflow = existing if isinstance(existing, dict) and not stale else None
        if workflow is None:
            workflow = _pending_workflow(feature, graph, current_hash, reason)
        if not validate_workflow(workflow):
            workflow = _pending_workflow(feature, graph, current_hash, "Saved workflow is invalid or incomplete.")
        write_payload(workflow_path(root, feature_id), workflow)
        status = str(workflow.get("status") or "pending")
        feature["status"] = status
        if status == "generated":
            generated += 1
        else:
            pending += 1
        updated_features.append(feature)

    manifest = {"schema": FEATURE_SCHEMA, "graph_hash": current_hash, "features": updated_features}
    write_payload(features_path(root), manifest)
    return {"features": len(updated_features), "generated": generated, "pending": pending,
            "graph_hash": current_hash, "agent_reason": ""}


def load_feature_manifest(root: str) -> Tuple[Optional[Dict[str, Any]], str]:
    from . import feature_workflow_loader as loader; return loader.load_feature_manifest(root)

def load_saved_feature_workflows(root: str) -> Dict[str, Any]:
    from . import feature_workflow_loader as loader; return loader.load_saved_feature_workflows(root)
