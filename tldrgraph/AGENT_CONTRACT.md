# TLDRGraph Agent Contract

TLDRGraph builds a source-backed feature catalog and Workflow Explorer. It does
not construct an architecture graph and does not launch an AI process itself.

## Direct artifact workflow

Run `tldrgraph init` to create a catalog. Run `tldrgraph refresh` to update an
existing catalog after source changes. A missing, invalid, or stale catalog returns
`needs_feature_workflows` and prints the current `source_hash`. The active coding
agent identifies feature outcomes and immediately writes the `.tldrgraph/features.yaml`
catalog index. It then delegates each indexed outcome to a separate source-reading
subagent. Every worker writes only its own complete file under
`.tldrgraph/workflows/`; the active agent does not collect worker objects or
write workflow files. Run the command that reported the status again to validate those artifacts
against the current source inventory and generate the visualizer.

Never delegate the entire catalog to one source-reading subagent. Workers may
run in parallel, but the active agent owns feature discovery, shared areas,
index creation and delegation; each worker owns its workflow-file write.

## Evidence

Every feature and every displayed workflow step must have evidence shaped as:

```yaml
file: relative/path/to/source.py
symbol: verified_symbol
line: 12
code_start: 12
code_end: 28
```

Paths must be repository-relative and present in the current source inventory.
Line ranges must exist in the current file. Never invent evidence.

Model each generated workflow as a directly renderable flowchart: initiating
action, proven process steps, decision branches, joined continuation, and final
response or UI update. When one workflow step has mutually exclusive paths,
modes, or choices, that step is rendered as a decision node. Add an `options`
list for its labeled branches; each option becomes a clickable process node,
rejoins the following proven step, and includes its own `title`, `text`, and
verified `evidence`. For example, a runtime bootstrap decision with Docker and
Kubernetes paths should use two options, not one step with both paths hidden as
references.

## Catalog rules

- Areas have a `product` or `technical` perspective and an order within it.
- Features describe user, admin, developer, or operator outcomes—not code symbols.
- A `generated` workflow proves the complete journey through its final response
  or visible result.
- A `partial` workflow contains only proven steps and explains the absent portion
  in `missing_coverage`.
- A `pending` workflow has no steps and explains what could not be established.
- User-facing flows begin at the initiating action and include the client request,
  backend work, response, and UI update when those stages exist.
- Alternate paths are represented as a decision step plus `options`, so the
  explorer can draw labeled branch nodes that reconnect to the following step.

The catalog index uses schema `tldrgraph/features@4`, generator
`feature-catalog-agent@4`, and the reported `source_hash`. Its feature rows only
contain ID, area, title, audience, summary, and workflow path. Each worker-owned
workflow uses schema `tldrgraph/feature-workflow@4`, generator
`feature-workflow-subagent@4`, the same source hash, matching ID and title, and
all feature evidence, status, missing coverage, steps, and options. Continue
until `tldrgraph init` or `tldrgraph refresh` reports `done`.
