### Goals
- Serve coverage data via the Model Context Protocol
- Ensure compatibility with LM Studio and other MCP clients
- Expose schema-compliant `resources/list` and `resources/read` endpoints
- Support deterministic LLM payload generation

### Tasks

- [x] Add `mcp[cli]>=1.7.0` to project dependencies with justification in AGENTS.md
- [x] Create `src/showcov/mcp_server.py` as MCP server entrypoint module
- [x] Define `FastMCP` instance and lifecycle handler functions
  - [x] Implement `on_initialize()` to register tool metadata and capabilities
  - [x] Implement `on_shutdown()` to handle graceful termination
- [x] Register `resources/list` handler
  - [x] Return synthetic resource descriptor for coverage payload (e.g., `showcov:coverage.json`)
  - [x] Populate `name`, `description`, `mime`, and `read_only` fields
  - [x] Include source location metadata
- [x] Register `resources/read` handler
  - [x] Resolve coverage XML and uncovered sections (via `resolve_sections(...)`)
  - [x] Serialize using `generate_llm_payload(...)` with context and code flags
  - [x] Return JSON response conforming to `mcp_schema.json`
  - [x] Validate response using `jsonschema.validate(...)`
- [x] Add new CLI entry point:
  - [x] Expose `showcov-mcp = showcov.mcp_server:main` in `pyproject.toml`
  - [x] Support `--debug`, `--context`, `--with-code`, and `--cov` flags for local control
  - [ ] Use `uvicorn` for debugging if desired (optional)
- [x] Add integration tests under `tests/test_mcp_server.py`
  - [x] Simulate `resources/list` and `resources/read` requests
  - [x] Validate returned structure matches expected `mcp_schema.json`
  - [x] Check for deterministic output
- [x] Add snapshot file for MCP JSON output to `tests/snapshots/`
  - [x] Ensure `context_lines=1` and `with_code=true` are covered
