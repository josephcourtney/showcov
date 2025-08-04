* [x] refactor: move `render_output()` from `cli/util.py` to `output/`
  * [x] Preserve existing call site in CLI
  * [x] Ensure no CLI-specific logic remains in the moved function

* [x] feature: implement model context protocol interface
  * [x] Add `mcp/` interface module under `src/showcov/mcp/`
  * [x] Define public function `get_model_context(sections: list[UncoveredSection], meta: OutputMeta) -> dict`
    * [x] Include version, environment metadata, uncovered sections (as JSON-compatible structures)
    * [x] Strip non-relevant fields and internal-only attributes

* [x] feature: generate MCP JSON schema
  * [x] Expose function `generate_llm_payload(...) -> str`
  * [x] Ensure output adheres strictly to `mcp_schema.json`
  * [x] Validate output format under test using `jsonschema`

* [x] test: add snapshot tests for model protocol
  * [x] Emit deterministic LLM payloads in `tests/snapshots/llm_interaction.json`
  * [x] Validate round-trip structure using `UncoveredSection.from_dict`

* [x] test: verify model output excludes global state
  * [x] Ensure only minimal interface-relevant state is present
