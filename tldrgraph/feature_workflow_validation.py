"""Validation for saved Feature Workflow Explorer files."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


WORKFLOW_SCHEMA = "codechakra/feature-workflow@1"
BANNED_WORKFLOW_RELATIONS = {"llm_http_route_link", "http_route_link", "calls_endpoint"}
FRONTEND_MARKERS = ("frontend/", "/app/", "/pages/", "/components/")
BACKEND_MARKERS = ("backend/", "/backend/", "server/", "/server/", "/routes/", "controller")
PHASE_ALIASES = {
    "ui": "ui_update",
    "client": "frontend",
    "server": "backend",
    "database": "persistence",
    "result": "response",
}
SCAFFOLD_MARKERS = (
    "pending_reason",
    "instructions",
    "required_step_shape",
)


def validate_workflow(workflow: Dict[str, Any]) -> bool:
    if workflow.get("schema") != WORKFLOW_SCHEMA:
        return False
    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        return workflow.get("status") == "pending"
    if not _steps_have_required_shape(steps):
        return False
    if _uses_banned_relation(steps):
        return False
    if workflow.get("status") != "generated":
        return True
    return _validate_generated_workflow(workflow, steps)


def _validate_generated_workflow(workflow: Dict[str, Any], steps: List[Dict[str, Any]]) -> bool:
    if any(workflow.get(marker) for marker in SCAFFOLD_MARKERS):
        return False
    phases = {_normalize_phase(step.get("phase")) for step in steps}
    phases.discard("")
    if not phases:
        return False
    if _is_user_facing_workflow(workflow):
        if len(steps) < 4:
            return False
        if not ({"user_action", "frontend"} & phases and "request" in phases):
            return False
        if not ({"response", "ui_update"} & phases):
            return False
        if (
            "request" in phases
            and not workflow.get("external_only_request")
            and not _steps_include_backend_evidence(steps)
        ):
            return False
        if _has_backend_evidence(workflow) and not _steps_include_backend_evidence(steps):
            return False
    else:
        if len(steps) < 3:
            return False
        if "backend" not in phases:
            return False
        if not ({"response", "ui_update"} & phases):
            return False
    return True


def _steps_have_required_shape(steps: List[Dict[str, Any]]) -> bool:
    for step in steps:
        if not isinstance(step, dict):
            return False
        if not isinstance(step.get("number"), int):
            return False
        if not _non_empty(step.get("phase")):
            return False
        if not _non_empty(step.get("title")) or not _non_empty(step.get("text")):
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


def _uses_banned_relation(steps: List[Dict[str, Any]]) -> bool:
    for step in steps:
        for ev in step.get("evidence") or []:
            relation = str(ev.get("relation") or "")
            if relation in BANNED_WORKFLOW_RELATIONS:
                return True
    return False


def _is_user_facing_workflow(workflow: Dict[str, Any]) -> bool:
    files = _workflow_evidence_files(workflow)
    return any(_is_frontend_file(file_path) for file_path in files)


def _has_backend_evidence(workflow: Dict[str, Any]) -> bool:
    files = _workflow_evidence_files(workflow)
    return any(_is_backend_file(file_path) for file_path in files)


def _steps_include_backend_evidence(steps: List[Dict[str, Any]]) -> bool:
    return any(_is_backend_file(str(ev.get("file") or "")) for ev in _step_evidence(steps))


def _workflow_evidence_files(workflow: Dict[str, Any]) -> Set[str]:
    files = {str(ev.get("file") or "") for ev in workflow.get("evidence") or [] if isinstance(ev, dict)}
    for node in workflow.get("evidence_nodes") or []:
        if not isinstance(node, dict):
            continue
        evidence = node.get("evidence")
        if isinstance(evidence, dict):
            files.add(str(evidence.get("file") or ""))
        for outgoing in node.get("outgoing") or []:
            if not isinstance(outgoing, dict):
                continue
            target = outgoing.get("target")
            if isinstance(target, dict):
                files.add(str(target.get("file") or ""))
    return files


def _step_evidence(steps: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for step in steps:
        for ev in step.get("evidence") or []:
            if isinstance(ev, dict):
                yield ev


def _normalize_phase(value: Any) -> str:
    phase = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return PHASE_ALIASES.get(phase, phase)


def _is_frontend_file(file_path: str) -> bool:
    path = file_path.replace("\\", "/").lower()
    return any(marker in path for marker in FRONTEND_MARKERS)


def _is_backend_file(file_path: str) -> bool:
    path = file_path.replace("\\", "/").lower()
    if any(marker in path for marker in BACKEND_MARKERS):
        return True
    return path.startswith("api/") or "/pages/api/" in path or "/app/api/" in path


def _non_empty(value: Any) -> bool:
    return bool(str(value or "").strip())
