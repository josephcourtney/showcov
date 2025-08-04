### Goals
- Serve coverage data via the Model Context Protocol
- Ensure compatibility with LM Studio and other MCP clients
- Expose schema-compliant `resources/list` and `resources/read` endpoints
- Support deterministic LLM payload generation

### Tasks

- [ ] Add `mcp[cli]>=1.7.0` to project dependencies with justification in AGENTS.md
- [ ] Create `src/showcov/mcp_server.py` as MCP server entrypoint module
- [ ] Define `FastMCP` instance and lifecycle handler functions
  - [ ] Implement `on_initialize()` to register tool metadata and capabilities
  - [ ] Implement `on_shutdown()` to handle graceful termination
- [ ] Register `resources/list` handler
  - [ ] Return synthetic resource descriptor for coverage payload (e.g., `showcov:coverage.json`)
  - [ ] Populate `name`, `description`, `mime`, and `read_only` fields
  - [ ] Include source location metadata
- [ ] Register `resources/read` handler
  - [ ] Resolve coverage XML and uncovered sections (via `resolve_sections(...)`)
  - [ ] Serialize using `generate_llm_payload(...)` with context and code flags
  - [ ] Return JSON response conforming to `mcp_schema.json`
  - [ ] Validate response using `jsonschema.validate(...)`
- [ ] Add new CLI entry point:
  - [ ] Expose `showcov-mcp = showcov.mcp_server:main` in `pyproject.toml`
  - [ ] Support `--debug`, `--context`, `--with-code`, and `--cov` flags for local control
  - [ ] Use `uvicorn` for debugging if desired (optional)
- [ ] Add integration tests under `tests/test_mcp_server.py`
  - [ ] Simulate `resources/list` and `resources/read` requests
  - [ ] Validate returned structure matches expected `mcp_schema.json`
  - [ ] Check for deterministic output
- [ ] Add snapshot file for MCP JSON output to `tests/snapshots/`
  - [ ] Ensure `context_lines=1` and `with_code=true` are covered
