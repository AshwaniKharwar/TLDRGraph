# Quickstart

Run inside a coding-agent session with the project open:

```bash
tldrgraph init
```

If the status is `needs_feature_workflows`, let the installed workflow delegate
the request to a source-reading subagent. After its response is saved, run
`tldrgraph init` again. A successful run reports `done`.

```bash
tldrgraph ui --serve
```

Search the catalog, select a workflow, click a step, and open any cited evidence
range in the live source viewer.
