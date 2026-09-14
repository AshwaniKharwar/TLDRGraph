"""Load saved feature workflow files for the visualizer."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from .cli_enrichment import read_payload
from .feature_workflows import (
    FEATURE_SCHEMA,
    LEGACY_FEATURE_SCHEMA,
    WORKFLOW_SCHEMA,
    features_path,
    relative_workflow_path,
    validate_workflow,
    workflow_path,
)

LEGACY_AREA = {
    "id": "legacy_features",
    "title": "Legacy features",
    "summary": "Features generated with the previous symbol-oriented catalog.",
    "perspective": "technical",
    "order": 0,
}
VALID_PERSPECTIVES = {"product", "technical"}


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
    if (
        not isinstance(data, dict)
        or data.get("schema") not in {FEATURE_SCHEMA, LEGACY_FEATURE_SCHEMA}
    ):
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
    if data.get("schema") == LEGACY_FEATURE_SCHEMA:
        data = _legacy_manifest(data)
    elif not _valid_areas(data.get("areas")):
        return None, "invalid_features"
    return data, "ready"


def _valid_areas(raw: Any) -> bool:
    if not isinstance(raw, list) or not raw:
        return False
    ids = set()
    for area in raw:
        if not isinstance(area, dict) or not str(area.get("id") or ""):
            return False
        if area["id"] in ids or area.get("perspective") not in VALID_PERSPECTIVES:
            return False
        if not isinstance(area.get("order"), int) or not str(area.get("title") or "").strip():
            return False
        ids.add(area["id"])
    return True


def _legacy_manifest(data: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt v1 files in memory while the next init requests v2 regeneration."""
    features = []
    for feature in data.get("features") or []:
        if not isinstance(feature, dict):
            continue
        features.append({
            **feature,
            "area_id": LEGACY_AREA["id"],
            "status": feature.get("status") or "generated",
        })
    return {**data, "areas": [LEGACY_AREA], "features": features, "legacy": True}


def load_saved_feature_workflows(root: str) -> Dict[str, Any]:
    manifest, state = load_feature_manifest(root)
    if not manifest:
        return {"state": state, "workflows": []}

    areas = manifest.get("areas") or []
    area_by_id = {
        str(area.get("id") or ""): area for area in areas if isinstance(area, dict)
    }
    workflows = [
        _visualizer_workflow(
            root, feature, area_by_id.get(str(feature.get("area_id") or ""), LEGACY_AREA)
        )
        for feature in manifest.get("features", []) if isinstance(feature, dict)
    ]
    ready_count = sum(1 for wf in workflows if wf.get("status") == "generated")
    partial_count = sum(1 for wf in workflows if wf.get("status") == "partial")
    return {
        "state": "ready" if workflows else "empty_features",
        "graph_hash": manifest.get("graph_hash"),
        "areas": areas,
        "legacy": bool(manifest.get("legacy")),
        "workflows": workflows,
        "ready_count": ready_count,
        "partial_count": partial_count,
        "pending_count": len(workflows) - ready_count - partial_count,
    }


def _visualizer_workflow(root: str, feature: Dict[str, Any], area: Dict[str, Any]) -> Dict[str, Any]:
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
        "area_id": area.get("id") or "legacy_features",
        "area_title": area.get("title") or "Legacy features",
        "area_summary": area.get("summary") or "",
        "perspective": area.get("perspective") or "technical",
        "area_order": int(area.get("order") or 0),
        "audience": feature.get("audience") or "developer",
        "category": area.get("title") or feature.get("audience") or "Feature",
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
        "missing_coverage": data.get("missing_coverage") or data.get("pending_reason") or "",
        "pending_reason": data.get("missing_coverage") or data.get("pending_reason")
        or ("" if status == "generated" else "Workflow coverage is incomplete."),
        "workflow_path": relative_workflow_path(feature_id),
        "process": _simple_process(feature_id, feature.get("title") or feature_id, steps, status),
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
            "phase": step.get("phase") or "backend",
            "code_start": int(ev.get("code_start") or ev.get("line") or 0),
            "code_end": int(ev.get("code_end") or ev.get("line") or 0),
            "evidence": evidence,
        })
    return steps


def _step_element(feature_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"{feature_id}__step_{step['step_number']}", "kind": "task",
        "label": step.get("display_label") or step.get("symbol"), "detail": step.get("intent") or "",
        "source_symbol": step.get("symbol") or "", "phase": step.get("phase") or "backend",
        "lane": "user" if step.get("phase") == "user_action" else "system",
        "step": step["step_number"], "step_title": step.get("display_label") or step.get("symbol"),
        "file": step.get("file") or "", "line": step.get("code_start") or 0,
        "node_id": step.get("node_id") or None, "minor": False,
    }


def _evidence_elements(feature_id: str, step: Dict[str, Any]) -> List[Dict[str, Any]]:
    elements = []
    for index, evidence in enumerate(step.get("evidence") or [], 1):
        where = str(evidence.get("file") or "")
        line = int(evidence.get("code_start") or evidence.get("line") or 0)
        elements.append({
            "id": f"{feature_id}__step_{step['step_number']}__evidence_{index}", "kind": "task",
            "label": evidence.get("symbol") or "Source evidence", "detail": f"Source evidence: {where}:{line}",
            "source_symbol": evidence.get("symbol") or "", "phase": step.get("phase") or "backend",
            "lane": "system", "step": step["step_number"], "file": where, "line": line,
            "node_id": evidence.get("node_id") or None, "minor": True,
        })
    return elements


def _simple_process(feature_id: str, title: str, steps: List[Dict[str, Any]], status: str) -> Dict[str, Any]:
    if status == "pending":
        return {"lanes": [], "elements": [], "flows": []}
    elements = [_event(f"{feature_id}__start", "start", f"Start: {title}", 0)]
    flows = []
    previous = elements[0]["id"]
    for step in steps:
        element = _step_element(feature_id, step)
        element_id = element["id"]
        elements.append(element)
        flows.append({"source": previous, "target": element_id, "label": "", "kind": "sequence"})
        for evidence in _evidence_elements(feature_id, step):
            elements.append(evidence)
            flows.append({"source": element_id, "target": evidence["id"], "label": "evidence", "kind": "detail"})
        previous = element_id
    label = "Feature workflow complete" if status == "generated" else "Known flow ends here"
    kind = "end" if status == "generated" else "partial"
    elements.append(_event(f"{feature_id}__finish", kind, label, len(steps) + 1))
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
