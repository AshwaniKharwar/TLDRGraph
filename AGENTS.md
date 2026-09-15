<!-- BEGIN TLDRGRAPH -->
## TLDRGraph

TLDRGraph builds a source-backed feature and workflow catalog for this repository.
It does not build an architecture graph, infer workflows heuristically, or run AI itself.

Run `tldrgraph init`. If it returns `needs_feature_workflows`, read
`.tldrgraph/feature_workflows_request.yaml`, delegate the entire request to a
source-reading subagent, and have it write
`.tldrgraph/feature_workflows_response.yaml`. Run `tldrgraph init` again to
validate and apply the response. Do not edit generated `features.yaml` or
`workflows/*.yaml` directly.

Every capability and workflow step must cite a verified repository-relative
file, symbol, and line range. Define capabilities as user, admin, developer, or
operator outcomes. Use `generated` only for a proven end-to-end journey,
`partial` with `missing_coverage` for a proven fragment, and `pending` with no
steps when no reliable sequence can be established.

The full schema is in `.tldrgraph/AGENT_CONTRACT.md`.
<!-- END TLDRGRAPH -->
