# showcov

showcov is a command-line utility that loads one or more coverage XML reports and emits a unified
summary of uncovered code. A single `report` command drives every format and section.

## Features

- **Unified coverage report from one or more XML files**
  - Merges multiple coverage reports into a single dataset.
  - Automatically locates the coverage XML via common project configs, or accepts explicit paths.
  - Normalizes file paths relative to the project root for stable output.

- **Report sections**
  - **Uncovered lines:** groups contiguous misses and merges groups separated only by blank lines.
  - **Uncovered branches:** lists per-line branch conditions with their individual coverage or “missing” status; supports different inclusion modes (e.g., only missing, partial, all).
  - **Summary:** per-file and overall totals for statements and branches (total / covered / missed) with derived percentages.
    - Select sections to render with `showcov report --sections ...` (e.g., `--sections summary`).
  - **Diff:** compares two reports, highlighting newly uncovered and resolved lines.

- **Output formats**
  - **Human-readable:** compact tables; optional color; suitable for terminals and logs.
  - **Machine-readable JSON:** validated against a versioned public schema; includes tool metadata, environment info, options, and all report sections.

- **Filtering & ordering**
  - Include/exclude files using glob/“.gitignore”-style patterns and concrete paths or directories.
  - Stable, deterministic sorting of files and line groups.
  - Multiple ordering strategies for summaries (by file name, statement coverage, branch coverage, or total misses).

- **Code context & annotations**
  - Optional inline source excerpts around uncovered ranges with a tunable context window.
  - Optional line numbers alongside excerpts.
  - Lightweight tagging of lines for common cases (e.g., “no-cover” pragmas, abstract methods).

- **Coverage thresholds**
  - Declarative constraints on statement coverage, branch coverage, and total misses.
  - Aggregates are computed across the unified dataset.
  - Structured failures and a non-zero exit status for CI enforcement.

- **TTY and color behavior**
  - Auto-detects whether ANSI color should be emitted; can be forced on/off.
  - Avoids ANSI codes in non-human formats.

- **Logging & exit codes**
  - Adjustable verbosity (quiet/normal/verbose/debug).
  - Clear, distinct exit statuses for success, threshold failure, malformed input, missing input, and configuration errors.

- **Programmatic surface**
  - Importable building blocks to parse coverage XML, build datasets, compute sections, and render human/JSON outputs.
  - A Rich-based coverage table renderer available for embedding in other tools.

- **Determinism & robustness**
  - Stable path presentation and ordering independent of CWD.
  - Safe file reading with graceful handling of unreadable or non-UTF-8 sources.

- **Developer tooling (artifacts)**
  - Generators for a plain-text manual page and shell completion scripts (bash/zsh/fish) to aid distribution and packaging.
