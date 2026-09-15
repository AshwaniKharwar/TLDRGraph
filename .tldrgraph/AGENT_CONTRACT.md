# TLDRGraph Agent Contract

TLDRGraph builds a source-backed feature catalog and Workflow Explorer. It does
not construct an architecture graph and does not launch an AI process itself.

## Initialization handshake

Run `tldrgraph init`. A missing or stale catalog produces:

```text
.tldrgraph/feature_workflows_request.yaml
```

The coding agent must delegate that complete request to a source-reading
subagent. The subagent writes the requested
`tldrgraph/feature-workflows-response@3` document to:

```text
.tldrgraph/feature_workflows_response.yaml
```

Run `tldrgraph init` again. TLDRGraph validates the response against the current
source inventory and atomically writes `.tldrgraph/features.yaml` plus one file
per capability under `.tldrgraph/workflows/`.

## Evidence

Every feature and every displayed workflow step must have at least one evidence
record:

```yaml
file: relative/path/to/source.py
symbol: verified_symbol
line: 12
code_start: 12
code_end: 28
```

Paths must be repository-relative and present in the request's source inventory.
Line ranges must exist in the current file. Never invent evidence.

When one workflow step has mutually exclusive paths, modes, or choices, add an
`options` list to that step. Each option becomes its own flow-chart node and must
include its own `title`, `text`, and verified `evidence`. For example, a runtime
bootstrap step with Docker and Kubernetes paths should use two options, not one
step with both paths hidden as references.

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
- Alternate paths are represented as step `options` so the explorer can draw
  separate branch nodes that reconnect to the following step.

The request contains the exact response shape and current `source_hash`. Copy the
hash verbatim. Continue the handshake until `tldrgraph init` reports `done`, then
run `tldrgraph ui --serve`.
