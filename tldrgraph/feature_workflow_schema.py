"""Graph-free v3 response normalization for source-backed workflows."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from .feature_workflow_validation import WORKFLOW_SCHEMA, validate_workflow

RESPONSE_SCHEMA = "tldrgraph/feature-workflows-response@3"
FEATURE_SCHEMA = "tldrgraph/features@3"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
PERSPECTIVES = {"product", "technical"}
AUDIENCES = {"user", "admin", "developer", "operator"}
STATUSES = {"generated", "partial", "pending"}


def _safe_file(root: str, raw: Any, known_files: set[str]) -> str:
    value = str(raw or "").replace("\\", "/")
    normalized = os.path.normpath(value).replace("\\", "/")
    if not value or os.path.isabs(value) or normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"evidence file must be repository-relative: {value or '<missing>'}")
    candidate = os.path.realpath(os.path.join(root, normalized))
    try:
        inside_root = os.path.commonpath((os.path.realpath(root), candidate)) == os.path.realpath(root)
    except ValueError:
        inside_root = False
    if normalized not in known_files or not inside_root or not os.path.isfile(candidate):
        raise ValueError(f"evidence file is not in the source inventory: {normalized}")
    return normalized


def _canonical_evidence(root: str, raw: Any, known_files: set[str]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("evidence entries must be objects")
    file_path = _safe_file(root, raw.get("file"), known_files)
    symbol = str(raw.get("symbol") or "").strip()
    if not symbol:
        raise ValueError(f"evidence in {file_path} requires a symbol")
    line = raw.get("line")
    start, end = raw.get("code_start", line), raw.get("code_end", line)
    if end is None:
        end = start
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise ValueError(f"evidence for {symbol} has an invalid line range")
    with open(os.path.join(root, file_path), "r", encoding="utf-8") as handle:
        line_count = sum(1 for _ in handle)
    if end > line_count:
        raise ValueError(f"evidence for {symbol} exceeds {file_path} ({line_count} lines)")
    return {"file": file_path, "symbol": symbol, "line": start,
            "code_start": start, "code_end": end}


def _evidence_list(root: str, raw: Any, known_files: set[str]) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("a non-empty evidence list is required")
    return [_canonical_evidence(root, item, known_files) for item in raw]


def _normalize_areas(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("response must contain at least one feature area")
    areas: List[Dict[str, Any]] = []
    ids, orders = set(), set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each feature area must be an object")
        area_id = str(item.get("id") or "")
        perspective, order = item.get("perspective"), item.get("order")
        if not ID_RE.fullmatch(area_id) or area_id in ids:
            raise ValueError(f"invalid or duplicate area id: {area_id or '<missing>'}")
        if perspective not in PERSPECTIVES or not isinstance(order, int) or order < 0:
            raise ValueError(f"area {area_id} requires perspective and non-negative order")
        if (perspective, order) in orders:
            raise ValueError(f"area {area_id} duplicates an order within {perspective}")
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not title or not summary:
            raise ValueError(f"area {area_id} requires title and summary")
        ids.add(area_id); orders.add((perspective, order))
        areas.append({"id": area_id, "title": title, "summary": summary,
                      "perspective": perspective, "order": order})
    rank = {"product": 0, "technical": 1}
    return sorted(areas, key=lambda item: (rank[item["perspective"]], item["order"], item["id"]))


def _normalize_steps(root: str, raw: Any, status: str,
                     known_files: set[str]) -> List[Dict[str, Any]]:
    if status == "pending":
        if raw not in (None, []):
            raise ValueError("pending workflows cannot contain steps")
        return []
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{status} workflows require steps")
    steps = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"workflow step {index} must be an object")
        step = {
            "number": item.get("number"), "phase": item.get("phase"),
            "title": str(item.get("title") or "").strip(),
            "text": str(item.get("text") or "").strip(),
            "evidence": _evidence_list(root, item.get("evidence"), known_files),
        }
        if item.get("options") is not None:
            step["options"] = _normalize_options(root, item.get("options"), step["phase"], known_files)
        steps.append(step)
    return steps


def _normalize_options(root: str, raw: Any, default_phase: Any,
                       known_files: set[str]) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("workflow step options require at least two branches")
    options = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"workflow option {index} must be an object")
        options.append({
            "phase": item.get("phase") or default_phase,
            "title": str(item.get("title") or "").strip(),
            "text": str(item.get("text") or "").strip(),
            "evidence": _evidence_list(root, item.get("evidence"), known_files),
        })
    return options


def _metadata(raw: Any, area_ids: set[str], used_ids: set[str]) -> Tuple[str, str, str, str, str]:
    if not isinstance(raw, dict):
        raise ValueError("each feature must be an object")
    values = tuple(str(raw.get(key) or "").strip()
                   for key in ("id", "area_id", "title", "summary", "audience"))
    feature_id, area_id, title, summary, audience = values
    if not ID_RE.fullmatch(feature_id) or feature_id in used_ids:
        raise ValueError(f"invalid or duplicate feature id: {feature_id or '<missing>'}")
    if area_id not in area_ids or not title or not summary or audience not in AUDIENCES:
        raise ValueError(f"feature {feature_id} has invalid metadata")
    used_ids.add(feature_id)
    return values


def _normalize_feature(root: str, current_hash: str, raw: Dict[str, Any],
                       area_ids: set[str], used_ids: set[str],
                       known_files: set[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    feature_id, area_id, title, summary, audience = _metadata(raw, area_ids, used_ids)
    evidence = _evidence_list(root, raw.get("evidence"), known_files)
    source = raw.get("workflow")
    if not isinstance(source, dict) or source.get("status") not in STATUSES:
        raise ValueError(f"feature {feature_id} requires a supported workflow")
    status = source["status"]
    missing = str(source.get("missing_coverage") or "").strip()
    if status in {"partial", "pending"} and not missing:
        raise ValueError(f"feature {feature_id} requires missing_coverage")
    workflow = {
        "schema": WORKFLOW_SCHEMA, "source_hash": current_hash,
        "generator": "feature-workflow-subagent@3", "feature_id": feature_id,
        "title": title, "summary": str(source.get("summary") or summary).strip(),
        "status": status, "missing_coverage": missing, "evidence": evidence,
        "steps": _normalize_steps(root, source.get("steps"), status, known_files),
    }
    if not validate_workflow(workflow):
        raise ValueError(f"feature {feature_id} has an incomplete or invalid workflow")
    feature = {
        "id": feature_id, "area_id": area_id, "title": title, "audience": audience,
        "summary": summary, "status": status,
        "workflow_path": f".tldrgraph/workflows/{feature_id}.yaml", "evidence": evidence,
    }
    return feature, workflow


def normalize_response(root: str, current_hash: str,
                       files: List[Dict[str, Any]], payload: Any):
    if not isinstance(payload, dict) or payload.get("schema") != RESPONSE_SCHEMA:
        raise ValueError(f"response schema must be {RESPONSE_SCHEMA}")
    if payload.get("source_hash") != current_hash:
        raise ValueError("response source_hash does not match the current repository")
    areas = _normalize_areas(payload.get("areas"))
    raw_features = payload.get("features")
    if not isinstance(raw_features, list) or not raw_features:
        raise ValueError("response must contain at least one feature")
    known_files = {str(item["path"]) for item in files}
    area_ids, used_ids = {item["id"] for item in areas}, set()
    features, workflows = [], {}
    for raw in raw_features:
        feature, workflow = _normalize_feature(
            root, current_hash, raw, area_ids, used_ids, known_files
        )
        features.append(feature); workflows[feature["id"]] = workflow
    manifest = {
        "schema": FEATURE_SCHEMA, "source_hash": current_hash,
        "generator": "feature-catalog-subagent@3", "areas": areas, "features": features,
    }
    return manifest, workflows
