### Phase 1: Structured JSON Output with Schema and Options

* [x] Define `UncoveredSection(file: Path, ranges: list[tuple[int, int]])` model with `.to_dict()` for JSON export.
* [x] Add CLI option `--format {human,json}` (default: `human`).
* [x] Modify `main()` and `print_uncovered_sections()` to dispatch based on format.
* [x] Write `print_json_output(uncovered_data: dict[Path, list[int]]) -> None`.
* [x] Abstract uncovered data into the structured internal model before formatting.
* [x] Add `--context-lines=N` (optional): include source lines ±N around each uncovered section.
* [x] Assess the JSON schema (`src/showcov/data/schema.json`) and update it as necessary.
* [x] Ensure that `schema.json` file is included when packaging.
* [x] Validate generated JSON matches schema using a static schema or runtime validator.
* [x] Ensure path normalize to POSIX-style (`/`) and resolve paths relative to project root.
* [x] Update/add tests covering:

  * [x] JSON output structure using the model.
  * [x] Presence/absence of code with `--with-code` and context lines.
  * [x] Schema validation success/failure.
  * [x] No ANSI escape codes in JSON.
  * [x] Stable ordering of files and ranges.

### Phase 2: Decouple formatting/output from Logic

* [ ] Add an item to the JSON output (and update the schema) to indicate the "environment" like what coverage file was run, and other important details.
* [ ] Make the behavior with respect to different command line flags consistent across output formats.
* [ ] Move all printing/formatting into dedicated module: `showcov/output.py`.
* [ ] Introduce output selection via a registry or strategy pattern so `--format` selects formatter.
* [ ] Update `main()` to call into the new output layer via a clean API, passing model instances.
* [ ] Ensure the human formatter still honors `--no-color` and that JSON formatter remains colorless.
* [ ] Add tests for the new output module (unit tests invoking formatters with deterministic input).

### Phase 3: Feature Completion and Determinism Guarantees (LLM Usability focus)

* [ ] Add option `--embed-source` to include raw source lines under each uncovered range.
* [ ] Avoid floating or system-dependent fields (timestamps, random hashes, etc.) in all outputs.
* [x] Ensure stable sorting: files alphabetically by posix path, uncovered groups ordered numerically, as invariants.
* [ ] Ensure all JSON output fully complies with machine-friendly constraints (no ANSI in non-human modes, consistent structure).
* [ ] Design output to conform to emerging context-tool protocols (e.g. OpenAI tool-calling, LangChain toolkits) as needed.

### Phase 4: Testing Enhancements beyond Basic Correctness

* [ ] Add round-trip validation: uncovered → JSON → parsed → == original model instances.
* [ ] Add snapshot tests of JSON output and sample prompts to LLMs for smoke-checking usability.
* [ ] Expand coverage for edge/corner cases introduced by new features (missing source files when embedding, invalid context ranges, etc.).

### Phase 5: Protocol/tooling Integration Readiness

* [ ] Ensure output JSON is valid with `application/json` MIME type, no extra preamble or wrapper.
* [ ] Expose main logic as a function callable via API: `get_coverage_data(xml_path: Path) -> list[UncoveredSection]` (already done but ensure documentation and tests).
* [ ] Annotate output functions with complete type hints using `TypedDict` or `pydantic.BaseModel`.
* [ ] Ensure public API and output are documented for CLI/API parity and external tooling consumption.
