# Agent contract

The direct-artifact contract uses two v4 schemas:

- `tldrgraph/features@4`
- `tldrgraph/feature-workflow@4`

The active agent writes the catalog index with the current `source_hash`; each
assigned feature worker writes its own workflow file with that same hash. A stale
hash, unsafe path, missing workflow, or invalid line range is rejected without
replacing valid artifacts.
