# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.3] - 2026-01-29

### Added

- add `--format json` to `showcov report` and `showcov diff` for schema-validated machine output

### Changed

- make `showcov report` coverage XML arguments optional and enable discovery when omitted

### Fixed

- fix branch summary counts when coverage XML provides `missing-branches` without `condition-coverage`
- fix branch summary merging across multiple reports to avoid order-dependent covered-branch undercount

## [0.2.2] - 2026-01-29

### Added

- add `--sections/--section` to `showcov report` to select which report sections are rendered (`lines`, `branches`, `summary`)

## [0.2.1] - 2026-01-22

### Fixed

- **CLI compatibility with Python 3.14**: Prevented `NameError` crashes caused by evaluated string annotations in Typer by ensuring required symbols (`Path`, `pathlib`) are present at runtime.
- **Coverage merging correctness**: Fixed uncovered-line calculation so merged reports only mark a line uncovered if _all_ inputs missed it.
- **Source enrichment robustness**: Coverage enrichment no longer crashes when referenced source files are missing or unreadable.
- **TOML parsing safety**: Narrowed exception handling when reading `pyproject.toml` coverage configuration.
- **Renderer error handling**: Invalid output formats now raise clearer, more specific errors.

### Changed

- **CLI internals refactor**: Consolidated report/diff build and render logic via shared helpers for consistent behavior (format resolution, color policy, thresholds).
- **Tooling strictness**: Removed `|| true` from lint, format, test, and coverage commands so failures surface correctly.
- **Typing improvements**: Added missing type annotations and removed dynamic `Any` usage in CLI and shared helpers.
- **Threshold handling**: Centralized threshold evaluation logic and improved failure reporting consistency.

### Tests

- Added regression test for multi-report statement hit merging.
- Added test to ensure enrichment succeeds when source files are missing.
- Tightened `pytest.raises()` assertions with explicit error message matching.
- Improved test docstrings to follow imperative mood.

### Developer Experience

- Cleaner Typer callback signatures and option declarations.
- Reduced CLI duplication and improved maintainability of command implementations.

## [0.2.0] - 2026-01-21

### Changed

- reorganize the core pipeline into dedicated `coverage`, `engine`, `render`, and `model` packages that drive the new report-building workflow
- replace assertion guards with explicit exceptions and refactor branch/summary helpers so errors surface deterministically and branch aggregation stays typed
- tighten XML parsing/JSON rendering by introducing typed coverage contracts, routing all XML access through `defusedxml`, and centralizing metadata setup in `showcov._meta`

## [0.1.4] - 2025-11-22

### Changed

- refactor human output formatter into smaller helpers for improved readability
- refactor riprg-style line renderer into smaller helpers for improved readability

### Fixed

- fix CLI threshold option typing so typecheck passes when evaluating thresholds
- fix typing in riprg renderer mapping helper to satisfy static type checker
- add a default for `OutputMeta.is_tty` so existing tests and callers do not need to pass it explicitly

## [0.1.0] - 2025-11-08

### Changed

- replace the multi-command interface with a single `report` entrypoint covering all sections and formats
- standardize “no results” messaging and ordering across human, markdown, and HTML renderers

### Added

- add exit-code documentation, color policy checks, and schema-v2 JSON snapshots for the unified CLI
- add `showcov.scripts` helpers for generating manual pages and shell completion scripts

### Removed

- remove legacy XML helpers that duplicated the new dataset/report pipeline

## [0.0.29] - 2025-11-07

### Added

- add `--format` support to `showcov summary`, including JSON and HTML rendering

## [0.0.28] - 2025-11-06

### Added

- add a `showcov summary` command that prints the statements/branches table also used in pytest output
- add `--code`, `--context`, and `--line-numbers` options to `showcov branches` plus grouped coverage summaries via a shared table formatter

### Changed

- report partially covered branch conditions by default and format branch condition labels more descriptively

## [0.0.27] - 2025-11-06

### Fixed

- fix `showcov branches` to report gaps when coverage XML only supplies the `missing-branches` attribute
