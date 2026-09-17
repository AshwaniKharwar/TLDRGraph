"""Assemble the zero-dependency workflow explorer HTML."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from .data import prepare_visualizer_data

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
OUTPUT_FILENAME = "TLDRGRAPH_VISUALIZER.html"


def _read_asset(name: str) -> str:
    with open(os.path.join(ASSETS_DIR, name), "r", encoding="utf-8") as handle:
        return handle.read()


def _json_for_script(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":")).replace("</script>", "<\\/script>").replace("<!--", "<\\!--")


def render_html(data: Dict[str, Any]) -> str:
    replacements = {
        "/*__STYLES__*/": _read_asset("app.css"),
        "/*__DATA_JSON__*/": _json_for_script(data),
        "/*__SOURCEVIEW_JS__*/": _read_asset("sourceview.js"),
        "/*__APP_JS__*/": _read_asset("app.js"),
    }
    pattern = re.compile("|".join(re.escape(key) for key in replacements))
    return pattern.sub(lambda match: replacements[match.group(0)], _read_asset("index.html"))


def generate_visualizer_html(root_dir: str = ".") -> str:
    root = os.path.abspath(root_dir)
    output_dir = os.path.join(root, ".tldrgraph")
    os.makedirs(output_dir, exist_ok=True)
    output = os.path.join(output_dir, OUTPUT_FILENAME)
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(render_html(prepare_visualizer_data(root)))
    return output
