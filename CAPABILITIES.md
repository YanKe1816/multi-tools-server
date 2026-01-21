# Capabilities Map

| Name | Path | Description | Status |
|------|------|-------------|--------|
| text_normalize | /tools/text_normalize | Deterministic normalization for newlines, whitespace, blank lines, and tabs. | active |
| schema_validate | /tools/schema_validate | Validate data against a limited JSON Schema subset; returns valid/errors or error. | active |
| schema_map | /tools/schema_map | Object mapping with rename/drop/default/require; returns ok/data/meta or ok/errors. | active |
| input_gate | /tools/input_gate | Pre-flight input checks for type/size/structure; returns pass or errors; error codes: TYPE_NOT_ALLOWED, JSON_TOO_LARGE, STRING_TOO_SHORT, STRING_TOO_LONG, ARRAY_TOO_LONG, OBJECT_TOO_DEEP, OBJECT_TOO_MANY_KEYS, RULES_INVALID, MODE_INVALID. | active |
| structured_error | /tools/structured_error | Normalize error inputs into a structured error envelope; returns ok=false with class/retryable/severity/where/fingerprint. | active |
| capability_contract | /tools/capability_contract | Validate/normalize a capability contract; returns ok true with contract or ok false with errors. | active |
| rule_trace | /tools/rule_trace | Normalize run/input/output summaries and rule hits into a trace envelope; returns ok true with trace. | active |
| schema_diff | /tools/schema_diff | Deterministically diff two JSON Schemas and return added/removed/changed paths. | active |
| enum_registry | /tools/enum_registry | Deterministically normalize and validate enum sets; returns matched/missing/duplicates. | active |

## Capability Contracts
Capability contracts provide explicit, deterministic input/output/error shapes for each tool and are used for governance and tool signing. Each tool exposes a contract endpoint and is also listed in the global contracts registry.

| Name | Tool Path | Contract Endpoint |
|------|-----------|-------------------|
| verify_test | /tools/verify_test | /tools/verify_test/contract |
| text_normalize | /tools/text_normalize | /tools/text_normalize/contract |
| input_gate | /tools/input_gate | /tools/input_gate/contract |
| schema_validate | /tools/schema_validate | /tools/schema_validate/contract |
| schema_map | /tools/schema_map | /tools/schema_map/contract |
| structured_error | /tools/structured_error | /tools/structured_error/contract |
| capability_contract | /tools/capability_contract | /tools/capability_contract/contract |
| rule_trace | /tools/rule_trace | /tools/rule_trace/contract |
| schema_diff | /tools/schema_diff | /tools/schema_diff/contract |
| enum_registry | /tools/enum_registry | /tools/enum_registry/contract |

Notes:
- This table is the single source of truth for capabilities merged into `main`.
- Only accepted capabilities are listed here.
- Experimental or verification-only tools are excluded unless formally accepted.
- structured_error contract: input includes source/tool/stage/version, error code/message/type/http_status/path/details, and policy (max_message_length/include_raw_message). Output is ok=false with error class/code/message/retryable/severity/where/http_status/fingerprint or an error with codes POLICY_INVALID, SOURCE_INVALID, ERROR_INVALID.
- structured_error rules: class is derived from error.code/http_status in a fixed priority order; retryable and severity are mapped from class; message is optionally included and truncated; fingerprint is sha256(tool|stage|class|code|http_status) first 16 hex chars.
- structured_error acceptance examples: (1) RULES_INVALID -> class=RULES_INVALID, retryable=false. (2) http_status=429 -> class=RATE_LIMIT, retryable=true. (3) http_status=503 or code contains UPSTREAM -> class=UPSTREAM, retryable=true.
- capability_contract contract: inputs/outputs schemas must be objects; forbidden flags must all be true; behavior.deterministic must be true. Output is ok true with contract (normalized in normalize mode) or ok false with errors; invalid inputs return error codes SCHEMA_INVALID or MODE_INVALID.
- capability_contract rules: normalize mode fills missing forbidden/behavior defaults as true and stabilizes key order with sort_keys.
- capability_contract acceptance examples: (1) forbidden all true + deterministic true -> ok true. (2) contract.forbidden.judgement=false -> ok false with FORBIDDEN_VIOLATION. (3) inputs.schema not object -> error SCHEMA_INVALID.
- rule_trace contract: input includes run metadata, input summary, result (ok, output_summary, rules_hit, error), and policy (max_message_length, hash_alg). Output is ok true with trace containing run/input/output/rules_hit/status; errors return POLICY_INVALID.
- rule_trace rules: hash_alg must be sha256; messages are truncated to max_message_length; status is error > rejected > success based on result.error and rules_hit kind=reject.
- rule_trace acceptance examples: (1) ok true and no reject -> status success. (2) ok false with reject rule -> status rejected. (3) policy.hash_alg invalid -> error POLICY_INVALID.
