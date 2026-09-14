<!-- BEGIN TLDRGRAPH -->
## TLDRGraph

This repository is mapped into architectural layers designed from its own source,
with per-symbol intents you can search and trace.

### ⛔ FORBIDDEN TOOL BEHAVIORS
- **DO NOT use `grep_search`, `ripgrep`, or `find_by_name` as your primary discovery tool.** Blind text searching is strictly prohibited for codebase exploration, feature lookup, and understanding component flows.
- **DO NOT guess symbol locations or execution paths.**

### ✅ MANDATORY FIRST-STEP PROTOCOL
Whenever the user asks where a feature lives, how a component works, or what a symbol connects to, your first tool call MUST be `run_command` with one of the following:

```bash
tldrgraph query "<feature in plain English>"   # semantic search + end-to-end flow
tldrgraph trace "<Source>" "<Target>"          # exact path between two symbols
tldrgraph layers                               # node counts per layer
tldrgraph dead-code                            # review candidates, never a delete list
```

**Discovery Pattern**:
1. Run `tldrgraph query "<query>"` or `tldrgraph trace "<from>" "<to>"` to identify the exact file, layer, and line range.
2. Use `view_file` on the target file path returned by TLDRGraph to inspect the code.

Those are read-only and never trigger enrichment.
**To build or refresh the graph**, run `tldrgraph init`. It handles layer setup,
extraction, embeddings, and writes the file-backed Feature Workflow Explorer
artifacts: `.tldrgraph/features.yaml` plus `.tldrgraph/workflows/<feature_id>.yaml`.

TLDRGraph never invents heuristic features or launches an AI process for feature
generation. If `init` returns `needs_feature_workflows`, the agent running it must
open `.tldrgraph/feature_workflows_request.yaml`, spawn a source-reading subagent,
and have that subagent write `.tldrgraph/feature_workflows_response.yaml` with inferred
product/technical areas and source-backed capabilities. Ranked symbols are investigation
leads, not the feature list. Run `tldrgraph init` again to validate and apply
the response; do not edit final feature/workflow files directly. Workflow Explorer
reads only saved YAML, never curated blueprints, route-link workflow discovery,
BPMN-derived generation, `discover_workflows()`, `llm_http_route_link`,
`http_route_link`, or `calls_endpoint`. When writing feature workflows, start at
the user's button/menu/form action and continue through client request, backend
work, response payload, client handling, and final UI update. Do not skip proven steps.
Define outcomes as features: "Natural-language project creation" is a feature;
`OpencodeService` is supporting evidence. Use `partial` with `missing_coverage` for a
proven fragment and `pending` with no steps when no reliable sequence can be drawn.
Do not set `status: generated` unless the saved steps cover the end-to-end flow
for the proven feature boundary, and do not use route-link relations as workflow
evidence.
Full workflow: `.claude/commands/tldrgraph-init.md` (identical copies live in every
other agent directory). Schema: `.tldrgraph/AGENT_CONTRACT.md`.

`tldrgraph dead-code` lists **review candidates, not confirmed dead code**.
`unreviewed` means "not enough evidence to conclude" and is never removable.

## Code Quality & Architectural Standards
- **File Length Limit**: Every source file in `tldrgraph/` must be strictly under 400 lines. Split large modules into cohesive sub-units.
- **Function Complexity**: Functions and methods must be focused (<= 50 lines) with low cyclomatic complexity (<= 15).
- **Modularity & Re-exports**: Keep modules decoupled; preserve backwards compatibility with top-level package re-exports.
<!-- END TLDRGRAPH -->
