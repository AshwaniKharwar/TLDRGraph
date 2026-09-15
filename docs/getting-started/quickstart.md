# Quickstart

Run inside a coding-agent session with the project open:

```bash
tldrgraph init
```

If the status is `needs_feature_workflows`, let the active agent identify feature
outcomes and write the v4 `features.yaml` index first. It then spawns one
source-reading subagent per indexed feature. Each worker writes only its own v4
workflow file. Run `tldrgraph init` again; a successful run reports `done`.

```bash
tldrgraph ui --serve
```

Search the catalog, select a workflow, click a step, and open any cited evidence
range in the live source viewer.
