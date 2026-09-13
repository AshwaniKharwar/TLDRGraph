"""Agent prompts for source-backed feature workflow files."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import agent_runner
from .feature_workflows import relative_workflow_path


def _run_json(root: str, prompt: str, agent_model: Optional[str]) -> Optional[Dict[str, Any]]:
    agent = agent_runner.find_agent_cli(respect_nesting=False)
    if agent is None:
        return None
    try:
        raw = agent_runner.run_agent_json(agent, prompt, root, model=agent_model)
    except agent_runner.AgentError:
        return None
    return raw if isinstance(raw, dict) else None


def generate_feature_manifest(
    root: str,
    graph_hash: str,
    candidates: List[Dict[str, Any]],
    agent_model: Optional[str],
) -> Optional[Dict[str, Any]]:
    prompt = (
        "Read this source-backed graph evidence and return JSON only. "
        "List the project's major user-facing and developer-facing features. "
        "Prefer features that represent an end-to-end user or developer goal, not isolated UI or backend helpers. "
        "Do not use curated workflows, BPMN, route-link workflow discovery, or guessed product flows. "
        "Every feature must include at least one evidence item copied from candidates.\n\n"
        "Return {\"features\":[{\"id\",\"title\",\"audience\",\"summary\",\"evidence\":[...] }]}.\n"
        f"Evidence:\n{{'graph_hash': {graph_hash!r}, 'candidates': {candidates!r}}}"
    )
    raw = _run_json(root, prompt, agent_model)
    items = raw.get("features") if raw else None
    if not isinstance(items, list):
        return None
    return {"features": items}


def generate_feature_workflow(
    root: str,
    graph_hash: str,
    feature: Dict[str, Any],
    evidence_nodes: List[Dict[str, Any]],
    agent_model: Optional[str],
) -> Optional[Dict[str, Any]]:
    prompt = (
        "Create one saved Feature Workflow Explorer workflow as JSON only. "
        "It must describe the FULL feature flow from the user's button/menu/form action all the way to the final response or UI update. "
        "Do not summarize away important hops or combine unrelated source symbols into one vague step. "
        "When source evidence supports it, include the path from the user-facing screen/component through request/client code, "
        "event handler, validation, request payload construction, API route or controller, middleware/auth, service/use-case logic, "
        "persistence/database, background jobs, external services, response payload creation, client response parsing, state update, "
        "toast/navigation/rendered result, and any user-visible error or success handling. "
        "Use simple language for non-technical users and vibe coders. "
        "Do not use curated workflows, BPMN generation, route-link workflow discovery, or guessed steps. "
        "Every step must include evidence copied from the provided source-backed nodes. "
        "If a frontend-to-backend or backend-to-frontend bridge is not present in evidence, include only the proven side and make the feature pending rather than inventing missing steps.\n\n"
        "Return exactly {\"workflow\":{\"schema\":\"codechakra/feature-workflow@1\",\"graph_hash\":...,\"feature_id\":...,"
        "\"title\":...,\"summary\":...,\"status\":\"generated\",\"steps\":[{\"number\":1,\"title\":...,\"text\":...,\"evidence\":[...]}]}}.\n"
        f"Feature:\n{feature!r}\nWorkflow path: {relative_workflow_path(str(feature.get('id') or 'feature'))}\n"
        f"Graph hash: {graph_hash}\nEvidence nodes:\n{evidence_nodes!r}"
    )
    raw = _run_json(root, prompt, agent_model)
    workflow = raw.get("workflow") if raw else None
    return workflow if isinstance(workflow, dict) else None
