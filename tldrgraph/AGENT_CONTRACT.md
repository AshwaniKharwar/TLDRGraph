# TLDRGraph Agent Contract

TLDRGraph builds a source-backed feature catalog and Workflow Explorer. It does
not construct an architecture graph and does not launch an AI process itself.

## Initialization handshake

Run `tldrgraph init`. A missing or stale catalog produces
`.tldrgraph/feature_workflows_request.yaml`. Delegate that complete request to a
source-reading subagent. The subagent writes the requested
`tldrgraph/feature-workflows-response@3` document to
`.tldrgraph/feature_workflows_response.yaml`.

Run `tldrgraph init` again. TLDRGraph validates the response against the current
source inventory and atomically writes `.tldrgraph/features.yaml` plus one file
per capability under `.tldrgraph/workflows/`.

## Evidence

Every feature and every displayed workflow step must have evidence shaped as:

```yaml
file: relative/path/to/source.py
symbol: verified_symbol
line: 12
code_start: 12
code_end: 28
```

Paths must be repository-relative and present in the request's source inventory.
Line ranges must exist in the current file. Never invent evidence.

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

The request contains the exact response shape and current `source_hash`. Copy the
hash verbatim. Continue until `tldrgraph init` reports `done`.
