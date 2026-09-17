# Coding-agent integration

`tldrgraph install` writes one shared workflow for supported coding agents. It
runs `tldrgraph init` to create a v4 catalog index, coordinates one source-reading
subagent per indexed feature, and reruns the same command after workers independently
write their workflow files. Use `tldrgraph refresh` to update an existing catalog
after repository source changes.

For Codex, installation also provides `/tldrgraph-init` for first catalogs and
`/tldrgraph-refresh` for existing catalogs that need updating.

Use `--all-agents` to install command files for every supported tool.
