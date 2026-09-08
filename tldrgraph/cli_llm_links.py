"""
Init-stage LLM route link orchestration.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import click

from . import agent_runner
from .cli_enrichment import read_payload, state_path, write_payload
from .llm_route_inference import (
    build_route_link_payload,
    build_route_link_prompt,
    coerce_link_items,
    payload_hash,
    apply_route_link_items,
)

REQUEST_FILENAME = "llm_links_request.yaml"
RESPONSE_FILENAME = "llm_links_response.yaml"
APPLIED_RESPONSE_FILENAME = "llm_links_response.applied.yaml"
STATE_FILENAME = "llm_links_state.yaml"
STATUS_NEEDS_LLM_LINKS = "needs_llm_links"


def _state(root: str) -> Dict[str, Any]:
    data = read_payload(state_path(root, STATE_FILENAME))
    return data if isinstance(data, dict) else {}


def _write_state(root: str, candidate_hash: str, applied: int) -> None:
    write_payload(state_path(root, STATE_FILENAME), {
        "schema": "codechakra/llm-route-links-state@1",
        "candidate_hash": candidate_hash,
        "applied": applied,
    })


def apply_pending_llm_links_response(path: str, loader: Any) -> Optional[Dict[str, Any]]:
    candidate = state_path(path, RESPONSE_FILENAME)
    if not os.path.isfile(candidate):
        return None
    items = coerce_link_items(read_payload(candidate))
    payload = build_route_link_payload(path, loader.graph)
    stats = apply_route_link_items(loader.graph, items)
    loader.save_graph()
    _write_state(path, payload_hash(payload), len(stats["applied"]))
    try:
        os.replace(candidate, state_path(path, APPLIED_RESPONSE_FILENAME))
    except OSError:
        pass
    return stats


def llm_links_already_current(path: str, payload: Dict[str, Any], candidate_hash: str) -> bool:
    state = _state(path)
    if state.get("candidate_hash") != candidate_hash:
        return False
    if state.get("applied", 0) > 0:
        return True
    return not payload.get("candidate_pairs")


def run_llm_link_step(
    path: str,
    root: str,
    loader: Any,
    agent_cli: bool,
    agent_model: Optional[str],
    as_json: bool,
    emit_status: Any,
) -> Optional[str]:
    payload = build_route_link_payload(path, loader.graph)
    candidate_hash = payload_hash(payload)
    if llm_links_already_current(path, payload, candidate_hash):
        return None
    if not payload.get("frontend_nodes") or not payload.get("backend_nodes"):
        _write_state(path, candidate_hash, 0)
        return None

    if agent_cli:
        agent = agent_runner.find_agent_cli()
        if agent is not None:
            try:
                raw = agent_runner.run_agent_json(
                    agent, build_route_link_prompt(root, payload), root, model=agent_model
                )
                stats = apply_route_link_items(loader.graph, coerce_link_items(raw))
                loader.save_graph()
                _write_state(path, candidate_hash, len(stats["applied"]))
                if not as_json:
                    click.echo(
                        f"🔗 Added {len(stats['applied'])} LLM route link(s); "
                        f"dropped {len(stats['rejected'])} candidate(s)."
                    )
                return None
            except agent_runner.AgentError as err:
                if not as_json:
                    click.echo(f"   ⚠️  LLM route link inference failed: {err}")
                return None

    req_path = write_payload(state_path(path, REQUEST_FILENAME), {
        "schema": "codechakra/llm-route-links-request@1",
        "response_file": os.path.join(".tldrgraph", RESPONSE_FILENAME),
        "instructions": [
            "Open and read the referenced source files before answering.",
            "Return only links with source-backed frontend/backend file and line evidence.",
            "Write a YAML list of {source, target, confidence, frontend_evidence, backend_evidence, explanation}.",
            f"Write the response to .tldrgraph/{RESPONSE_FILENAME}, then run tldrgraph init again.",
        ],
        "payload": payload,
    })
    emit_status(STATUS_NEEDS_LLM_LINKS, "llm_links", [
        "The graph is built and enriched. LLM frontend-backend link inference needs the active agent:",
        "",
        f"  1. Read {os.path.relpath(req_path, root)}",
        "  2. Open the referenced frontend and backend source files.",
        f"  3. Write .tldrgraph/{RESPONSE_FILENAME} with strict evidence for every link.",
        "  4. Run: tldrgraph init",
        "",
        "Use --no-llm-links to skip this optional inference stage.",
    ], progress={"candidate_hash": candidate_hash}, as_json=as_json)
    return STATUS_NEEDS_LLM_LINKS
