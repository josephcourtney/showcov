### CLI Behavior & Output Fixes

- [x] **Honor `--no-paths`**
  Add `show_paths` field to `OutputMeta`; update all formatters to suppress file headings and "File" column when false.

- [x] **Normalize `--include` / `--exclude` behavior**
  - Normalize all paths to project-relative form before filtering.
  - Automatically expand included directories to match `**/*`.

- [x] **Make `--line-numbers` functional**
  Add `show_line_numbers` to `OutputMeta`; apply in all formatters that render code.

- [x] **Harden `--context` parsing**
  Catch `ValueError` in `_resolve_context_option()`; raise `click.BadParameter` with user-friendly message.

- [x] **Respect `--no-code` in all formats**
  Check `meta.with_code` in each formatter (Markdown, HTML, etc.) before rendering code blocks.

- [x] **Emit stats in JSON output**
  Extend JSON schema to include:
  - `summary`: total uncovered lines.
  - `files[]`: add `counts` field per file with line stats.
  Respect `--stats` and `--file-stats`.

- [x] **Handle `--output` path errors gracefully**
  - Pre-validate output path existence and writability.
  - Catch `OSError` in `write_output()` and raise `click.FileError`.

- [x] **Make `--verbose` meaningful**
  Add `logger.debug()` calls at key points:
  - Input discovery
  - Path filtering
  - Formatter selection
  - Stats computation
  Respect `--verbose` via log level control.

- [x] **Suggest alternatives on `--format` errors**
  On bad format, use `difflib.get_close_matches()` to suggest valid values.

- [x] **Disallow `--format auto` with file output**
  If `--format=auto` and `--output` is set (non-TTY), raise `click.BadOptionUsage` with guidance.

### Pager Improvements

- [x] **Add `--pager` / `--no-pager` to `diff`**
  - Move pager logic into shared helper.
  - Use same options and behavior as `show`.

- [x] **Change Default pager behavior and document it**
  - make no-pager the default option
  - Add README note describing auto-pager.
  - Support `SHOWCOV_PAGER=off` to disable pager without CLI flag.

- [x] **Expand Test Coverage**
  - A usability study surfaced all of the problems above. Many of them should have been covered by tests. Go through all like user behaviors and option combinations and make sure that all cases are covered. Use test parameterization to assist in covering combinations
