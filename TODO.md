## TODO

#### JSON schema v2 (single, versioned document)
- [x] add `src/showcov/data/schema.v2.json` covering lines/branches/summary/diff in one shape
- [x] implement `format_json_v2(report)`; keep v1 encoder as internal helper for tests only
- [x] validate v2 with `jsonschema.validate` (update call sites)
- [x] embed `schema` and `schema_version` in top-level payload

### unify CLI into a single `report` surface (no backwards-compat required)

#### renderers (HUMAN/MD/HTML/JSON) for the unified `Report`
- [x] create `output/report_render.py` with `render_report(report, fmt, meta)`
- [x] HUMAN: section titles, shared table helper, one color policy; reuse `table.py`
- [x] MARKDOWN: `<details>` per file per section; reuse code-block logic; align with line numbers flag
- [x] HTML: `<section id=...>` structure; minimal inline styles; anchor links per file
- [x] JSON: v2 encoder only (v1 removed from CLI path)

#### CLI surface: `showcov report` (default)
- [x] replace `cli.py` subcommands with a single `report` command (make it the default entrypoint)
- [x] arguments & options:
  - [x] `[PATHS]...`, `--cov PATH`
  - [x] `--include GLOB...`, `--exclude GLOB...`
  - [x] `--sections S1,S2,...` where S ∈ `{lines,branches,summary,diff}`
  - [x] `--diff-base PATH` (required iff `diff` selected)
  - [x] `--branches-mode {missing-only,partial,all}` (default: `partial`)
  - [x] `--format {human,markdown,html,json,auto}`
  - [x] `--output FILE|-`
  - [x] `--code/--no-code`, `--context N[,M]`, `--line-numbers`
  - [x] `--paths/--no-paths`
  - [x] `--sort {file,stmt_cov,br_cov,miss}`
  - [x] `--stats` (aggregate counts) and `--file-stats`
  - [x] `--threshold stmt=<pct> br=<pct> miss=<n>` (repeatable; parse into policy)
  - [x] `--color/--no-color`, `-q/--quiet`, `-v/--verbose`, `--debug`
- [x] implement single-pass execution: parse XML once → dataset → build requested sections → render once
- [x] make bare `showcov` invoke `report`

#### exit codes & policy
- [ ] keep existing: `0` ok, `65` data error, `66` input missing, `78` config error, `1` generic
- [ ] add `2` when thresholds fail (document in help)
- [x] implement threshold evaluation over summary + lines counts (stmt%, branch%, total misses)

#### deletion of old subcommands
- [ ] remove `show`, `branches`, `summary`, `diff` entrypoints and their tests
- [ ] keep internal helpers where still useful (e.g., table formatting, branch parsing)
- [ ] update `__main__.py` and `project.scripts` unchanged (still points to `cli:cli`)

#### help, man page, completions
- [ ] update `man` generator to reflect `report` options only
- [ ] update `completions` scripts to complete `--sections`, `--branches-mode`, `--threshold`, etc.

#### code cleanup & consistency
- [ ] move all path normalization via `normalize_path` with a single `base` (coverage XML parent)
- [ ] unify “no results” messages across formats and sections
- [ ] standardize color behavior: `--color` forces; `--no-color` disables; `auto` uses TTY
- [ ] ensure deterministic ordering for files, ranges, branch condition lists
- [ ] annotate public APIs with Python 3.13 types; satisfy `ty check`
- [ ] delete legacy code paths in `showcov.core.core` / `showcov.core.coverage` that duplicate dataset/report logic once `report` is live

#### tests (replace, not patch)
- [ ] remove tests tied to deleted subcommands
- [x] add unit tests:
  - [x] `CoverageDataset` construction from XML (incl. malformed XML)
  - [x] builders: lines/branches/summary/diff (filters, sorting, modes)
  - [x] thresholds evaluation (pass/fail boundaries, mixed constraints)
  - [x] table width/grouping remains deterministic
  - [ ] color policy (forced vs disabled vs auto)
- [ ] add JSON v2 snapshot tests (stable ordering, numeric precision)
- [ ] e2e tests:
  - [ ] `report --sections lines,branches,summary --format json`
  - [ ] `report --sections diff --diff-base base.xml`
  - [ ] `report --threshold ...` exit code `2`
- [ ] performance test: ensure single XML parse when multiple sections requested (spy/patch parse)

#### docs & metadata
- [ ] update `README.md` with new CLI, examples, and JSON v2 shape
- [ ] update `CHANGELOG.md`:
  - [ ] add entry for version bump with “Changed: replace multi-subcommand CLI with unified `report`”
  - [ ] add “Added: thresholds & exit code 2; branches-mode; sections composition”
- [ ] bump version in `pyproject.toml`
- [ ] update `AGENTS.md` notes about CLI and schema v2 for contributors

#### implementation order (atomic PRs)
- [ ] PR1: `CoverageDataset` + builders (no CLI changes) + unit tests
- [ ] PR2: JSON v2 encoder + schema + snapshot tests
- [ ] PR3: renderers unified over `Report` (HUMAN/MD/HTML/JSON)
- [ ] PR4: `report` command wiring (keep repo compiling; old subcommands still present temporarily)
- [ ] PR5: thresholds + exit codes + tests
- [ ] PR6: remove old subcommands + delete legacy tests
- [ ] PR7: docs, changelog, version bump

#### QA & tooling
- [ ] ensure `.venv/bin/ruff check` and `.venv/bin/ruff format` clean after refactor
- [ ] ensure `.venv/bin/ty check` passes with Python 3.13 annotations
- [ ] ensure `.venv/bin/pytest` green; keep coverage equal or higher
- [ ] run `just qa` and add any missing recipes if helpful (optional)


