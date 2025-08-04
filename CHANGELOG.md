## [0.0.19] - 2025-08-04

### Added
- add HTML output format for static reports
- add optional per-file coverage summary with uncovered percentages
- dynamically derive CLI format choices from available formats

---

## [0.0.18] - 2025-08-04

### Added
- add model context protocol interface and LLM payload generator
- move output rendering logic to output package

---

## [0.0.17] - 2025-08-04

### Changed
- remove `--no-pager`; make pager off the default
- replace custom path filtering with `pathspec` for include/exclude rules
- use `more-itertools.consecutive_groups` to group uncovered line numbers

---

## [0.0.16] - 2025-08-03

### Fixed
- deduplicate uncovered `<line>` elements so repeated line numbers no longer expand ranges or crash grouping
- `Runtime.debug` now honours `--debug` instead of piggy-backing on `--verbose`
- mutually-exclusive `--pager` / `--no-pager` conflict is detected immediately
- `Format.from_str()` is now case-insensitive with better suggestions

## [0.0.14] - 2025-08-03

### Added
- add CLI flags for `--quiet`, `--verbose`, `--summary-only`, `--stats`, `--pager`, and `--list-files`
- add automatic format detection and improved invalid format suggestions
- emit coverage statistics footer and enhanced fallback messages

### Changed
- refine exit codes and logging diagnostics

---

## [0.0.13] - 2025-08-03

### Changed
- replace string-based formatter flags with `Format` enum and `OutputMeta` dataclass

---

## [0.0.12] - 2025-08-03

### Added
- add `PathFilter` utility for reusable path include/exclude logic

### Changed
- validate CLI input types with strict path and range checks
- consolidate CLI error handling for coverage XML failures

### Fixed
- raise `ValueError` for negative `context_lines` inputs

---

## [0.0.11] - 2025-08-03

### Changed
- refactor tests with shared fixtures and parameterization

---

## [0.0.10] - 2025-08-03

### Changed
- limit source line cache to 256 entries to bound memory usage

---

## [0.0.9] - 2025-08-02

### Changed
- centralize configuration constants in `config.py`
- remove module-level side effects and load schema via package resources

---

## [0.0.8] - 2025-08-02

### Added
- reimplement CLI with click, path filtering, exclusion patterns, and file output
- add markdown and sarif output formats

---

## [0.0.7] - 2025-08-02

### Added
- stream coverage XML parsing to reduce memory usage

### Fixed
- cache source file lines and handle UnicodeDecodeError gracefully
- validate CLI inputs and configuration paths

---

## [0.0.6] - 2025-08-02

### Added
- add JSON round-trip parsing via `parse_json_output` and `UncoveredSection.from_dict`
- add snapshot tests for JSON output and LLM prompts
- add edge-case tests for missing source files and context line handling

### Fixed
- handle negative context-line values without crashing

---

## [0.0.4] - 2025-08-02

### Added
- CLI flag `--with-code` to embed raw source lines in JSON output.
- CLI flag `--context-lines` to include surrounding source lines in human and JSON outputs.
- CLI output formatter registry in `showcov/output.py`, supporting `human` and `json` formats.
- Environment metadata block in JSON output: includes coverage XML path, context settings.
- Structured `UncoveredSection` data model with `.to_dict()` for serialization.
- Runtime JSON schema validation using `jsonschema`.
- JSON schema at `src/showcov/data/schema.json` defining structured coverage report format.
- Tests for:
  - Output formatters and flag integration.
  - JSON schema compliance.
  - Color control, deterministic output, and embedded source inclusion.
- CLI flags:
  - `--format {human,json}` (default `human`)
  - `--no-color` to disable ANSI output.

### Changed
- Renamed CLI flag `--embed-source` to `--with-code`.
- Decoupled CLI logic and core logic into `cli.py` and `core.py`.
- Delegated formatting to centralized formatter registry.
- Made file and section ordering deterministic in all output formats.
- Updated `pyproject.toml`:
  - Version bumped to `0.0.4`.
  - `showcov` entry point updated to `showcov.cli:main`.
- Updated fallback version resolution in `__init__.py` when package metadata is missing.

### Fixed
- Removed system-dependent fields from JSON environment metadata.

---

## [0.0.3] - 2025-08-02

### Changed
- Marked Phase 1 TODO items as complete.
- Ensured `schema.json` is included in package metadata.
- Removed JSON from `exclude_print` list in `.grobl.config.json`.

---

## [0.0.2] - 2025-08-02

### Feature: JSON Output (Phase 1)

#### Added
- JSON output mode via `--format json`.
- Schema-compliant JSON formatter emitting structured uncovered sections.
- Unit tests for JSON formatting and CLI integration.

#### Changed
- `TODO.md` updated to reflect completed output format implementation.
- `determine_xml_file()` refined to normalize input paths.

---

### Added
- `TODO.md` to document roadmap: format support, protocol integration, decoupling steps.
- `AGENTS.md` to define automation guidelines, coding standards, and tooling requirements.
- `--no-color` CLI flag for ANSI suppression.
- Tests for color disabling and deterministic output behavior.
- Sample output block added to `README.md`.
- `src/showcov/__main__.py` to support `python -m showcov`.

### Changed
- Moved `ty` to `[dependency-groups.dev]`.
- Refactored tests into `tests/test_cli.py` and `tests/test_core.py`.
- Split CLI and core logic for separation of concerns.
- Reorganized and condensed `TODO.md` into phased structure.
- Updated `.grobl.config.json`, `AGENTS.md`, and `TODO.md` for new module layout.

---

## [0.0.1] - 2025-08-02

### Breaking
- Changed project license from `MIT` to `GPL-3.0-only`.
- Increased minimum Python version from `>=3.12` to `>=3.13`.

### Changed
- Migrated build backend from `hatchling` to `uv_build`.
- Fixed author email casing.
- Set fixed version string (`0.0.1`) instead of dynamic versioning.
- Refined `ruff` configuration to suppress false positives in tests.

---

## [0.0.0] - 2025-04-22

### Initial Release

#### Added
- Implemented `showcov`, a CLI tool for extracting and printing uncovered lines from a coverage XML report.
- Contiguous uncovered sections grouped by file and displayed with context.
- Colorized CLI output using `colorama`.
- XML file detection via `pyproject.toml`, `.coveragerc`, or `setup.cfg`.
- Support for merging uncovered ranges across blank lines.
- Robust parsing using `defusedxml` with early root extraction.
- CLI argument parsing and structured logging.
- Test suite for:
  - CLI parsing and options
  - File and config resolution
  - XML parsing logic and edge cases
- Stub project structure under `src/showcov/` and `tests/`.
- Configuration:
  - `pyproject.toml` for packaging, dependencies, linting, testing, and coverage.
  - `.grobl.config.json` for indexing and codebase formatting.
  - `.gitignore` for Python, editors, and build artifacts.
- `LICENSE` file under MIT License (later changed).

---

## Meta and Infrastructure

### Documentation
- Added `AGENTS.md` with automation constraints and live-log conventions.
- Added `TODO.md` and later restructured it into phase-based goals.
- Added `LIVELOG.md` and placeholder `CHANGELOG.md` at project root.
- Updated `README.md` with sample output.

### Project Management
- Version bumps:
  - `0.0.1` → `0.0.2` → `0.0.3` → `0.0.4`
- Defined release protocol: version bump before pull request submission.
- Created index commit referencing major TODO.md updates.

