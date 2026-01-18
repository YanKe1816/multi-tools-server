# Capabilities Map

| Name | Path | Description | Status |
|------|------|-------------|--------|
| text_normalize | /tools/text_normalize | Deterministic normalization for newlines, whitespace, blank lines, and tabs. | active |
| schema_validate | /tools/schema_validate | Validate data against a limited JSON Schema subset; returns valid/errors or error. | active |
| schema_map | /tools/schema_map | Object mapping with rename/drop/default/require; returns ok/data/meta or ok/errors. | active |
| input_gate | /tools/input_gate | Pre-flight input checks for type/size/structure; returns pass or errors; error codes: TYPE_NOT_ALLOWED, JSON_TOO_LARGE, STRING_TOO_SHORT, STRING_TOO_LONG, ARRAY_TOO_LONG, OBJECT_TOO_DEEP, OBJECT_TOO_MANY_KEYS, RULES_INVALID, MODE_INVALID. | active |
| structured_error | /tools/structured_error | Normalize error inputs into a structured error envelope; returns ok=false with class/retryable/severity/where/fingerprint. | active |

Notes:
- This table is the single source of truth for capabilities merged into `main`.
- Only accepted capabilities are listed here.
- Experimental or verification-only tools are excluded unless formally accepted.
- structured_error contract: input includes source/tool/stage/version, error code/message/type/http_status/path/details, and policy (max_message_length/include_raw_message). Output is ok=false with error class/code/message/retryable/severity/where/http_status/fingerprint or an error with codes POLICY_INVALID, SOURCE_INVALID, ERROR_INVALID.
- structured_error rules: class is derived from error.code/http_status in a fixed priority order; retryable and severity are mapped from class; message is optionally included and truncated; fingerprint is sha256(tool|stage|class|code|http_status) first 16 hex chars.
- structured_error acceptance examples: (1) RULES_INVALID -> class=RULES_INVALID, retryable=false. (2) http_status=429 -> class=RATE_LIMIT, retryable=true. (3) http_status=503 or code contains UPSTREAM -> class=UPSTREAM, retryable=true.
