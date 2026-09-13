# TLDRGraph Agent Contract

**Audience: the coding agent with this repository open** (Codex, Claude Code, Cursor, Antigravity).

TLDRGraph builds an architectural graph from the graphify AST export. By default,
`tldrgraph init` does not ask AI to design architecture layers, enrich every
symbol, infer route links, or generate BPMN workflows. The only default AI-shaped
artifact is the saved Feature Workflow Explorer YAML, and it must stay backed by
real source evidence.

---

## Start here: `tldrgraph init`

One command handles extraction, saved feature workflows, and embeddings:

```bash
tldrgraph init
```

Use `--agent-cli` only when the user explicitly asks for AI-assisted architecture
layer design and all-symbol enrichment. Saved feature workflow generation is
independent and does not require `--agent-cli`.

| status | what it wants |
| --- | --- |
| `needs_layers` | Only process if the user explicitly opted into architecture AI with `--agent-cli`. |
| `needs_confirmation` | Only belongs to explicit `--agent-cli` enrichment. Ask before continuing. |
| `needs_enrichment` | Only process if the user explicitly asked for full graph enrichment. |
| `needs_embeddings` | Enrichment finished but the required dense model/index could not be built. Fix model access and rerun init. |
| `done` | Nothing left. Use `query` / `trace` / `layers`. |

`--json` gives you the same thing machine-readably. The sections below document the file
formats `init` reads and writes; the underlying `queue-enrichment` / `apply-enrichment`
commands remain available for scripting.

**Copy every `id` verbatim from the request.** A constructed id matches nothing, is
dropped, and will be reported back to you — but the work is wasted.

---

## Explicit Enrichment Loop

The legacy enrichment files below are for explicit `--agent-cli`,
`queue-enrichment`, or `apply-enrichment` work. Do not process them as part of
default Feature Workflow Explorer generation. Never add `--limit`,
`--agent-cli`, `--llm-links`, or `--embeddings off` unless the user explicitly
requests that behavior.

Request and response are **separate files**. Never write your answer back into
`enrichment_request.yaml`; it is regenerated on every run and your work would be lost.

| File | Written by | Read by |
| --- | --- | --- |
| `.tldrgraph/enrichment_request.yaml` (or `enrichment_request.json`) | `queue-enrichment` | you |
| `.tldrgraph/enrichment_response.yaml` (or `enrichment_response.json`) | **you** | `apply-enrichment` |
| `.tldrgraph/enrichment_cursor.json` | both commands | both commands |
| `.tldrgraph/enrichment_approval.json` | `init --yes` | later `init` runs |
| `.tldrgraph/pending_enrichment.json` | *(legacy)* | `apply-enrichment`, only if no response file exists |

---

## Feature Workflow Explorer artifacts

`tldrgraph init` also creates the saved workflow artifacts used by the visualizer:

| File | Written by | Read by |
| --- | --- | --- |
| `.tldrgraph/features.yaml` | `tldrgraph init` | Workflow Explorer |
| `.tldrgraph/workflows/<feature_id>.yaml` | `tldrgraph init` | Workflow Explorer |

The Workflow Explorer tab is intentionally file-driven. It must read only
`.tldrgraph/features.yaml` and `.tldrgraph/workflows/<feature_id>.yaml`; if those
files are missing, invalid, incomplete, or a feature has no generated workflow
yet, show an explicit empty or pending state.

Do **not** reintroduce Workflow Explorer fallback discovery through
`discover_workflows()`, curated workflow blueprints, route-link workflow
discovery, `llm_http_route_link`, `http_route_link`, `calls_endpoint`, or
BPMN-derived workflow generation. Graph views elsewhere may still show route
links or BPMN data, but saved feature workflows must remain independent.

Every saved workflow step must be simple enough for non-technical users and vibe
coders, and each step must carry source evidence: `node_id`, symbol, file, and
line/range. If the evidence is absent, mark the workflow pending instead of
guessing.

A saved feature workflow should describe the complete flow when evidence exists:
the exact user button/menu/form action, event handler, validation, client
request code, request payload construction, API route/controller,
middleware/auth, service or use-case logic, persistence/database, background
job, external system, response payload creation, client response parsing, state
update, navigation/toast/rendered result, and visible success or error handling.
Do not stop at only the frontend or only the backend when the source proves the
handoff, and do not collapse multiple proven source hops into one vague step.

---

## Request schema (`enrichment_request.yaml`)

```yaml
schema: codechakra/enrichment-request@1
generated_at: "2026-08-19T00:00:00+00:00"
response_file: .tldrgraph/enrichment_response.yaml
contract: .tldrgraph/AGENT_CONTRACT.md
progress:
  total_candidates: 1873   # un-enriched, non-utility nodes
  already_enriched: 12     # nodes that already carry an intent
  queued_now: 200          # entries in "nodes" below
  remaining_after: 1673    # still waiting after this batch is applied
nodes:
  - id: backend_src_applications_applications_controller_applicationscontroller
    label: ApplicationsController
    layer_id: api
    layer: "Layer 2: API Gateway"
    file: backend/src/applications/applications.controller.ts
    source_location: L31
    degree: 41             # in + out edges in the AST graph
    cross_layer_degree: 17 # of those, how many cross a layer boundary
    rank: 1                # 1 = highest priority in this batch
    existing_intent_source: heuristic  # "" when the node has no intent at all
```

`file` is repo-relative. `source_location` is graphify's line hint and may be `null`.
`layer_id` is the stable machine key (e.g. `cli`, `engine`, `storage`, `api`, `ui`).

`existing_intent_source` is `"heuristic"` when the node already carries an intent written
by the offline template enricher. That text was generated from the label and layer alone
— it has not read a line of source — so the node is still a candidate and your answer
should overwrite it. Applied answers are stamped `"agent"` and are never re-queued.

---

## Response schema (`enrichment_response.yaml` or `enrichment_response.json`)

A **YAML list** (preferred) or **JSON array** of objects:

```yaml
- id: backend_src_applications_applications_controller_applicationscontroller
  intent: |
    ### Pension Application Lifecycle Gateway
    REST gateway for the pension application lifecycle. Authorizes DEO/AAO/AO/DAG roles,
    dispatches cases to ApplicationsService and records status transitions.
  input_fields:
    - caseId
    - transitionPayload
    - remarks
    - sanctionOrderNo
  output_fields:
    - applicationStatus
    - disposition
  calls:
    - ApplicationsService
    - JwtAuthGuard
    - RolesGuard
    - pension_cases
```

Equivalent JSON format (also accepted from `.tldrgraph/enrichment_response.json` or `.tldrgraph/pending_enrichment.json`):
```json
[
  {
    "id": "backend_src_applications_applications_controller_applicationscontroller",
    "intent": "### Pension Application Lifecycle Gateway\nREST gateway for the pension application lifecycle. It authorizes roles and dispatches source-backed status transitions.",
    "input_fields": ["caseId", "transitionPayload", "remarks", "sanctionOrderNo"],
    "output_fields": ["applicationStatus", "disposition"],
    "calls": ["ApplicationsService", "JwtAuthGuard", "RolesGuard", "pension_cases"]
  }
]
```

| Key | Type | Meaning |
| --- | --- | --- |
| `id` | string, **required** | The node id, copied **verbatim** from the request. An id that is not in the graph is skipped silently. |
| `intent` | string (Markdown) | Markdown formatted 2-3 sentence explanation: what this symbol does, why it exists, and its source-backed behavior. Headings and list markers do not count as sentences. This is the text semantic search matches against. |
| `input_fields` | array of strings | Input parameters, arguments, request body payload attributes, query filters. |
| `output_fields` | array of strings | Return types, response models, emitted event names, or mutated state attributes. |
| `fields` | array of strings (legacy) | Supported for backwards compatibility (maps to input fields). |
| `calls` | array of strings or objects | Downstream symbols, files (`file:symbol`), or node IDs this symbol calls. Cross-layer bridges are created with 100% confidence. |
| `layer_id` | string (optional) | Explicitly reassign the architectural layer ID if the AST classification miscategorized it. |

`input_fields`, `output_fields`, and `calls` may be omitted or empty. An object with only `id` and `intent` is
valid and useful.

---

## Hard rules

1. **Open and read the actual source file before writing an intent.** You have the repo
   checked out; that is the entire reason this path exists. Read `file` (use
   `source_location` to find the symbol), and read enough of its imports and callees to
   describe what it really does. An intent paraphrased from the label is worse than no
   intent, because it poisons search with confident-sounding noise.

2. **Write every intent in 2-3 complete sentences.** Cover what the symbol does, why it
   exists, and its source-backed behavior. Markdown headings and list markers do not count
   as sentences.

3. **Do not invent fields or calls. Omit what you cannot verify in the code.** If you
   read the file and it handles three params, list three. Do not pad the list with what a
   symbol of that name "usually" has. `"fields": []` is a correct, honest answer.
   A wrong `calls` entry creates a real, wrong edge in the graph that later queries will
   follow.

4. **`calls` entries are resolved with 2-tier high precision.**
   - **Tier 1 (Exact Match, 100% confidence):** Exact symbol names (`ApplicationsService`),
     function names, node IDs, file paths (`calc.ts`), or database table names (`pension_cases`).
   - **Tier 2 (Vector Fallback):** Semantic search with a calibrated 0.35 score floor.

   | Good | Bad |
   | --- | --- |
   | `ApplicationsService` | `the application service` |
   | `calc.ts` | `some calculation helper` |
   | `pension_cases` | `the database` |
   | `JwtAuthGuard` | `auth stuff` |

   Prefer the exact symbol name, file name, or table/model name as it appears in the source.

5. **Copy `id` verbatim.** Do not normalize, shorten or re-case it.

6. **Answer only the nodes in the request.** Extra ids are ignored; missing ids just come
   back in a later batch.

7. **After full approval, never ask again for the same campaign.** Continue processing
   `needs_enrichment` batches until `status: done`. Do not silently add `--limit` or
   `--embeddings off`.

---

## Priority order in the queue

The queue is not arbitrary — a node that many things depend on is worth more of your
attention than a leaf. A node is a **candidate** when it sits outside `General / Utility`
and either has no intent at all, or has one that came from the offline template heuristic
(`enrichment_source: "heuristic"`, i.e. nobody read the source). Candidates are sorted by:

1. **`cross_layer_degree` descending** — neighbours that sit in a *different* layer.
   These are the seams TLDRGraph exists to describe, and they are exactly where the AST
   alone is weakest.
2. **`degree` descending** — total in + out edges. Hub nodes first.
3. **node id ascending** — only to make the ordering deterministic.

Both degrees are computed from the live graph. (The `degree` key that graphify emits is
absent, so anything reading `node["degree"]` from the raw export sees `0`; TLDRGraph
recomputes it and stamps it back into `.tldrgraph/graph.json`.)

---

## Paging and progress

`queue-enrichment` remembers what it has handed out in `.tldrgraph/enrichment_cursor.json`:

- `applied` — ids successfully merged by `apply-enrichment`. Never re-queued.
- `queued` — ids handed out but not yet applied ("in flight"). Skipped by default.

So running `queue-enrichment` twice in a row **advances** to the next batch instead of
repeating. Two escape hatches:

- `--requeue` — also hand out in-flight ids again (use when a batch was abandoned).
- `--reset` — clear all progress and start again from the highest-priority node.
- `--limit 0` — no cap; queue every remaining candidate at once.

---

## What `apply-enrichment` does with your answer

For each object it can match to a node:

1. sets `intent`, rewrites `summary` to `"<layer>: <label> - <intent>"`, sets `fields`;
2. writes the node into the SQLite hash-gate cache, keyed by a content signature, so the
   work survives re-scans and is not redone until the file actually changes;
3. resolves every `calls` entry through the vector index and, above the `0.35` floor,
   adds a `cross_layer_link` edge;
4. re-indexes and persists `.tldrgraph/graph.json` plus `.tldrgraph/layers.yaml`.

It then records the ids in the cursor so the next `queue-enrichment` moves on.

---

## Related commands

```bash
tldrgraph init                         # everything, resumable (scan/enrich are aliases)
tldrgraph query "pension approval"     # semantic search + end-to-end flow trace
tldrgraph trace AaoDeskView pension_cases
tldrgraph layers                       # node counts per layer
tldrgraph dead-code --status candidate # nodes worth a human/agent review
```

`query`, `trace`, `layers` and `dead-code` are read commands: they never trigger
enrichment.

### `dead-code` is a review list, not a delete list

`dead-code` reports `dead_code_status` per node:

| Status | Means |
| --- | --- |
| `live` | Reached by something. |
| `entry_point` | A root: route handler, CLI entry, cron job, exported public API. |
| `candidate` | **Worth reviewing.** Nothing observed reaches it — which is evidence, not proof. |
| `unreviewed` | **Not enough evidence to conclude anything.** Never treat as removable. |

TLDRGraph has no delete capability and will not gain one. Reflection, DI containers,
string-built routes, template references and test-only entry points all produce nodes the
static graph cannot see. Confirm with the source before removing anything.
