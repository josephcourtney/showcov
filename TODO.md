## Group A: schema packaging and config constants

- [x] Embed schema.json via importlib.resources.files("showcov.data") at build time and list it under [tool.uv_build].resources to avoid runtime FileNotFoundError when installed as a wheel.
- [x] Move `CONSECUTIVE_STEP` and other constants to `src/showcov/config.py`
- [x] enumerate and eliminate module-level side effects

---

## Group B: performance and stability enhancements

- [x] Limit `_read_file_lines` cache size with `@lru_cache(maxsize=256)`
  - Avoid unbounded memory use for large repositories

---

## Group C: improved testing infrastructure

- [x] Replace inline XML strings in tests with reusable fixture factories
  - Move to `conftest.py` or shared `test_utils.py`
- [x] Define a reusable test fixture for `CliRunner`
- [x] Parameterize tests with `pytest.mark.parametrize` where appropriate
- [x] Improve tests using parameterization, reusable mocks and fixtures, and make them more consistent with idiomatic pytest usage

---

## Group D: hypothesis property-based testing

- [ ] Add property-based tests with `hypothesis`

---

## Group E: CLI and path-filtering improvements

- [ ] Create a `PathFilter` utility class for include/exclude logic
  - Encapsulate `_expand_paths()` and `_filter_sections()` into a reusable and testable component
- [ ] Consolidate CLI error handling for `CoverageXMLNotFoundError`, `ElementTree.ParseError`, and `OSError`
- [ ] Validate CLI input types with Click `Path(..., exists=True)` and `IntRange(min=0)`
- [ ] Fail early on negative `context_lines` in non-CLI contexts
  - Raise `ValueError` in `UncoveredSection.to_dict()` if violated

---

## Group F: formatter API refactor and Enum cleanup

- [ ] Replace `--format` string flags with a `Format` Enum
  - Define `Format(str, Enum)` in `output.py`
  - Use Enum in `get_formatter()` and `click.Choice`
- [ ] Introduce `OutputMeta` dataclass to consolidate formatter options
  - Replace `context_lines`, `with_code`, `coverage_xml`, and `color` params with a single object
- [ ] Replace format string literals in `FORMATTERS` with an Enum-based registry
  - Add `.from_str()` helper if needed for CLI compatibility

---

## Group G: XML logic modularization

- [ ] Extract XML parsing and discovery logic from `core.py` into a new `src/showcov/xml.py` module
  - Move `gather_uncovered_lines_from_xml`, `parse_large_xml`, and `get_config_xml_file` and its helpers
  - Provide `discover_xml_path()` and `stream_coverage()` for reuse
  - Keep `core.py` focused only on grouping logic

---

## Group H: dev ops
- [ ] implement version bump automation by adding a `pre-commit` hook that checks `CHANGELOG.md` against `pyproject.toml`
