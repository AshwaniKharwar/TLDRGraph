"""Prepare the workflow-only payload embedded in the standalone explorer."""

from __future__ import annotations

import os
from typing import Any, Dict

from ..feature_workflow_loader import load_saved_feature_workflows
from ..source_inventory import build_source_inventory


def prepare_visualizer_data(root_dir: str) -> Dict[str, Any]:
    root = os.path.abspath(root_dir)
    inventory = build_source_inventory(root)
    saved = load_saved_feature_workflows(
        root, str(inventory["source_hash"]), inventory
    )
    return {
        "root": root,
        "workflow_areas": saved.get("areas", []),
        "workflows": saved.get("workflows", []),
        "workflow_state": {
            key: value for key, value in saved.items()
            if key not in {"areas", "workflows", "source_files"}
        },
        "source_files": saved.get("source_files", []),
    }
