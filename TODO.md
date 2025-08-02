### I. Output Format Refactor

#### Add Output Format Option

* [x] Add CLI option `--format {human,json}` (default: `human`).
* [x] Modify `main()` and `print_uncovered_sections()` to dispatch based on format.
* [ ] Abstract uncovered data into a structured internal model before formatting.

#### Implement JSON Output

* [x] Write `print_json_output(uncovered_data: dict[Path, list[int]]) -> None`.
* [ ] Add `--with-code` (optional): include source lines in the output.
* [ ] Add `--context-lines=N` (optional): include source lines ±N around each uncovered section.
* [ ] Assess the JSON schema and update it as necessary.
* [ ] Validate generated JSON matches schema using a static schema or runtime validator.

### II. LLM-Focused Enhancements

#### Machine-Friendliness

* [x] add a --no-color flag
* [x] Remove all ANSI color codes and text styling from `json` mode.
* [x] Normalize all paths to POSIX-style (`/`) and resolve relative paths.

#### Determinism and Consistency

* [x] Ensure stable ordering: files sorted alphabetically, uncovered groups ordered numerically.
* [ ] Avoid floating or system-dependent fields (timestamps, random hashes, etc.).

#### Contextual Source Embedding (optional future support)

* [ ] Add option `--embed-source` to include raw source lines under each uncovered range:

  ```json
  { "start": 136, "end": 136, "lines": ["    return groups"] }
  ```

### III. Internal Architecture Improvements

#### Abstract Internal Data Model

* [ ] Define `UncoveredSection(file: Path, ranges: list[tuple[int, int]])`.
* [ ] Add model serialization methods: `.to_dict()` for JSON export.

#### Decouple Output from Logic

* [ ] Move all printing/formatting into dedicated module: `showcov/output.py`.
* [ ] Allow output selection via a registry or strategy pattern.

### IV. Protocol/Tooling Integration Readiness

#### Context Protocol Support

* [ ] Design output to conform to emerging context-tool protocols (e.g. OpenAI tool-calling, LangChain toolkits).
* [ ] Ensure that output JSON is valid with `application/json` MIME type, no extra preamble or wrapper.

#### CLI + API Parity

* [x] Expose main logic as a function callable via API:
  `get_coverage_data(xml_path: Path) -> list[UncoveredSection]`

#### JSON Schema + Type Hints

* [ ] Provide a `schema.json` file for the JSON output format.
* [ ] Annotate output functions with complete type hints using `TypedDict` or `pydantic.BaseModel`.

### V. Testing Enhancements

#### Add Format-Specific Tests

* [x] Add tests for `--format json` using `json.loads` and structural assertions.
* [ ] Add round-trip validation: uncovered → JSON → parsed → == original.

#### Ensure LLM Usability

* [ ] Add snapshot tests of JSON output and sample prompts to LLMs for smoke-checking usability.

## Appendix
### Proposed JSON Schema
```json
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/showcov.schema.json",
  "title": "Showcov Coverage Report",
  "type": "object",
  "properties": {
    "version": {
      "description": "Version of the showcov tool or schema.",
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "files": {
      "description": "List of source files with uncovered code sections.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file": {
            "description": "Path to the source file.",
            "type": "string"
          },
          "uncovered": {
            "description": "List of uncovered line ranges.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "start": {
                  "type": "integer",
                  "minimum": 1
                },
                "end": {
                  "type": "integer",
                  "minimum": 1
                },
                "lines": {
                  "description": "Optional source code lines in this range.",
                  "type": "array",
                  "items": {
                    "type": "string"
                  },
                  "minItems": 1
                }
              },
              "required": ["start", "end"],
              "additionalProperties": false
            }
          }
        },
        "required": ["file", "uncovered"],
        "additionalProperties": false
      }
    }
  },
  "required": ["version", "files"],
  "additionalProperties": false
}
```
