# Coding-agent integration

`tldrgraph install` writes one shared workflow for supported coding agents. It
runs `tldrgraph init`, writes a v4 catalog index, coordinates one source-reading
subagent per indexed feature, and reruns initialization after workers independently
write their workflow files.

Use `--all-agents` to install command files for every supported tool.
