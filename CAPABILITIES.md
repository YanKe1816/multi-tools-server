# Capabilities Map

| Name | Path | Description | Status |
|------|------|-------------|--------|
| text_normalize | /tools/text_normalize | Deterministic normalization for newlines, whitespace, blank lines, and tabs. | active |
| schema_validate | /tools/schema_validate | Validate data against a limited JSON Schema subset; returns valid/errors or error. | active |
| schema_map | /tools/schema_map | Object mapping with rename/drop/default/require; returns ok/data/meta or ok/errors. | active |

Notes:
- This table is the single source of truth for capabilities merged into `main`.
- Only accepted capabilities are listed here.
- Experimental or verification-only tools are excluded unless formally accepted.
