* [ ] refactor: move `render_output()` from `cli/util.py` to `output/`
  * [ ] Preserve existing call site in CLI
  * [ ] Ensure no CLI-specific logic remains in the moved function

* [ ] feature: implement model context protocol interface
  * [ ] Add `mcp/` interface module under `src/showcov/mcp/`
  * [ ] Define public function `get_model_context(sections: list[UncoveredSection], meta: OutputMeta) -> dict`
    * [ ] Include version, environment metadata, uncovered sections (as JSON-compatible structures)
    * [ ] Strip non-relevant fields and internal-only attributes

* [ ] feature: generate MCP JSON schema
  * [ ] Expose function `generate_llm_payload(...) -> str`
  * [ ] Ensure output adheres strictly to `mcp_schema.json`
  * [ ] Validate output format under test using `jsonschema`

* [ ] test: add snapshot tests for model protocol
  * [ ] Emit deterministic LLM payloads in `tests/snapshots/llm_interaction.json`
  * [ ] Validate round-trip structure using `UncoveredSection.from_dict`

* [ ] test: verify model output excludes global state
  * [ ] Ensure only minimal interface-relevant state is present
