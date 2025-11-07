# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
