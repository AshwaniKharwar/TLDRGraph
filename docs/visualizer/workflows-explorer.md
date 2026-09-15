# Workflow Explorer

The explorer reads only the v3 feature manifest and workflow YAML files. It shows:

- ordered product and technical capability areas;
- generated, partial, and pending status;
- a pannable and zoomable workflow canvas;
- vertical flowchart rendering by default, with process boxes, decision diamonds,
  labeled alternate paths, and branch reconvergence;
- source evidence for every displayed step;
- live source through `ui --serve` or a browser folder grant.

When repository contents no longer match the catalog's `source_hash`, the last
catalog remains visible with a stale warning. Run `tldrgraph init` to refresh it.

Click a process box, a decision diamond, or an alternate-path box to inspect its
source-backed detail and open the cited source range. The canvas remains
pannable and zoomable, and the horizontal layout remains available as an
alternate view.
