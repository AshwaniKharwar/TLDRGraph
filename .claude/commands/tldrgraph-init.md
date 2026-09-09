---
name: tldrgraph-init
description: Build or continue this repository's TLDRGraph architecture graph (layers, extraction, enrichment)
---

# TLDRGraph: build this repository's architecture graph

In Claude Code or Cursor, invoke `/tldrgraph-init`. In Codex CLI, type `/skills`
and select `tldrgraph-init`, or mention `$tldrgraph-init` directly.

One command handles layer design, extraction, enrichment, LLM route links, and embeddings:

```bash
tldrgraph init
```

By default TLDRGraph detects `claude`, `cursor-agent`, or `gemini`, asks once before enrichment token spend, processes every
eligible node in batches of 200, and downloads/builds the local embedding model.
Use `--yes` for approval, `--batch N` for batch size, `--embeddings off|auto|on`,
`--no-llm-links` to skip LLM frontend/backend route inference, or `--no-agent-cli`
for manual file handoff.

After the user approves the full run, use exactly `tldrgraph init --yes`. The
approval is saved for the current candidate set, so later `tldrgraph init` calls
must continue without asking again. `--batch 200` means all nodes in 200-node
batches; `--limit 200` means stop after only 200 nodes. Never add `--limit` or
`--embeddings off` unless the user explicitly requests a partial or no-embedding run.

## Completion contract for agents

Once the user approves a full enrichment campaign, you are not done until one of
these terminal states occurs:

- `tldrgraph init` reports `status: done`.
- Dense embeddings finish, or `init` explicitly reports that embeddings are
  unavailable while preserving a queryable graph.
- A real blocking error occurs that requires user action, and you report the
  exact command/output that blocked continuation.

These are **not** terminal states:

- `status: needs_enrichment`
- `NEXT ACTION`
- "nodes remaining"
- "batches remaining"
- "applied N enrichment entries"

For every non-terminal enrichment state, immediately continue the loop:

1. Read `.tldrgraph/enrichment_request.yaml`.
2. Open the source file for every requested node.
3. Write `.tldrgraph/enrichment_response.yaml`.
4. Run `tldrgraph init` again.
5. Repeat until a terminal state occurs.

Do not end the task with a progress-only summary such as "I applied 400 entries
and 1,438 remain." That is an incomplete run, not a final answer. If nested-agent
protection prevents a CLI from launching another agent, you are the enrichment
agent and must process the batch yourself.

If no supported agent is available or dense embeddings cannot be built, `init`
preserves the graph and prints a resumable status. It never guesses source intent,
route links, or architectural layers.

## `status: needs_layers`

TLDRGraph ships **no layer templates** and will not invent an architecture.
Design one from this repository.

1. Read `.tldrgraph/propose_layers_request.json`. It carries the symbols and
   files extraction already found -- a starting point, not a substitute for
   opening the code.
2. **Open real source files**: entry points first, then a representative file
   from each cluster in the evidence. Work out what this codebase actually does
   and where responsibility changes hands.
3. Write `.tldrgraph/propose_layers_response.json`:

```json
{
  "utility_id": "<id of your catch-all layer>",
  "layers": [
    {
      "id": "short_machine_id",
      "name": "Layer 1: Human Friendly Name",
      "order": 1,
      "description": "One sentence on what lives here",
      "rules": [
        {"file_contains": ["substring"], "exclude_file": ["optional"]},
        {"label_contains": ["SymbolNamePart"]}
      ]
    }
  ]
}
```

4. Run `tldrgraph init` again; it continues with enrichment and embeddings.

### Rules that hold for any answer

- 3 to 6 layers, plus exactly one catch-all whose `id` equals `utility_id` and
  whose `rules` are `[]`.
- Unique `id` and `name` per layer; sequential integer `order` from 1.
- Rule keys: `file_contains`, `exclude_file`, `path_regex`, `label_contains`,
  `exclude_label`, `label_ends_with`, `type_in`, `id_prefix`. Values are lists of
  strings. Rules are evaluated in `order` and the first match wins.
- Derive rules from paths and symbol names you actually saw. A rule matching
  nothing is worse than no rule; a rule matching everything collapses the map.

## `status: needs_confirmation`

The output shows how many nodes need enrichment and how many agent round-trips
that implies. **Ask the user whether to proceed, and show them that estimate.**
Do not decide for them.

- They agree: `tldrgraph init --yes` saves approval for the full campaign
- Smaller first pass: `tldrgraph init --yes --limit 100`
- They decline: stop. The graph is already built and queryable.

## `status: needs_enrichment`

1. Read `.tldrgraph/enrichment_request.yaml`.
2. **Open the source file of every node in it.** This is the entire point: an
   intent paraphrased from a symbol name poisons semantic search with
   confident-sounding noise.
3. Write `.tldrgraph/enrichment_response.yaml` -- a *different* file from the
   request, which is regenerated on every run:

```yaml
- id: "<node id copied verbatim from the request>"
  intent: |
    What this symbol does, why it exists, and its execution logic.
  input_fields: [caseId, remarks]
  output_fields: [status, disposition]
  calls: [ApplicationsService, pension_cases]
```

Every `intent` must contain **2-3 complete sentences** covering what the symbol does,
why it exists, and its source-backed behavior. Markdown headings and list markers do not
count as sentences.

4. Run `tldrgraph init` again. Approval is saved; process any next
   `needs_enrichment` batch immediately without asking the user again until
   `status: done` or `needs_llm_links`.

Inside an existing Codex/Claude/Cursor session, nested-agent protection may stop
the CLI from launching a second agent. In that case **you are the enrichment
agent**: process every 200-node batch yourself. A `needs_enrichment` status is a
continuation instruction, not a reason to stop or request confirmation.

**Copy every `id` verbatim.** A constructed id matches nothing, is dropped, and
gets reported back to you -- but the work is wasted.

**Never invent `fields` or `calls`.** Omit what you cannot verify in the code: an
empty list is a correct answer, a wrong `calls` entry becomes a real wrong edge.

## `status: needs_llm_links`

1. Read `.tldrgraph/llm_links_request.yaml`.
2. Open the referenced frontend and backend source files.
3. Write `.tldrgraph/llm_links_response.yaml` as a YAML list of
   `{source, target, confidence, frontend_evidence, backend_evidence, explanation}`.
   Only include source-backed links with file and line evidence.
4. Run `tldrgraph init` again, or use `--no-llm-links` to skip this optional stage.

## Once it says DONE

```bash
tldrgraph query "<feature in plain English>"
tldrgraph trace "<Source>" "<Target>"
tldrgraph layers
tldrgraph ui --serve
```

Read-only, and they never trigger enrichment. Full schema:
`.tldrgraph/AGENT_CONTRACT.md`.
