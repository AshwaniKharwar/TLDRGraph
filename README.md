# TLDRGraph

TLDRGraph turns a repository into a source-backed feature catalog and interactive
Workflow Explorer. Your coding agent reads the repository, identifies meaningful
product and technical capabilities, and records every displayed step with file,
symbol, and line-range evidence.

TLDRGraph does not run an AI process itself and does not infer workflows from a
static graph. It coordinates a transparent file handshake with the coding agent
that already has your repository open.

## Install

```bash
pip install tldrgraph
```

## Generate a catalog

Run this inside a supported coding-agent session:

```bash
tldrgraph init
```

When `init` reports `needs_feature_workflows`, the installed agent workflow reads
`.tldrgraph/feature_workflows_request.yaml`, delegates repository inspection to a
source-reading subagent, and writes `.tldrgraph/feature_workflows_response.yaml`.
Run `tldrgraph init` again to validate and apply the response.

The final artifacts are:

- `.tldrgraph/features.yaml`
- `.tldrgraph/workflows/<feature_id>.yaml`
- `.tldrgraph/TLDRGRAPH_VISUALIZER.html`

## Explore

```bash
tldrgraph ui --serve
```

The standalone browser application groups product and technical capabilities,
draws each proven workflow, and opens cited source ranges from the repository.

## CLI

```text
tldrgraph init [PATH] [--json]
tldrgraph ui [--path PATH] [--serve] [--port PORT] [--open|--no-open]
tldrgraph install [--path PATH] [--all-agents]
```

Version 0.3 is a breaking, workflow-only release. Earlier graph-based commands
and v1/v2 generated artifacts are not supported; run `tldrgraph init` to produce
the v3 catalog.
