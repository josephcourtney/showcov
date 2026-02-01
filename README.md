# showcov

showcov is a command-line utility that loads one or more coverage XML reports, merges them into a
single dataset, and emits a deterministic summary of uncovered code. All workflows now flow through the
single `report` command, which toggles the available sections and enrichment flags (no additional
subcommands or formats).

## Features

- **Unified coverage report from one or more XML files**
  - Merges multiple coverage reports into a single dataset.
  - Automatically locates the coverage XML via common project configs or accepts explicit paths.
  - Normalizes file paths relative to the project root for stable output.

- **Report sections**
  - **Uncovered lines:** groups contiguous misses and merges gaps separated only by blank lines. Toggle with `--lines/--no-lines`.
  - **Uncovered branches:** lists per-line branch conditions and their coverage status. Enable or disable branch output with `--branches/--no-branches`.
  - **Summary:** per-file and overall totals for statements and branches plus derived percentages. Disable with `--no-summary` if only raw misses are desired.

- **Human-readable output**
  - A single Rich-inspired renderer with compact tables and optional inline snippets; no other formats are exposed.

- **Filtering & ordering**
  - Include/exclude files using glob/“.gitignore”-style patterns and concrete paths or directories.
  - Stable, deterministic sorting of files and line groups.
  - Multiple ordering strategies for summaries (by file name, statement coverage, branch coverage, or total misses).

- **Code context & annotations**
  - Optional inline source excerpts around uncovered ranges enabled with `--code` and tuned via `--context`.
  - Optional line numbers alongside excerpts.
  - Lightweight tagging of lines for common cases (e.g., “no-cover” pragmas, abstract methods).

- **Coverage thresholds**
  - Declarative constraints on statement coverage, branch coverage, and total misses.
  - Aggregates are computed across the unified dataset.
  - Structured failures and a non-zero exit status for CI enforcement.

- **TTY and color behavior**
  - Auto-detects whether ANSI color should be emitted; can be forced on/off.

- **Logging & exit codes**
  - Adjustable verbosity (quiet/normal/verbose/debug).
  - Clear, distinct exit statuses for success, threshold failure, malformed input, missing input, and configuration errors.

- **Programmatic surface**
  - Importable building blocks to parse coverage XML, build datasets, compute sections, and render human output.
  - A Rich-based coverage table renderer available for embedding in other tools.

- **Determinism & robustness**
  - Stable path presentation and ordering independent of CWD.
  - Safe file reading with graceful handling of unreadable or non-UTF-8 sources.

- **Developer tooling (artifacts)**
  - Generators for a plain-text manual page and shell completion scripts (bash/zsh/fish) to aid distribution and packaging.
