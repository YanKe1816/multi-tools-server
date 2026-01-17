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
