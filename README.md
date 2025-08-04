# showcov

showcov is a command-line utility that prints uncovered lines of code—grouped into contiguous sections—from a coverage XML report.

## Features

- Human-readable report of uncovered lines with optional surrounding context.  
- Structured JSON output conforming to a published schema.  
- Option to include source code snippets around uncovered ranges.  
- Deterministic ordering of files and ranges for reliable diffing and automation.  
- Environment metadata embedded in JSON (coverage file, context settings, inclusion flags).  
- Automatic resolution of the coverage XML file from argument or common config files.  
- Snapshot-ready output for integration with LLMs or CI.  
- Round-trip fidelity: JSON can be parsed back into the same coverage sections.  
- Validation of JSON output against the schema to catch regressions.  
- CLI flags: format selection, code embedding, context control, and disabling ANSI color.  
- Graceful handling of common edge cases (missing source, invalid context, no uncovered lines).  
- Programmatic API for consuming uncovered-section data in other tools or scripts.  
- Gitignore-style path filtering via `--include` and `--exclude` powered by `pathspec`
- Save results directly to a file with `--output FILE`  
- Markdown format: emit collapsible code blocks for easy use in pull-request comments (`--format markdown`)  
- SARIF format: emit machine-readable results for GitHub Advanced Security annotations (`--format sarif`)
- Quiet and verbose modes:
  - `--quiet` suppresses informational logs
  - `--verbose` emits file and output diagnostics
- Summary and statistics output:
  - `--summary-only` prints only affected file paths
  - `--stats` appends totals for uncovered files, regions, and lines
- Auto-paging for long reports:
  - Pipe `--format human` output through `$PAGER` when writing to TTY
  - Configurable with `--pager` and `--no-pager`
- Optional interactive mode:
  - `--interactive` steps through uncovered files one at a time
- Smarter error handling and logging:
  - `--debug` enables full tracebacks
  - Friendly error messages by default
- Structured exit codes for CI:
  - Use `sysexits.h`–style codes to indicate error cause
- Format autodetection:
  - `--format auto` selects `human` or `json` based on stdout target
- Glob pattern support in CLI arguments:
  - Accept glob patterns (e.g., `src/**/*.py`) as input paths
- File-only listing mode:
  - `--list-files` emits one uncovered file path per line
- Output suggestions on flag errors:
  - Suggest closest matching format name on typos

## Installation

```bash
uv tool install clone https://github.com/josephcourtney/showcov.git
```

## Usage

```bash
showcov [COVERAGE_XML_FILE]
```

- **COVERAGE_XML_FILE**: _(Optional)_ The path to your coverage XML report.  
  If omitted, showcov will search for a configuration file (such as `pyproject.toml`, `.coveragerc`, or `setup.cfg`) that specifies the XML report’s location.

Result for showcov itself:

```bash
INFO: Using coverage XML file from config: .coverage.xml

Uncovered sections in /Users/josephcourtney/code/showcov/src/showcov/__version__.py:
  Line 1:
       1: __version__ = "0.0.9"


Uncovered sections in /Users/josephcourtney/code/showcov/src/showcov/main.py:
  Line 25:
      25:     from xml.etree.ElementTree import Element  # noqa: S405

  Line 136:
     136:         return groups

  Line 199:
     199:             continue

  Lines 240-241:
     240:             logger.error("Failed to parse coverage XML file: %s", xml_file)
     241:             sys.exit(1)
```


## API Usage

You can use `showcov` programmatically via the `get_coverage_data` function:

```python
from pathlib import Path
from showcov.core import build_sections, parse_large_xml, determine_xml_file, gather_uncovered_lines

xml_path = determine_xml_file()
root = parse_large_xml(xml_path)
uncovered = gather_uncovered_lines(root)
sections = build_sections(uncovered)
````

This returns a list of `UncoveredSection` instances, which can be serialized to JSON using:

```python
from showcov.output import OutputMeta, format_json

meta = OutputMeta(context_lines=1, with_code=True, coverage_xml=xml_path, color=False)
output = format_json(sections, meta)
print(output)
```

## JSON Output Format

The `--format json` output is guaranteed to conform to the schema at `src/showcov/data/schema.json`, which supports:

- Tool version (`version`)
- Execution environment metadata (`environment`)
- Deterministic list of uncovered code blocks grouped by file

Use this format for toolchain integration with LLMs, CI pipelines, or coverage dashboards.
```

## License

This project is licensed under the [GPL v3.0 License](LICENSE).
