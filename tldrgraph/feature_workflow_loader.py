"""Load v4 catalog indexes and feature-owned workflow files for the explorer."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from .feature_workflow_schema import FEATURE_SCHEMA
from .feature_workflow_validation import validate_workflow
from .feature_workflows import features_path, workflow_path
from .payload import read_payload


def load_feature_manifest(root: str, current_hash: str = ""):
    try:
        data = read_payload(features_path(root))
    except Exception as error:
        return None, f"invalid_features: {error}"
    if data is None:
        return None, "missing_features"
    if not isinstance(data, dict) or data.get("schema") != FEATURE_SCHEMA:
        return None, "legacy_features: regenerate v1/v2/v3 artifacts with tldrgraph refresh"
    if not isinstance(data.get("areas"), list) or not isinstance(data.get("features"), list):
        return None, "invalid_features"
    state = "stale_features" if current_hash and data.get("source_hash") != current_hash else "ready"
    return data, state


def _step(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    evidence = item.get("evidence") or []
    first = evidence[0] if evidence else {}
    return {
        "number": int(item.get("number") or index), "phase": item.get("phase") or "backend",
        "title": item.get("title") or first.get("symbol") or f"Step {index}",
        "text": item.get("text") or "", "evidence": evidence,
        "options": [_option(option, item.get("phase") or "backend")
                    for option in item.get("options") or []],
        "file": first.get("file") or "", "symbol": first.get("symbol") or "",
        "code_start": int(first.get("code_start") or first.get("line") or 0),
        "code_end": int(first.get("code_end") or first.get("line") or 0),
    }


def _option(item: Dict[str, Any], default_phase: str) -> Dict[str, Any]:
    evidence = item.get("evidence") or []
    first = evidence[0] if evidence else {}
    return {
        "phase": item.get("phase") or default_phase,
        "title": item.get("title") or first.get("symbol") or "Option",
        "text": item.get("text") or "", "evidence": evidence,
        "file": first.get("file") or "", "symbol": first.get("symbol") or "",
        "code_start": int(first.get("code_start") or first.get("line") or 0),
        "code_end": int(first.get("code_end") or first.get("line") or 0),
    }


def _workflow(root: str, feature: Dict[str, Any], area: Dict[str, Any]) -> Dict[str, Any]:
    path = workflow_path(root, str(feature.get("id") or ""))
    try:
        data = read_payload(path)
    except Exception:
        data = None
    if not isinstance(data, dict) or not validate_workflow(data):
        data = {"status": "pending", "steps": [],
                "missing_coverage": "Workflow file is missing or invalid."}
    steps = [_step(item, index) for index, item in enumerate(data.get("steps") or [], 1)]
    return {
        "id": feature.get("id"), "title": data.get("title") or feature.get("title"),
        "summary": data.get("summary") or feature.get("summary") or "",
        "area_id": area.get("id"), "area_title": area.get("title"),
        "perspective": area.get("perspective", "technical"),
        "audience": feature.get("audience", "developer"),
        "status": data.get("status", "pending"), "steps": steps,
        "evidence": data.get("evidence") or feature.get("evidence") or [],
        "step_count": len(steps),
        "missing_coverage": data.get("missing_coverage") or "",
    }


def _source_files(workflows: List[Dict[str, Any]], inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
    used = {evidence.get("file") for workflow in workflows
            for evidence in workflow.get("evidence") or [] if evidence.get("file")}
    used.update(evidence.get("file") for workflow in workflows for step in workflow["steps"]
                for evidence in step.get("evidence") or [] if evidence.get("file"))
    used.update(evidence.get("file") for workflow in workflows for step in workflow["steps"]
                for option in step.get("options") or []
                for evidence in option.get("evidence") or [] if evidence.get("file"))
    by_path = {item["path"]: item for item in inventory.get("files") or []}
    return [by_path[path] for path in sorted(used) if path in by_path]


def load_saved_feature_workflows(root: str, current_hash: str = "",
                                 inventory: Dict[str, Any] | None = None) -> Dict[str, Any]:
    manifest, state = load_feature_manifest(root, current_hash)
    if not manifest:
        return {"state": state, "error": state, "areas": [], "workflows": [], "source_files": []}
    areas = manifest.get("areas") or []
    by_id = {item.get("id"): item for item in areas if isinstance(item, dict)}
    workflows = [_workflow(root, feature, by_id.get(feature.get("area_id"), {}))
                 for feature in manifest.get("features") or [] if isinstance(feature, dict)]
    inv = inventory or {"files": []}
    return {
        "state": state, "source_hash": manifest.get("source_hash"), "areas": areas,
        "workflows": workflows, "source_files": _source_files(workflows, inv),
        "ready_count": sum(item["status"] == "generated" for item in workflows),
        "partial_count": sum(item["status"] == "partial" for item in workflows),
        "pending_count": sum(item["status"] == "pending" for item in workflows),
    }
