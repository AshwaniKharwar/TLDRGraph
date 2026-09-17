"""Install the TLDRGraph workflow contract and agent instructions."""

from __future__ import annotations

import os
from typing import Dict, List

from .agent_commands import install_agent_commands

GITIGNORE_BEGIN = "# BEGIN TLDRGRAPH"
GITIGNORE_END = "# END TLDRGRAPH"
GITIGNORE_BLOCK = "\n".join([
    "# TLDRGraph generated workflow state.",
    ".tldrgraph/*",
    "!.tldrgraph/AGENT_CONTRACT.md",
])


def upsert_block(existing: str, body: str, begin: str, end: str) -> str:
    block = f"{begin}\n{body.strip()}\n{end}\n"
    start, stop = existing.find(begin), existing.find(end)
    if start != -1 and stop > start:
        return existing[:start] + block + existing[stop + len(end):].lstrip("\n")
    if not existing:
        return block
    separator = "\n" if existing.endswith("\n") else "\n\n"
    return existing + separator + block


def ensure_gitignore(root_dir: str = ".") -> Dict[str, str]:
    path = os.path.join(os.path.abspath(root_dir), ".gitignore")
    existing = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    updated = upsert_block(existing, GITIGNORE_BLOCK, GITIGNORE_BEGIN, GITIGNORE_END)
    if updated == existing:
        return {"path": path, "status": "unchanged"}
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(updated)
    return {"path": path, "status": "updated" if existing else "created"}


def _contract_text() -> str:
    candidates = (
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "AGENT_CONTRACT.md"),
        os.path.join(os.path.dirname(__file__), "AGENT_CONTRACT.md"),
    )
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
    raise RuntimeError("TLDRGraph AGENT_CONTRACT.md is missing from the installation")


def install_agent_rules(root_dir: str = ".", all_agents: bool = False) -> Dict[str, str]:
    root = os.path.abspath(root_dir)
    state = os.path.join(root, ".tldrgraph")
    os.makedirs(state, exist_ok=True)
    contract = os.path.join(state, "AGENT_CONTRACT.md")
    content = _contract_text()
    current = None
    if os.path.isfile(contract):
        with open(contract, "r", encoding="utf-8") as handle:
            current = handle.read()
    if current != content:
        with open(contract, "w", encoding="utf-8") as handle:
            handle.write(content)
    result = install_agent_commands(root, all_agents)
    result["contract"] = contract
    return result


def gitignore_warnings(root_dir: str = ".") -> List[str]:
    path = os.path.join(os.path.abspath(root_dir), ".gitignore")
    if not os.path.isfile(path):
        return []
    watched = {".agents", ".claude", ".cursor", "AGENTS.md"}
    warnings = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            entry = raw.strip()
            if entry and not entry.startswith("#") and entry.lstrip("/").rstrip("/") in watched:
                warnings.append(f".gitignore:{number} ignores '{entry}', so installed agent rules may not be shared")
    return warnings
