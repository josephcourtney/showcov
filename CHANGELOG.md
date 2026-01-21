# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).


## [0.2.0] - 2026-01-21

### Changed
- reorganize the core pipeline into dedicated `coverage`, `engine`, `render`, and `model` packages that drive the new report-building workflow
- replace assertion guards with explicit exceptions and refactor branch/summary helpers so errors surface deterministically and branch aggregation stays typed
- tighten XML parsing/JSON rendering by introducing typed coverage contracts, routing all XML access through `defusedxml`, and centralizing metadata setup in `showcov._meta`


## [0.1.4] - 2025-11-22

### Changed
- refactor human output formatter into smaller helpers for improved readability
- refactor ripgrep-style line renderer into smaller helpers for improved readability

### Fixed
- fix CLI threshold option typing so typecheck passes when evaluating thresholds
- fix typing in ripgrep renderer mapping helper to satisfy static type checker
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
