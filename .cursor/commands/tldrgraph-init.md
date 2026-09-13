---
name: tldrgraph-init
description: Build or continue this repository's TLDRGraph architecture graph (layers, extraction, enrichment)
---

# TLDRGraph: build this repository's architecture graph

In Claude Code or Cursor, invoke `/tldrgraph-init`; in Codex CLI, select
`tldrgraph-init` from `/skills` or mention `$tldrgraph-init`.

One command handles extraction, feature-file scaffolding, and embeddings:

```bash
tldrgraph init
```

By default TLDRGraph does not ask another AI process to design architecture
layers, enrich every symbol, infer route links, or generate BPMN workflows. It
writes `.tldrgraph/features.yaml` and one `.tldrgraph/workflows/<feature_id>.yaml`
file per feature. The coding agent that ran `tldrgraph init` owns completing any
pending workflow files from source evidence.

Use exactly `tldrgraph init` for this workflow. Add `--yes` only if a non-agent
`needs_confirmation` response explicitly asks for approval. `--batch 200` means
all nodes in chunks; `--limit 200` means stop after only 200 nodes.
Never add `--limit`, `--agent-cli`, `--llm-links`, or `--embeddings off` unless the user
explicitly requests it.

## Feature Workflow Explorer artifacts

Every init run writes `.tldrgraph/features.yaml` and `.tldrgraph/workflows/<feature_id>.yaml`.
Workflow Explorer reads only those files; missing or invalid workflows show pending states.
Do not restore discovery through `discover_workflows()`, curated blueprints, route-link workflow discovery, route-link relations, or BPMN generation.
Each plain-language step needs source evidence. Start at the button/menu/form action and continue through client request, backend work, response payload, client handling, and final UI update when proven.
When `init` reports pending feature workflows:

1. Open `.tldrgraph/features.yaml`.
2. Open every pending `.tldrgraph/workflows/<feature_id>.yaml`.
3. Open the source files referenced in `evidence_nodes`; do not guess.
4. Replace `steps: []` with source-backed steps and set `status: generated`.
5. Run `tldrgraph init` again.

## `status: needs_layers`

This should only appear when the user explicitly opted into architecture AI with
`--agent-cli` or an older TLDRGraph build is running. Do not complete this
handoff unless the user asked for architecture layer design.

## `status: needs_confirmation`

This belongs to explicit `--agent-cli` enrichment. Ask before continuing.

## `status: needs_enrichment`

This should only appear when the user explicitly opted into architecture
enrichment with `--agent-cli` or an older TLDRGraph build is running. Do not
process enrichment batches unless the user asked for full graph enrichment.

**Copy every `id` verbatim.** A constructed id matches nothing, is dropped, and
gets reported back to you -- but the work is wasted.

**Never invent `fields` or `calls`.** Omit what you cannot verify in the code: an
empty list is a correct answer, a wrong `calls` entry becomes a real wrong edge.

## `status: needs_llm_links`

Read `.tldrgraph/llm_links_request.yaml`, open the referenced frontend/backend
files, then write `.tldrgraph/llm_links_response.yaml` as a YAML list of
`{source, target, confidence, frontend_evidence, backend_evidence, explanation}`.
Only include source-backed links with file and line evidence. Run `tldrgraph init`
again. This continuation state only appears when the user explicitly opted into
route-link inference with `--llm-links`.

## Once it says DONE

```bash
tldrgraph query "<feature in plain English>"
tldrgraph trace "<Source>" "<Target>"
tldrgraph layers
tldrgraph ui --serve
```

Read-only, and they never trigger enrichment. Full schema:
`.tldrgraph/AGENT_CONTRACT.md`.
