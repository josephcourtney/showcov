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

