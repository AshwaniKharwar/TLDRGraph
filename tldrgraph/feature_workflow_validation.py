"""Validation rules for graph-free v3 feature workflows."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

WORKFLOW_SCHEMA = "tldrgraph/feature-workflow@4"
ALLOWED_PHASES = {
    "user_action", "frontend", "request", "backend", "persistence",
    "external", "response", "ui_update",
}
FRONTEND_MARKERS = ("frontend/", "/app/", "/pages/", "/components/")
BACKEND_MARKERS = ("backend/", "/backend/", "server/", "/server/", "/routes/")


def validate_workflow(workflow: Dict[str, Any]) -> bool:
    if workflow.get("schema") != WORKFLOW_SCHEMA:
        return False
    status, steps = workflow.get("status"), workflow.get("steps")
    if status not in {"generated", "partial", "pending"} or not isinstance(steps, list):
        return False
    if status == "pending":
        return not steps and _non_empty(workflow.get("missing_coverage"))
    if not steps or not _steps_have_shape(steps):
        return False
    if status == "partial":
        return _non_empty(workflow.get("missing_coverage"))
    return _complete_generated(steps)


def _steps_have_shape(steps: List[Dict[str, Any]]) -> bool:
    for number, step in enumerate(steps, 1):
        if not isinstance(step, dict) or step.get("number") != number:
            return False
        if step.get("phase") not in ALLOWED_PHASES:
            return False
        if not _non_empty(step.get("title")) or not _non_empty(step.get("text")):
            return False
        if not _valid_evidence(step.get("evidence")):
            return False
        if not _valid_options(step.get("options"), step["phase"]):
            return False
    return True


def _valid_options(options: Any, default_phase: str) -> bool:
    if options is None:
        return True
    if not isinstance(options, list) or len(options) < 2:
        return False
    for option in options:
        if not isinstance(option, dict):
            return False
        phase = option.get("phase", default_phase)
        if phase not in ALLOWED_PHASES:
            return False
        if not _non_empty(option.get("title")) or not _non_empty(option.get("text")):
            return False
        if not _valid_evidence(option.get("evidence")):
            return False
    return True


def _valid_evidence(items: Any) -> bool:
    return bool(isinstance(items, list) and items and all(
        isinstance(item, dict) and _non_empty(item.get("file"))
        and _non_empty(item.get("symbol"))
        and isinstance(item.get("code_start"), int)
        and isinstance(item.get("code_end"), int)
        and 1 <= item["code_start"] <= item["code_end"]
        for item in items
    ))


def _complete_generated(steps: List[Dict[str, Any]]) -> bool:
    phases = {step["phase"] for step in steps}
    files = set(_evidence_files(steps))
    if any(_frontend(path) for path in files):
        return (len(steps) >= 4 and bool({"user_action", "frontend"} & phases)
                and "request" in phases and bool({"response", "ui_update"} & phases)
                and (not any(_backend(path) for path in files) or "backend" in phases))
    return len(steps) >= 3 and "backend" in phases and bool({"response", "ui_update"} & phases)


def _evidence_files(steps: List[Dict[str, Any]]) -> Iterable[str]:
    for step in steps:
        for evidence in step.get("evidence") or []:
            yield str(evidence.get("file") or "").replace("\\", "/").lower()
        for option in step.get("options") or []:
            for evidence in option.get("evidence") or []:
                yield str(evidence.get("file") or "").replace("\\", "/").lower()


def _frontend(path: str) -> bool:
    return any(marker in path for marker in FRONTEND_MARKERS)


def _backend(path: str) -> bool:
    return any(marker in path for marker in BACKEND_MARKERS) or path.startswith("api/")


def _non_empty(value: Any) -> bool:
    return bool(str(value or "").strip())
