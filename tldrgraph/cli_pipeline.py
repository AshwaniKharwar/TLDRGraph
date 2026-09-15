"""Workflow-only initialization pipeline."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import click

from .feature_workflow_handoff import feature_workflow_status_lines
from .feature_workflows import generate_feature_workflow_files
from .installer import ensure_gitignore, install_agent_rules
from .source_inventory import build_source_inventory
from .visualizer import generate_visualizer_html

STATUS_DONE = "done"
STATUS_NEEDS_FEATURE_WORKFLOWS = "needs_feature_workflows"


def emit_status(status: str, lines: List[str], progress: Dict[str, Any], as_json: bool) -> str:
    if as_json:
        click.echo(json.dumps({"status": status, "phase": "feature_workflows",
                               "next_action": lines, "progress": progress}, indent=2))
    else:
        click.echo("\nTLDRGRAPH INIT — " + ("COMPLETE" if status == STATUS_DONE else "NEXT ACTION REQUIRED"))
        click.echo(f"status: {status}")
        click.echo(f"source_hash: {progress['source_hash']}")
        for line in lines:
            click.echo(line)
        click.echo()
    return status


def init_pipeline(path: str, as_json: bool = False) -> str:
    root = os.path.abspath(path)
    ensure_gitignore(root)
    install_agent_rules(root)
    inventory = build_source_inventory(root)
    stats = generate_feature_workflow_files(root, inventory)
    progress = {"source_files": len(inventory["files"]),
                "source_hash": inventory["source_hash"],
                "features": stats.get("features", 0)}
    if stats["pending"]:
        return emit_status(STATUS_NEEDS_FEATURE_WORKFLOWS,
                           feature_workflow_status_lines(root, stats), progress, as_json)
    html_path = generate_visualizer_html(root)
    lines = [f"Saved {stats['features']} feature(s).",
             f"Generated {os.path.relpath(html_path, root)}."]
    return emit_status(STATUS_DONE, lines, progress, as_json)
