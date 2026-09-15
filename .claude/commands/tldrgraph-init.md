---
name: tldrgraph-init
description: Build or refresh source-backed feature workflows
---

# TLDRGraph: build the source-backed workflow catalog

Run exactly:

```bash
tldrgraph init
```

When the status is `needs_feature_workflows`:

1. Read `.tldrgraph/feature_workflows_request.yaml` completely.
2. Spawn a source-reading subagent and delegate the entire request.
3. Have it inspect the repository and write the requested v3 response to
   `.tldrgraph/feature_workflows_response.yaml`.
4. Run `tldrgraph init` again.

Continue until the status is `done`.
