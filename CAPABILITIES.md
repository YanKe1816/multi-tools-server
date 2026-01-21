# Capabilities Map

| Name | Path | Contract Endpoint | Determinism | Acceptance Status |
|------|------|-------------------|-------------|-------------------|
| verify_test | /tools/verify_test | /tools/verify_test/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| text_normalize | /tools/text_normalize | /tools/text_normalize/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| input_gate | /tools/input_gate | /tools/input_gate/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| schema_validate | /tools/schema_validate | /tools/schema_validate/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| schema_map | /tools/schema_map | /tools/schema_map/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| structured_error | /tools/structured_error | /tools/structured_error/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| capability_contract | /tools/capability_contract | /tools/capability_contract/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| rule_trace | /tools/rule_trace | /tools/rule_trace/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| schema_diff | /tools/schema_diff | /tools/schema_diff/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |
| enum_registry | /tools/enum_registry | /tools/enum_registry/contract | Deterministic; no side effects. | PASS (2026-01-21; Deterministic / Unified error / Contract aligned / Pytest passing) |

## Acceptance Results (2026-01-21)
- pytest: PASS.
- / reachable: PASS.
- /mcp reachable: PASS.
- Sample tool call:
  - Request: POST /tools/verify_test with {"text":"hello"}
  - Response: {"ok":true,"echo":"hello","length":5}
