"""Validation and status reporting for direct agent-authored workflow artifacts."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .feature_workflow_schema import validate_catalog_artifacts
from .payload import read_payload


def feature_workflow_status_lines(root: str, stats: Optional[Dict[str, Any]],
                                  command_name: str = "init") -> List[str]:
    values = stats or {}
    if not values.get("pending"):
        return ["Feature catalog and workflow files are current."]
    lines = [
        "Feature discovery requires the active coding agent:",
        "  1. Inspect the repository and identify feature outcomes.",
        "  2. Spawn one fresh source-reading subagent for each feature.",
        "  3. Combine their evidence-backed results and write .tldrgraph/features.yaml",
        "     plus .tldrgraph/workflows/<feature_id>.yaml using this source_hash.",
        f"  4. Run: tldrgraph {command_name}",
    ]
    if values.get("error"):
        lines.insert(1, f"  Current artifacts rejected: {values['error']}")
    return lines


def current_manifest(root: str, inventory: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return the validated manifest, or a concrete reason it cannot be used."""
    from .feature_workflows import features_path, workflow_path

    try:
        manifest = read_payload(features_path(root))
        if not isinstance(manifest, dict):
            return None, "features catalog is missing or invalid"
        workflows = {
            str(feature.get("id") or ""): read_payload(workflow_path(root, str(feature.get("id") or "")))
            for feature in manifest.get("features") or [] if isinstance(feature, dict)
        }
        validated, _ = validate_catalog_artifacts(
            os.path.abspath(root), str(inventory["source_hash"]), inventory["files"], manifest, workflows,
        )
        return validated, ""
    except (OSError, ValueError, TypeError, yaml.YAMLError) as error:
        return None, str(error)
