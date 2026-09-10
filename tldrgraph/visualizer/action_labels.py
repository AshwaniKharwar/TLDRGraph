"""Plain-language labels for workflow nodes."""

from __future__ import annotations

import re
from typing import Any, Dict

HTTP_VERBS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
ACTION_WORDS = {"create", "update", "delete", "remove", "list", "fetch", "get", "load", "save"}


def _words(text: str) -> str:
    cleaned = re.sub(r"\(.*?\)", "", str(text or "")).strip().split(".")[-1].lstrip("_")
    cleaned = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cleaned).replace("_", " ").replace("-", " ")
    return " ".join(w for w in cleaned.split() if w)


def humanize_symbol(text: str, default: str = "Do the work") -> str:
    words = _words(text)
    if not words:
        return default
    if words.lower().endswith(" page"):
        words = "Show " + words[:-5]
    elif not words.split()[0].lower() in ACTION_WORDS:
        words = "Use " + words
    return words[:1].upper() + words[1:]


def _usable_intent(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return ""
    lower = normalized.lower()
    bad = (
        lower.startswith(("the symbol ", "this symbol ", "core module symbol")),
        " is defined in " in lower,
        " located at " in lower,
        "visible in that source module" in lower,
    )
    if any(bad):
        return ""
    first = re.split(r"(?<=[.!?])\s+", normalized, 1)[0].strip(" .")
    first = re.sub(r"^(This|The)\s+(function|method|class|component|route|endpoint|schema)\s+", "", first, flags=re.I)
    first = re.sub(r"^(It|This)\s+", "", first, flags=re.I)
    return first[:1].upper() + first[1:] if first else ""


def _route_action(label: str) -> str:
    match = re.search(r"\b(" + "|".join(HTTP_VERBS) + r")\s+(/[^\s]+)", str(label or ""), re.I)
    if not match:
        return ""
    method, path = match.group(1).upper(), match.group(2)
    parts = [p for p in re.split(r"/+", path) if p and not p.startswith(":") and "{" not in p]
    if not parts:
        return "Handle web request"
    last = parts[-1].lower()
    resource = parts[-2] if last in ACTION_WORDS and len(parts) > 1 else parts[-1]
    resource = _words(resource).lower().rstrip("s") or "item"
    verb = last if last in ACTION_WORDS else {
        "GET": "fetch", "POST": "create", "PUT": "update", "PATCH": "update",
        "DELETE": "delete",
    }.get(method, "handle")
    action = f"{verb} {resource}".strip()
    if "handler" in label.lower():
        action = "handle " + action + " request"
    return action[:1].upper() + action[1:]


def action_label(node: Dict[str, Any], fallback: str = "") -> str:
    intent = _usable_intent(str(node.get("intent") or node.get("summary") or ""))
    if intent:
        return intent
    label = str(node.get("label") or node.get("symbol") or fallback or "")
    route = _route_action(label)
    if route:
        return route
    file_path = str(node.get("file") or "").lower()
    layer = str(node.get("layer") or node.get("layer_id") or "").lower()
    if ("schema.prisma" in file_path or "data" in layer or "persistence" in layer) and _words(label):
        return f"Store {_words(label).lower()} data"
    return humanize_symbol(label or fallback)
