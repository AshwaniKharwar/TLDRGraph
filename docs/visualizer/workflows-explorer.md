# Workflow Explorer

The explorer reads only the v3 feature manifest and workflow YAML files. It shows:

- ordered product and technical capability areas;
- generated, partial, and pending status;
- a pannable and zoomable workflow canvas;
- source evidence for every displayed step;
- live source through `ui --serve` or a browser folder grant.

When repository contents no longer match the catalog's `source_hash`, the last
catalog remains visible with a stale warning. Run `tldrgraph init` to refresh it.
