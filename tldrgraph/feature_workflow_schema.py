"""Validation for direct v4 catalog indexes and feature-owned workflows."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from .feature_workflow_validation import WORKFLOW_SCHEMA, validate_workflow

FEATURE_SCHEMA = "tldrgraph/features@4"
CATALOG_GENERATOR = "feature-catalog-agent@4"
WORKFLOW_GENERATOR = "feature-workflow-subagent@4"
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


def validate_catalog_index(current_hash: str, manifest: Any) -> Dict[str, Any]:
    """Validate the main-agent-owned feature index before workers create workflows."""
    if not isinstance(manifest, dict) or manifest.get("schema") != FEATURE_SCHEMA:
        raise ValueError(f"features schema must be {FEATURE_SCHEMA}")
    if manifest.get("source_hash") != current_hash:
        raise ValueError("features source_hash does not match the current repository")
    if manifest.get("generator") != CATALOG_GENERATOR:
        raise ValueError(f"features generator must be {CATALOG_GENERATOR}")
    areas = _normalize_areas(manifest.get("areas"))
    raw_features = manifest.get("features")
    if not isinstance(raw_features, list) or not raw_features:
        raise ValueError("features must contain at least one feature")
    area_ids, used_ids = {item["id"] for item in areas}, set()
    features = []
    for raw in raw_features:
        feature_id, area_id, title, summary, audience = _metadata(raw, area_ids, used_ids)
        feature = {
            "id": feature_id, "area_id": area_id, "title": title, "audience": audience,
            "summary": summary, "workflow_path": f".tldrgraph/workflows/{feature_id}.yaml",
        }
        if raw != feature:
            raise ValueError(f"feature {feature_id} is not in canonical catalog-index form")
        features.append(feature)
    return {"schema": FEATURE_SCHEMA, "source_hash": current_hash,
            "generator": CATALOG_GENERATOR, "areas": areas, "features": features}


def _normalize_workflow(root: str, current_hash: str, feature: Dict[str, Any],
                        source: Any, known_files: set[str]) -> Dict[str, Any]:
    feature_id = feature["id"]
    if not isinstance(source, dict):
        raise ValueError(f"workflow file is missing or invalid for {feature_id}")
    if source.get("schema") != WORKFLOW_SCHEMA:
        raise ValueError(f"workflow {feature_id} has an unsupported schema")
    if source.get("source_hash") != current_hash:
        raise ValueError(f"workflow {feature_id} source_hash does not match the current repository")
    if source.get("generator") != WORKFLOW_GENERATOR:
        raise ValueError(f"workflow {feature_id} generator must be {WORKFLOW_GENERATOR}")
    status = source.get("status")
    if source.get("feature_id") != feature_id or source.get("title") != feature["title"]:
        raise ValueError(f"workflow {feature_id} does not match its feature identity")
    summary = str(source.get("summary") or "").strip()
    missing = str(source.get("missing_coverage") or "").strip()
    if not summary:
        raise ValueError(f"workflow {feature_id} requires a summary")
    if status not in STATUSES or (status in {"partial", "pending"} and not missing):
        raise ValueError(f"workflow {feature_id} has an unsupported status")
    workflow = {
        "schema": WORKFLOW_SCHEMA, "source_hash": current_hash,
        "generator": WORKFLOW_GENERATOR, "feature_id": feature_id,
        "title": feature["title"], "summary": summary, "status": status,
        "missing_coverage": missing,
        "evidence": _evidence_list(root, source.get("evidence"), known_files),
        "steps": _normalize_steps(root, source.get("steps"), status, known_files),
    }
    if not validate_workflow(workflow):
        raise ValueError(f"workflow {feature_id} is incomplete or invalid")
    if source != workflow:
        raise ValueError(f"workflow {feature_id} is not in canonical workflow form")
    return workflow


def validate_catalog_artifacts(root: str, current_hash: str,
                               files: List[Dict[str, Any]], manifest: Any,
                               workflow_payloads: Dict[str, Any]):
    """Validate the catalog index and every independently authored workflow."""
    catalog = validate_catalog_index(current_hash, manifest)
    known_files = {str(item["path"]) for item in files}
    workflows, errors = {}, []
    for feature in catalog["features"]:
        try:
            workflows[feature["id"]] = _normalize_workflow(
                root, current_hash, feature, workflow_payloads.get(feature["id"]), known_files,
            )
        except ValueError as error:
            errors.append(str(error))
    if errors:
        raise ValueError("; ".join(errors))
    return catalog, workflows
