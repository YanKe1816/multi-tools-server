# multi-tools-server

A minimal multi-tool server and governance shell for exposing deterministic tools
under `/tools/*`.

## OpenAI review step
- MCP Server URL: https://multi-tools-server.onrender.com/mcp
- Scan Tools should find: verify_test (and future tools)
- `/mcp` is the capability discovery and platform scanning entry point
- `/mcp` returns the current `/tools/*` list with `name`, `path`, and `description`
- `verify_test` is a stability check tool
- `text_normalize` is the first formal capability
- `schema_validate` validates data against a limited JSON Schema subset
- `schema_map` maps objects deterministically using explicit paths
- `input_gate` performs pre-flight input checks with fixed rules
- `structured_error` normalizes error inputs into a structured error envelope
- `capability_contract` validates or normalizes capability contracts for governance
- `rule_trace` normalizes execution traces for governance and audit
- `schema_diff` diffs two JSON Schemas into added/removed/changed paths

### Example requests
```bash
curl https://multi-tools-server.onrender.com/mcp
```

```bash
curl -X POST https://multi-tools-server.onrender.com/tools/verify_test \
  -H "Content-Type: application/json" \
  -d '{"text":"hello"}'
```

### Examples (text_normalize)

1) Newline normalization

Request:
```json
{"text":"line1\r\nline2\rline3\n"}
```

Response:
```json
{
  "text": "line1\nline2\nline3\n",
  "meta": {
    "original_length": 19,
    "normalized_length": 18,
    "changes": ["normalized_newlines"]
  }
}
```

2) Blank line collapsing

Request:
```json
{"text":"a\n\n\n\nb"}
```

Response:
```json
{
  "text": "a\n\n\nb",
  "meta": {
    "original_length": 6,
    "normalized_length": 5,
    "changes": ["collapsed_blank_lines"]
  }
}
```

3) Error shape (empty text)

Request:
```json
{"text":""}
```

Response:
```json
{
  "error": {
    "code": "TEXT_EMPTY",
    "message": "Text is empty."
  }
}
```

### Examples (schema_validate)

1) Valid data

Request:
```json
{
  "schema": {
    "type": "object",
    "properties": {
      "name": { "type": "string", "minLength": 1 }
    },
    "required": ["name"]
  },
  "data": { "name": "Ada" }
}
```

Response:
```json
{
  "valid": true,
  "errors": []
}
```

2) Missing required field

Request:
```json
{
  "schema": {
    "type": "object",
    "properties": {
      "name": { "type": "string", "minLength": 1 }
    },
    "required": ["name"]
  },
  "data": {}
}
```

Response:
```json
{
  "valid": false,
  "errors": ["$.name: required"]
}
```

3) Unsupported schema keyword ($ref)

Request:
```json
{
  "schema": {
    "$ref": "#/definitions/name"
  },
  "data": { "name": "Ada" }
}
```

Response:
```json
{
  "error": {
    "code": "SCHEMA_UNSUPPORTED",
    "message": "Unsupported schema keyword: $ref."
  }
}
```

### Examples (schema_map)

1) Rename + defaults (ok=true)

Request:
```json
{
  "data": { "user": { "name": "Ada" } },
  "mapping": {
    "rename": { "user.name": "profile.display_name" },
    "defaults": { "profile.active": true },
    "drop": [],
    "require": ["profile.display_name"]
  },
  "mode": "strict"
}
```

Response:
```json
{
  "ok": true,
  "data": {
    "user": {},
    "profile": {
      "display_name": "Ada",
      "active": true
    }
  },
  "meta": {
    "applied": [
      "rename:user.name->profile.display_name",
      "defaults:profile.active"
    ]
  }
}
```

2) Require missing (ok=false)

Request:
```json
{
  "data": { "user": {} },
  "mapping": {
    "rename": {},
    "defaults": {},
    "drop": [],
    "require": ["user.name"]
  },
  "mode": "strict"
}
```

Response:
```json
{
  "ok": false,
  "errors": [
    {
      "path": "user.name",
      "code": "REQUIRED_MISSING",
      "message": "Required path is missing."
    }
  ]
}
```

3) Strict rename source missing (ok=false)

Request:
```json
{
  "data": { "user": {} },
  "mapping": {
    "rename": { "user.name": "profile.display_name" },
    "defaults": {},
    "drop": [],
    "require": []
  },
  "mode": "strict"
}
```

Response:
```json
{
  "ok": false,
  "errors": [
    {
      "path": "user.name",
      "code": "SOURCE_PATH_MISSING",
      "message": "Rename source path is missing."
    }
  ]
}
```

### Examples (input_gate)

1) Valid input (pass=true)

Request:
```json
{
  "input": { "name": "Ada" },
  "rules": {
    "max_size": 200,
    "allow_types": ["object"],
    "string": { "min_length": 0, "max_length": 10 },
    "object": { "max_depth": 2, "max_keys": 5 },
    "array": { "max_length": 3 }
  },
  "mode": "strict"
}
```

Response:
```json
{ "pass": true }
```

2) String too long

Request:
```json
{
  "input": "toolong",
  "rules": {
    "max_size": 200,
    "allow_types": ["string"],
    "string": { "min_length": 0, "max_length": 3 },
    "object": { "max_depth": 1, "max_keys": 1 },
    "array": { "max_length": 1 }
  },
  "mode": "strict"
}
```

Response:
```json
{
  "pass": false,
  "errors": [
    { "code": "STRING_TOO_LONG", "path": "$", "message": "String length exceeds max_length." }
  ]
}
```

3) Object too deep

Request:
```json
{
  "input": { "a": { "b": { "c": 1 } } },
  "rules": {
    "max_size": 200,
    "allow_types": ["object"],
    "string": { "min_length": 0, "max_length": 10 },
    "object": { "max_depth": 2, "max_keys": 10 },
    "array": { "max_length": 10 }
  },
  "mode": "strict"
}
```

Response:
```json
{
  "pass": false,
  "errors": [
    { "code": "OBJECT_TOO_DEEP", "path": "$", "message": "Object depth exceeds max_depth." }
  ]
}
```

4) Invalid rules

Request:
```json
{
  "input": "ok",
  "rules": {
    "max_size": "large",
    "allow_types": ["string"],
    "string": { "min_length": 0, "max_length": 10 },
    "object": { "max_depth": 2, "max_keys": 10 },
    "array": { "max_length": 10 }
  },
  "mode": "strict"
}
```

Response:
```json
{
  "error": { "code": "RULES_INVALID", "message": "Rules are invalid." }
}
```

### Examples (structured_error)

1) RULES_INVALID

Request:
```json
{
  "source": { "tool": "schema_map", "stage": "rename", "version": "0.1.0" },
  "error": {
    "code": "RULES_INVALID",
    "message": "Rules are invalid.",
    "type": "ValueError",
    "http_status": 400,
    "path": "mapping.rename",
    "details": {}
  },
  "policy": { "max_message_length": 300, "include_raw_message": true }
}
```

Response:
```json
{
  "ok": false,
  "error": {
    "class": "RULES_INVALID",
    "code": "RULES_INVALID",
    "message": "Rules are invalid.",
    "retryable": false,
    "severity": "low",
    "where": { "tool": "schema_map", "stage": "rename", "path": "mapping.rename" },
    "http_status": 400,
    "fingerprint": "8dab2ff1ac8f5b45"
  }
}
```

2) http_status=429 -> RATE_LIMIT

Request:
```json
{
  "source": { "tool": "input_gate", "stage": "size", "version": "0.1.0" },
  "error": {
    "code": "RATE_LIMIT",
    "message": "Too many requests.",
    "type": "HTTPError",
    "http_status": 429,
    "path": "",
    "details": {}
  },
  "policy": { "max_message_length": 300, "include_raw_message": true }
}
```

Response:
```json
{
  "ok": false,
  "error": {
    "class": "RATE_LIMIT",
    "code": "RATE_LIMIT",
    "message": "Too many requests.",
    "retryable": true,
    "severity": "medium",
    "where": { "tool": "input_gate", "stage": "size", "path": "" },
    "http_status": 429,
    "fingerprint": "9bdd6c78b259973c"
  }
}
```

3) http_status=503 -> UPSTREAM

Request:
```json
{
  "source": { "tool": "schema_validate", "stage": "validate", "version": "0.1.0" },
  "error": {
    "code": "UPSTREAM_TIMEOUT",
    "message": "Upstream timed out.",
    "type": "TimeoutError",
    "http_status": 503,
    "path": "",
    "details": {}
  },
  "policy": { "max_message_length": 300, "include_raw_message": true }
}
```

Response:
```json
{
  "ok": false,
  "error": {
    "class": "UPSTREAM",
    "code": "UPSTREAM_TIMEOUT",
    "message": "Upstream timed out.",
    "retryable": true,
    "severity": "medium",
    "where": { "tool": "schema_validate", "stage": "validate", "path": "" },
    "http_status": 503,
    "fingerprint": "496ba049e95816ba"
  }
}
```

### Examples (capability_contract)

1) Valid contract (ok=true)

Request:
```json
{
  "capability": { "name": "schema_map", "path": "/tools/schema_map", "version": "0.1.0" },
  "contract": {
    "inputs": { "schema": { "type": "object" } },
    "outputs": { "schema": { "type": "object" } },
    "forbidden": { "network": true, "storage": true, "side_effects": true, "judgement": true },
    "behavior": { "deterministic": true, "idempotent": true }
  },
  "mode": "validate"
}
```

Response:
```json
{
  "ok": true,
  "contract": {
    "inputs": { "schema": { "type": "object" } },
    "outputs": { "schema": { "type": "object" } },
    "forbidden": { "network": true, "storage": true, "side_effects": true, "judgement": true },
    "behavior": { "deterministic": true, "idempotent": true }
  }
}
```

2) Forbidden violation (ok=false)

Request:
```json
{
  "capability": { "name": "schema_map", "path": "/tools/schema_map", "version": "0.1.0" },
  "contract": {
    "inputs": { "schema": { "type": "object" } },
    "outputs": { "schema": { "type": "object" } },
    "forbidden": { "network": true, "storage": true, "side_effects": true, "judgement": false },
    "behavior": { "deterministic": true, "idempotent": true }
  },
  "mode": "validate"
}
```

Response:
```json
{
  "ok": false,
  "errors": [
    {
      "path": "contract.forbidden.judgement",
      "code": "FORBIDDEN_VIOLATION",
      "message": "Forbidden flag must be true."
    }
  ]
}
```

3) Invalid inputs schema (error)

Request:
```json
{
  "capability": { "name": "schema_map", "path": "/tools/schema_map", "version": "0.1.0" },
  "contract": {
    "inputs": { "schema": "not-an-object" },
    "outputs": { "schema": { "type": "object" } },
    "forbidden": { "network": true, "storage": true, "side_effects": true, "judgement": true },
    "behavior": { "deterministic": true, "idempotent": true }
  },
  "mode": "validate"
}
```

Response:
```json
{
  "error": {
    "code": "SCHEMA_INVALID",
    "message": "contract.inputs.schema must be an object."
  }
}
```

### Examples (rule_trace)

1) Success status

Request:
```json
{
  "run": {
    "run_id": "run-001",
    "ts": "2025-01-01T00:00:00Z",
    "actor": "system",
    "tool": "text_normalize",
    "tool_version": "0.1.0",
    "stage": "normalize"
  },
  "input": { "summary": { "type": "string", "size": 12, "hash": "abc" } },
  "result": {
    "ok": true,
    "output_summary": { "type": "string", "size": 12, "hash": "def" },
    "rules_hit": []
  },
  "policy": { "max_message_length": 200, "hash_alg": "sha256" }
}
```

Response:
```json
{
  "ok": true,
  "trace": {
    "run_id": "run-001",
    "ts": "2025-01-01T00:00:00Z",
    "actor": "system",
    "tool": "text_normalize",
    "tool_version": "0.1.0",
    "stage": "normalize",
    "input": { "type": "string", "size": 12, "hash": "abc" },
    "output": { "type": "string", "size": 12, "hash": "def" },
    "rules_hit": [],
    "status": "success"
  }
}
```

2) Rejected status

Request:
```json
{
  "run": {
    "run_id": "run-002",
    "ts": "2025-01-01T00:00:01Z",
    "actor": "agent",
    "tool": "schema_map",
    "tool_version": "0.1.0",
    "stage": "require"
  },
  "input": { "summary": { "type": "object", "size": 20, "hash": "ghi" } },
  "result": {
    "ok": false,
    "output_summary": { "type": "object", "size": 0, "hash": "" },
    "rules_hit": [
      {
        "rule_id": "require.user.name",
        "kind": "reject",
        "path": "user.name",
        "code": "REQUIRED_MISSING",
        "message": "Required path is missing."
      }
    ]
  },
  "policy": { "max_message_length": 200, "hash_alg": "sha256" }
}
```

Response:
```json
{
  "ok": true,
  "trace": {
    "run_id": "run-002",
    "ts": "2025-01-01T00:00:01Z",
    "actor": "agent",
    "tool": "schema_map",
    "tool_version": "0.1.0",
    "stage": "require",
    "input": { "type": "object", "size": 20, "hash": "ghi" },
    "output": { "type": "object", "size": 0, "hash": "" },
    "rules_hit": [
      {
        "rule_id": "require.user.name",
        "kind": "reject",
        "path": "user.name",
        "code": "REQUIRED_MISSING",
        "message": "Required path is missing."
      }
    ],
    "status": "rejected"
  }
}
```

3) Policy invalid

Request:
```json
{
  "run": {
    "run_id": "run-003",
    "ts": "2025-01-01T00:00:02Z",
    "actor": "user",
    "tool": "input_gate",
    "tool_version": "0.1.0",
    "stage": "size"
  },
  "input": { "summary": { "type": "string", "size": 3, "hash": "xyz" } },
  "result": {
    "ok": true,
    "output_summary": { "type": "string", "size": 3, "hash": "xyz" },
    "rules_hit": []
  },
  "policy": { "max_message_length": 200, "hash_alg": "md5" }
}
```

Response:
```json
{
  "error": {
    "code": "POLICY_INVALID",
    "message": "policy.hash_alg must be sha256."
  }
}
```
