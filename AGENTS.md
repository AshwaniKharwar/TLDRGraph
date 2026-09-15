<!-- BEGIN TLDRGRAPH -->
## TLDRGraph

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
<!-- END TLDRGRAPH -->
