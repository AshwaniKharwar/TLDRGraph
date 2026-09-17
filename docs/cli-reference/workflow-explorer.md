# CLI reference

## `tldrgraph init [PATH] [--json]`

Inventories source files, validates the direct catalog index and independently
authored workflow files, and generates the explorer when every indexed feature
has a valid workflow.

## `tldrgraph refresh [PATH] [--json]`

Runs the same pipeline as `init` for an existing catalog. Use it after repository
source changes so the current catalog and explorer are validated or regenerated.

## `tldrgraph ui`

Generates standalone HTML. Use `--serve` for live source access, `--port` to
choose the local port, and `--no-open` to avoid opening a browser.

## `tldrgraph install`

Installs the contract and coding-agent workflow. `--all-agents` writes command
files for every supported agent.
