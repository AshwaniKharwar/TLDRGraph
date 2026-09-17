# TLDRGraph

TLDRGraph turns a repository into a source-backed feature catalog and interactive
Workflow Explorer. Your coding agent reads the repository, identifies meaningful
product and technical capabilities, and records every displayed step with file,
symbol, and line-range evidence.

TLDRGraph does not run an AI process itself and does not infer workflows from a
static graph. It coordinates direct catalog and workflow artifacts with the
coding agent that already has your repository open.

## Install

```bash
pip install tldrgraph
```

## Generate a catalog

Run this inside a supported coding-agent session:

```bash
tldrgraph init
```

When `init` reports `needs_feature_workflows`, it includes the current source
hash. The active agent identifies feature outcomes and immediately writes the v4
`.tldrgraph/features.yaml` index. It delegates one indexed feature to each
source-reading subagent; each worker writes only its own v4 workflow file. Run
`tldrgraph init` again to validate the artifacts and generate the explorer.

When repository source changes after a catalog exists, run `tldrgraph refresh`
instead. It performs the same validation and generation flow while making the
update intent explicit.

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
tldrgraph refresh [PATH] [--json]
tldrgraph ui [--path PATH] [--serve] [--port PORT] [--open|--no-open]
tldrgraph install [--path PATH] [--all-agents]
```

Version 0.3 is a breaking, workflow-only release. Earlier graph-based commands
and v1/v2 generated artifacts are not supported; run `tldrgraph init` to create
the current catalog, then `tldrgraph refresh` after later source changes.
