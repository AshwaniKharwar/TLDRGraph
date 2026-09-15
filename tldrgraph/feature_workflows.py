"""Paths and orchestration for saved graph-free feature workflows."""

from __future__ import annotations

import os
from typing import Any, Dict

from .payload import read_payload

FEATURES_FILENAME = "features.yaml"
WORKFLOWS_DIRNAME = "workflows"
WORKFLOW_GENERATOR = "feature-workflow-subagent@4"


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
        current_manifest,
    )

    current_hash = str(inventory["source_hash"])
    manifest, error = current_manifest(root, inventory)
    if manifest is not None:
        features = manifest.get("features") or []
        statuses = [
            str((read_payload(workflow_path(root, str(item.get("id") or ""))) or {}).get("status") or "")
            for item in features
        ]
        return {
            "features": len(features),
            "generated": statuses.count("generated"),
            "partial": statuses.count("partial"),
            "workflow_pending": statuses.count("pending"),
            "pending": 0, "source_hash": current_hash, "error": "", "request_path": "",
        }
    return {"features": 0, "generated": 0, "partial": 0, "workflow_pending": 0,
            "pending": 1, "source_hash": current_hash, "error": error,
            "request_path": ""}


def load_feature_manifest(root: str, current_hash: str = ""):
    from .feature_workflow_loader import load_feature_manifest as load
    return load(root, current_hash)


def load_saved_feature_workflows(root: str, current_hash: str = ""):
    from .feature_workflow_loader import load_saved_feature_workflows as load
    return load(root, current_hash)
