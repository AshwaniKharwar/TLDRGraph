"""Paths and orchestration for saved graph-free feature workflows."""

from __future__ import annotations

import os
from typing import Any, Dict

FEATURES_FILENAME = "features.yaml"
WORKFLOWS_DIRNAME = "workflows"
WORKFLOW_GENERATOR = "feature-workflow-subagent@3"


def features_path(root: str) -> str:
    return os.path.join(os.path.abspath(root), ".tldrgraph", FEATURES_FILENAME)


def workflows_dir(root: str) -> str:
    return os.path.join(os.path.abspath(root), ".tldrgraph", WORKFLOWS_DIRNAME)


def workflow_path(root: str, feature_id: str) -> str:
    return os.path.join(workflows_dir(root), f"{feature_id}.yaml")


def relative_workflow_path(feature_id: str) -> str:
    return f".tldrgraph/workflows/{feature_id}.yaml"


def generate_feature_workflow_files(root: str, inventory: Dict[str, Any]) -> Dict[str, Any]:
    from .feature_workflow_handoff import (
        apply_feature_workflow_response,
        clear_feature_workflow_request,
        current_manifest,
        write_feature_workflow_request,
    )

    current_hash = str(inventory["source_hash"])
    manifest, error = apply_feature_workflow_response(root, inventory)
    if not error:
        manifest = manifest or current_manifest(root, current_hash)
    if manifest is not None:
        clear_feature_workflow_request(root)
        features = manifest.get("features") or []
        return {
            "features": len(features),
            "generated": sum(item.get("status") == "generated" for item in features),
            "partial": sum(item.get("status") == "partial" for item in features),
            "workflow_pending": sum(item.get("status") == "pending" for item in features),
            "pending": 0, "source_hash": current_hash, "error": "", "request_path": "",
        }
    request = write_feature_workflow_request(root, inventory, error)
    return {"features": 0, "generated": 0, "partial": 0, "workflow_pending": 0,
            "pending": 1, "source_hash": current_hash, "error": error,
            "request_path": request}


def load_feature_manifest(root: str, current_hash: str = ""):
    from .feature_workflow_loader import load_feature_manifest as load
    return load(root, current_hash)


def load_saved_feature_workflows(root: str, current_hash: str = ""):
    from .feature_workflow_loader import load_saved_feature_workflows as load
    return load(root, current_hash)
