# Installation

```bash
pip install tldrgraph
cd your-project
tldrgraph install
```

The installer adds a managed section to `AGENTS.md`, installs the
`tldrgraph-init` workflow, writes `.tldrgraph/AGENT_CONTRACT.md`, and updates the
generated-state block in `.gitignore`.

TLDRGraph requires Python 3.10 or newer. Its runtime dependencies are Click and
PyYAML.
