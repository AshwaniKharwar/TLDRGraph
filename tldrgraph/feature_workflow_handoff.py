"""Host-agent handshake for graph-free feature workflow generation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .feature_workflow_schema import FEATURE_SCHEMA, RESPONSE_SCHEMA, normalize_response
from .feature_workflow_validation import validate_workflow
from .payload import atomic_write, read_payload

REQUEST_FILENAME = "feature_workflows_request.yaml"
RESPONSE_FILENAME = "feature_workflows_response.yaml"
APPLIED_RESPONSE_FILENAME = "feature_workflows_response.applied.yaml"
REQUEST_SCHEMA = "tldrgraph/feature-workflows-request@3"


def _state_path(root: str, filename: str) -> str:
    return os.path.join(os.path.abspath(root), ".tldrgraph", filename)


def clear_feature_workflow_request(root: str) -> None:
    try:
        os.remove(_state_path(root, REQUEST_FILENAME))
    except FileNotFoundError:
        pass


def feature_workflow_status_lines(root: str, stats: Optional[Dict[str, Any]]) -> List[str]:
    values = stats or {}
    if not values.get("pending"):
        return ["Feature catalog and workflow files are current."]
    lines = [
        "Feature discovery requires the active coding agent:",
        "  1. Read .tldrgraph/feature_workflows_request.yaml",
        "  2. Delegate it to a source-reading subagent.",
        "  3. Have it write .tldrgraph/feature_workflows_response.yaml.",
        "  4. Run: tldrgraph init",
    ]
    if values.get("error"):
        lines.insert(1, f"  Previous response rejected: {values['error']}")
    return lines


def _response_shape() -> Dict[str, Any]:
    def evidence() -> Dict[str, Any]:
        return {"file": "relative/source.py", "symbol": "verified_symbol",
                "line": 10, "code_start": 10, "code_end": 24}

    option_a = {"phase": "optional override; defaults to parent step phase",
                "title": "Mutually exclusive path title",
                "text": "Source-backed behavior for this path.",
                "evidence": [evidence()]}
    option_b = {"phase": "optional override; defaults to parent step phase",
                "title": "Second mutually exclusive path title",
                "text": "Source-backed behavior for the second path.",
                "evidence": [evidence()]}
    return {
        "schema": RESPONSE_SCHEMA, "source_hash": "copy from this request",
        "areas": [{"id": "lowercase_snake_case", "title": "Capability area",
                   "summary": "What the area provides.", "perspective": "product | technical",
                   "order": 0}],
        "features": [{
            "id": "lowercase_snake_case", "area_id": "copy an area id",
            "title": "Human capability title", "audience": "user | admin | developer | operator",
            "summary": "Source-backed outcome.", "evidence": [evidence()],
            "workflow": {"status": "generated | partial | pending",
                         "summary": "Complete or known flow.",
                         "missing_coverage": "required for partial or pending",
                         "steps": [{"number": 1,
                                    "phase": "user_action | frontend | request | backend | persistence | external | response | ui_update",
                                    "title": "Short title", "text": "Source-backed behavior.",
                                    "evidence": [evidence()],
                                    "options": [option_a, option_b]}]},
        }],
    }


def write_feature_workflow_request(root: str, inventory: Dict[str, Any], error: str = "") -> str:
    payload = {
        "schema": REQUEST_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hash": inventory["source_hash"],
        "response_file": f".tldrgraph/{RESPONSE_FILENAME}",
        "instructions": [
            "Delegate this request to a source-reading subagent.",
            "Inspect the whole repository: docs, UI actions, APIs, services, persistence, integrations, configuration, and operations.",
            "Define meaningful user, admin, developer, or operator outcomes; never use a class or service as the feature itself.",
            "Start at the initiating action and follow every proven hop through the response or final UI update.",
            "When a step has mutually exclusive paths, modes, or choices, add options so each path becomes its own flow-chart node.",
            "Use generated only for a complete flow, partial with missing_coverage for a proven fragment, and pending with no steps when no sequence is reliable.",
            "Every feature and displayed step needs verified repository-relative file, symbol, and line-range evidence.",
            f"Write {RESPONSE_SCHEMA} YAML to .tldrgraph/{RESPONSE_FILENAME}, then rerun tldrgraph init.",
        ],
        "repository_discovery": {"root": ".", "source_files": inventory["files"]},
        "response_shape": _response_shape(),
    }
    if error:
        payload["previous_response_error"] = error
    return atomic_write(_state_path(root, REQUEST_FILENAME), payload)


def apply_feature_workflow_response(root: str, inventory: Dict[str, Any]):
    from .feature_workflows import features_path, workflow_path

    response_path = _state_path(root, RESPONSE_FILENAME)
    if not os.path.isfile(response_path):
        return None, ""
    try:
        manifest, workflows = normalize_response(
            os.path.abspath(root), str(inventory["source_hash"]), inventory["files"],
            read_payload(response_path),
        )
        for feature_id, workflow in workflows.items():
            atomic_write(workflow_path(root, feature_id), workflow)
        atomic_write(features_path(root), manifest)
        os.replace(response_path, _state_path(root, APPLIED_RESPONSE_FILENAME))
        clear_feature_workflow_request(root)
        return manifest, ""
    except (OSError, ValueError, TypeError, yaml.YAMLError) as error:
        return None, str(error)


def current_manifest(root: str, current_hash: str):
    from .feature_workflows import features_path, workflow_path

    manifest = read_payload(features_path(root))
    if not isinstance(manifest, dict) or manifest.get("schema") != FEATURE_SCHEMA:
        return None
    if (manifest.get("source_hash") != current_hash
            or manifest.get("generator") != "feature-catalog-subagent@3"):
        return None
    areas, features = manifest.get("areas"), manifest.get("features")
    if not isinstance(areas, list) or not areas or not isinstance(features, list) or not features:
        return None
    for feature in features:
        if not isinstance(feature, dict):
            return None
        workflow = read_payload(workflow_path(root, str(feature.get("id") or "")))
        if (not isinstance(workflow, dict) or workflow.get("source_hash") != current_hash
                or workflow.get("feature_id") != feature.get("id")
                or workflow.get("status") != feature.get("status")
                or not validate_workflow(workflow)):
            return None
    return manifest
