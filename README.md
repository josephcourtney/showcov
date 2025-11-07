# showcov

showcov is a command-line utility that loads one or more coverage XML reports and emits a unified
summary of uncovered code. A single `report` command drives every format and section.

## Quick start

```bash
showcov report --cov coverage.xml --sections lines,summary --format human
```

The command accepts coverage XML via `--cov`. When omitted, `showcov` searches for the configured
XML path in common config files (`pyproject.toml`, `.coveragerc`, `setup.cfg`).

Key options:

* `--sections lines,branches,summary,diff` – render any combination of report sections.
* `--format human|markdown|html|json|auto` – choose an output format; `auto` selects human output
  when stdout is a TTY and JSON otherwise.
* `--code`, `--context`, `--line-numbers` – include annotated source code for uncovered lines.
* `--include/--exclude` – filter files by glob patterns.
* `--branches-mode missing-only|partial|all` – control which branch conditions are reported.
* `--threshold` – enforce coverage thresholds; failures exit with status code `2`.

## JSON output

`showcov report --format json` produces the schema-v2 JSON structure containing metadata, report
sections, and deterministic ordering of files, ranges, and branch conditions. Use
`jsonschema --instance <output> src/showcov/data/schema.v2.json` to validate the payload.

## Exit status

* `0` – success
* `1` – unexpected internal error
* `2` – one or more thresholds failed
* `65` – malformed coverage XML
* `66` – coverage XML could not be located or read
* `78` – configuration error (invalid `--cov` references, etc.)

## Completions and manual page

`showcov.scripts.build_completion_script(shell)` and `showcov.scripts.build_man_page()` generate
up-to-date shell completions and a plain-text manual that reflect every option of the unified
`report` command.
