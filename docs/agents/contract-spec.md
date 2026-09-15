# Agent contract

The handshake uses four v3 schemas:

- `tldrgraph/feature-workflows-request@3`
- `tldrgraph/feature-workflows-response@3`
- `tldrgraph/features@3`
- `tldrgraph/feature-workflow@3`

The request contains the current `source_hash`, deterministic source inventory,
instructions, and exact response shape. Responses with a stale hash, unsafe path,
missing file, or invalid line range are rejected without replacing the last
accepted catalog.
