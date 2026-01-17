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
