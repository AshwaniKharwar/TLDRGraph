# Coding-agent integration

`tldrgraph install` writes one shared workflow for supported coding agents. It
runs `tldrgraph init`, delegates the generated request to a source-reading
subagent, and reruns initialization after the response is written.

Use `--all-agents` to install command files for every supported tool.
