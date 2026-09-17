"""Small YAML/JSON persistence helpers used by the workflow handshake."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import yaml


def read_payload(path: str) -> Any:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle) if path.endswith(".json") else yaml.safe_load(handle)


def atomic_write(path: str, payload: Any) -> str:
    """Write YAML atomically so interrupted init runs never leave partial files."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False)
    try:
        with handle:
            yaml.safe_dump(payload, handle, default_flow_style=False, sort_keys=False)
        os.replace(handle.name, path)
    except Exception:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise
    return path
