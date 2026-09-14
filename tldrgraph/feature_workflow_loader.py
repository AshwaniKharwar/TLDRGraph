"""Load saved feature workflow files for the visualizer."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from .cli_enrichment import read_payload
from .feature_workflows import (
    FEATURE_SCHEMA,
    WORKFLOW_SCHEMA,
    features_path,
    relative_workflow_path,
    validate_workflow,
    workflow_path,
)


def _humanize(text: str) -> str:
    return str(text or "").replace("_", " ").replace("-", " ").title() or "Project Feature"


def _pending_workflow(feature: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "schema": WORKFLOW_SCHEMA,
        "graph_hash": feature.get("graph_hash", ""),
        "feature_id": feature.get("id"),
        "title": feature.get("title") or _humanize(feature.get("id")),
        "summary": feature.get("summary") or reason,
        "status": "pending",
        "pending_reason": reason,
        "steps": [],
    }


def load_feature_manifest(root: str) -> Tuple[Optional[Dict[str, Any]], str]:
    data = read_payload(features_path(root))
    if data is None:
        return None, "missing_features"
    if not isinstance(data, dict) or data.get("schema") != FEATURE_SCHEMA:
        return None, "invalid_features"
    features = data.get("features")
    if not isinstance(features, list):
        return None, "invalid_features"
    request = read_payload(os.path.join(root, ".tldrgraph", "feature_workflows_request.yaml"))
    if (
        isinstance(request, dict)
        and request.get("graph_hash")
        and request.get("graph_hash") != data.get("graph_hash")
    ):
        return None, "stale_features"
    if not features:
        return data, "empty_features"
    return data, "ready"


def load_saved_feature_workflows(root: str) -> Dict[str, Any]:
    manifest, state = load_feature_manifest(root)
    if not manifest:
        return {"state": state, "workflows": []}

    workflows = [_visualizer_workflow(root, f) for f in manifest.get("features", []) if isinstance(f, dict)]
    ready_count = sum(1 for wf in workflows if wf.get("status") == "generated")
    return {
        "state": "ready" if workflows else "empty_features",
        "graph_hash": manifest.get("graph_hash"),
        "workflows": workflows,
        "ready_count": ready_count,
        "pending_count": len(workflows) - ready_count,
    }


def _visualizer_workflow(root: str, feature: Dict[str, Any]) -> Dict[str, Any]:
    feature_id = str(feature.get("id") or "")
    path = workflow_path(root, feature_id)
    data = read_payload(path)
    if not os.path.isfile(path):
        data = _pending_workflow(feature, "Workflow file has not been generated yet.")
    elif not isinstance(data, dict) or not validate_workflow(data):
        data = _pending_workflow(feature, "Workflow file is invalid or incomplete.")

    status = str(data.get("status") or feature.get("status") or "pending")
    steps = _visualizer_steps(data.get("steps") if isinstance(data, dict) else [])
    return {
        "id": feature_id,
        "title": data.get("title") or feature.get("title") or _humanize(feature_id),
        "category": feature.get("audience") or "Feature",
        "root_node": feature.get("title") or feature_id,
        "root_id": _first_node_id(steps, feature),
        "file": _first_file(steps, feature),
        "layer_id": "feature",
        "layer": "Feature Workflow",
        "summary": data.get("summary") or feature.get("summary") or "",
        "step_count": len(steps),
        "layers_involved": [],
        "node_ids": [s["node_id"] for s in steps if s.get("node_id")],
        "steps": steps,
        "support": [],
        "status": status,
        "pending_reason": data.get("pending_reason") or ("" if status == "generated" else "Workflow is pending."),
        "workflow_path": relative_workflow_path(feature_id),
        "process": _simple_process(feature_id, steps, status),
    }


def _visualizer_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []
    steps = []
    for index, step in enumerate(raw_steps, 1):
        if not isinstance(step, dict):
            continue
        evidence = step.get("evidence") or []
        ev = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
        steps.append({
            "step_number": int(step.get("number") or index),
            "node_id": str(ev.get("node_id") or ""),
            "symbol": ev.get("symbol") or step.get("title") or f"Step {index}",
            "display_label": step.get("title") or ev.get("symbol") or f"Step {index}",
            "file": ev.get("file") or "",
            "layer_id": "feature",
            "layer": "Feature Workflow",
            "type": "feature_step",
            "intent": step.get("text") or "",
            "code_start": int(ev.get("code_start") or ev.get("line") or 0),
            "code_end": int(ev.get("code_end") or ev.get("line") or 0),
            "evidence": evidence,
        })
    return steps


def _simple_process(feature_id: str, steps: List[Dict[str, Any]], status: str) -> Dict[str, Any]:
    elements = [_event(f"{feature_id}__start", "start", "Start the feature", 0)]
    flows = []
    previous = elements[0]["id"]
    for step in steps:
        element_id = f"{feature_id}__step_{step['step_number']}"
        elements.append({
            "id": element_id,
            "kind": "task",
            "label": step.get("intent") or step.get("display_label") or step.get("symbol"),
            "detail": step.get("symbol") or "",
            "lane": "system",
            "step": step["step_number"],
            "step_title": step.get("display_label") or step.get("symbol"),
            "file": step.get("file") or "",
            "line": step.get("code_start") or 0,
            "node_id": step.get("node_id") or None,
            "minor": False,
        })
        flows.append({"source": previous, "target": element_id, "label": "", "kind": "sequence"})
        previous = element_id
    label = "Workflow pending" if status != "generated" else "Feature workflow complete"
    elements.append(_event(f"{feature_id}__finish", "end", label, len(steps) + 1))
    flows.append({"source": previous, "target": elements[-1]["id"], "label": "", "kind": "sequence"})
    return {
        "lanes": [
            {"id": "user", "name": "You", "note": "What a person starts"},
            {"id": "system", "name": "TLDRGraph", "note": "What the source-backed workflow does"},
        ],
        "elements": elements,
        "flows": flows,
    }


def _event(event_id: str, kind: str, label: str, step: int) -> Dict[str, Any]:
    return {
        "id": event_id, "kind": kind, "label": label, "detail": "", "lane": "user" if kind == "start" else "system",
        "step": step, "line": 0, "node_id": None, "minor": False,
    }


def _first_node_id(steps: List[Dict[str, Any]], feature: Dict[str, Any]) -> str:
    if steps and steps[0].get("node_id"):
        return steps[0]["node_id"]
    evidence = feature.get("evidence") or []
    return str((evidence[0] if evidence else {}).get("node_id") or "")


def _first_file(steps: List[Dict[str, Any]], feature: Dict[str, Any]) -> str:
    if steps and steps[0].get("file"):
        return steps[0]["file"]
    evidence = feature.get("evidence") or []
    return str((evidence[0] if evidence else {}).get("file") or "")
