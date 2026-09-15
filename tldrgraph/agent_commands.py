"""Install one graph-free workflow handshake across supported coding agents."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

BLOCK_BEGIN = "<!-- BEGIN TLDRGRAPH -->"
BLOCK_END = "<!-- END TLDRGRAPH -->"
COMMAND_NAME = "tldrgraph-init"
AGENTS_MD = "AGENTS.md"


@dataclass(frozen=True)
class AgentTarget:
    name: str
    command_path: Optional[str] = None
    instructions_path: Optional[str] = None
    marker: Optional[str] = None
    frontmatter: bool = True


TARGETS: Tuple[AgentTarget, ...] = (
    AgentTarget("Claude Code", command_path=f".claude/commands/{COMMAND_NAME}.md"),
    AgentTarget("Cursor", command_path=f".cursor/commands/{COMMAND_NAME}.md"),
    AgentTarget("opencode", command_path=f".opencode/command/{COMMAND_NAME}.md", marker=".opencode"),
    AgentTarget("Codex", command_path=f".agents/skills/{COMMAND_NAME}/SKILL.md"),
    AgentTarget("Cline", command_path=f".clinerules/workflows/{COMMAND_NAME}.md",
                instructions_path=".clinerules/tldrgraph.md", marker=".clinerules"),
    AgentTarget("Windsurf", command_path=f".windsurf/workflows/{COMMAND_NAME}.md",
                instructions_path=".windsurf/rules/tldrgraph.md", marker=".windsurf"),
    AgentTarget("Roo Code", command_path=f".roo/commands/{COMMAND_NAME}.md", marker=".roo"),
    AgentTarget("Kilo Code", command_path=f".kilocode/workflows/{COMMAND_NAME}.md", marker=".kilocode"),
    AgentTarget("Goose", command_path=f".goosehints/{COMMAND_NAME}.md", marker=".goosehints", frontmatter=False),
    AgentTarget("Continue", command_path=f".continue/prompts/{COMMAND_NAME}.prompt", marker=".continue", frontmatter=False),
)

SUPERSEDED = (
    ".claude/skills/tldrgraph/SKILL.md", ".claude/skills/codechakra/SKILL.md",
    ".claude/commands/tldrgraph-layers.md", ".claude/commands/tldrgraph-enrich.md",
    ".cursor/rules/tldrgraph.mdc", ".agents/workflows/tldrgraph.md",
    ".agents/workflows/tldrgraph-init.md", ".agents/rules/tldrgraph.md",
    ".agents/rules/tldrgraph-init.md",
)

INSTRUCTIONS_BODY = """## TLDRGraph

TLDRGraph builds a source-backed feature and workflow catalog for this repository.
It does not build an architecture graph, infer workflows heuristically, or run AI itself.

Run `tldrgraph init`. If it returns `needs_feature_workflows`, identify feature
outcomes and immediately write the `.tldrgraph/features.yaml` v4 catalog index
with the reported `source_hash`. Then spawn one fresh source-reading subagent
for each indexed feature. Each worker writes only its assigned complete
`.tldrgraph/workflows/<feature_id>.yaml` v4 file; it never edits `features.yaml`
or another feature's workflow. Run `tldrgraph init` again to validate the direct
artifacts and generate the explorer.

Every capability and workflow step must cite a verified repository-relative
file, symbol, and line range. Define capabilities as user, admin, developer, or
operator outcomes. Use `generated` only for a proven end-to-end journey,
`partial` with `missing_coverage` for a proven fragment, and `pending` with no
steps when no reliable sequence can be established.

Model each feature as a directly renderable flowchart: initiating action,
proven process steps, decision branches, joined continuation, and final result.
When a workflow step has mutually exclusive paths, modes, or choices, make the
step the decision node and represent each labeled, evidence-backed branch as a
step `options` entry that rejoins the following proven step.

The full schema is in `.tldrgraph/AGENT_CONTRACT.md`.
"""

COMMAND_BODY = """# TLDRGraph: build the source-backed workflow catalog

Run exactly:

```bash
tldrgraph init
```

When the status is `needs_feature_workflows`:

1. Read the `source_hash` and validation status returned by `tldrgraph init`.
2. Identify feature outcomes, define areas, and write the v4
   `.tldrgraph/features.yaml` index before delegating workflow research.
3. Spawn one fresh source-reading subagent for each indexed feature. Never assign the entire catalog to one subagent.
4. Have each worker write only its evidence-backed v4 workflow to its assigned
   `.tldrgraph/workflows/<feature_id>.yaml` file; do not collect or rewrite it.
5. Run `tldrgraph init` again.

Continue until the status is `done`.
"""


def _frontmatter(name: str, description: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n"


def command_text(target: Optional[AgentTarget] = None) -> str:
    if target is not None and not target.frontmatter:
        return COMMAND_BODY
    return _frontmatter(COMMAND_NAME, "Build or refresh source-backed feature workflows") + COMMAND_BODY


def instructions_text(target: Optional[AgentTarget] = None) -> str:
    if target is None or not target.frontmatter:
        return INSTRUCTIONS_BODY
    return _frontmatter("tldrgraph", "Source-backed feature workflow catalog") + INSTRUCTIONS_BODY


def _write_if_changed(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() == content:
                return
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def active_targets(root: str, all_agents: bool = False) -> List[AgentTarget]:
    return [target for target in TARGETS
            if all_agents or target.marker is None or os.path.isdir(os.path.join(root, target.marker))]


def remove_superseded(root: str) -> List[str]:
    removed = []
    for relative in SUPERSEDED:
        path = os.path.join(root, relative)
        if os.path.isfile(path):
            os.remove(path); removed.append(relative)
    return removed


def install_agent_commands(root_dir: str = ".", all_agents: bool = False) -> Dict[str, str]:
    from .installer import upsert_block

    root, written = os.path.abspath(root_dir), {}
    agents_path = os.path.join(root, AGENTS_MD)
    existing = ""
    if os.path.isfile(agents_path):
        with open(agents_path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    _write_if_changed(agents_path, upsert_block(existing, INSTRUCTIONS_BODY, BLOCK_BEGIN, BLOCK_END))
    written[f"{AGENTS_MD} (instructions, all agents)"] = agents_path
    for target in active_targets(root, all_agents):
        if target.command_path:
            path = os.path.join(root, target.command_path); _write_if_changed(path, command_text(target))
            written[f"{target.name} (command)"] = path
        if target.instructions_path:
            path = os.path.join(root, target.instructions_path); _write_if_changed(path, instructions_text(target))
            written[f"{target.name} (instructions)"] = path
    removed = remove_superseded(root)
    if removed:
        written["superseded (removed)"] = ", ".join(removed)
    return written
