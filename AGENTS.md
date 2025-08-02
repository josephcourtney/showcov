## Purpose

This file defines how coding agents (LLMs, autonomous dev tools, etc.) should operate when contributing to this project.

## Role

You are an assistant contributing to `showcov`, a CLI tool that identifies uncovered lines in Python source files from a coverage XML report.

Your responsibilities include:
- Editing Python source files under `src/showcov/`
- Editing or creating test files under `tests/`
- Maintaining output determinism, testability, and format extensibility
- Respecting existing CLI design and internal architecture

## Directories

- Source code: `src/showcov/`
- Tests: `tests/`
- Do not create or modify files outside these directories unless explicitly instructed.

## Tooling Requirements

You must use the following tools for validation and conformance before proposing code:

### Linting
- Run: `ruff check src/ tests/`
- Use rules defined in `pyproject.toml` and any referenced `ruff.default.toml`

### Formatting
- Run: `ruff format src/ tests/`

### Static Typing
- Run: `ty check src/ tests/`
- Use Python 3.13–compatible type syntax.
- Respect constraints in `pyproject.toml`

### Testing
- Run: `pytest`
- `pytest` should follow the settings in `pyproject.toml`
- Add test coverage for new features or regression paths.
- Use deterministic test data and avoid system-dependent values (e.g., timestamps, absolute paths).

## Behavior Constraints

- **Path normalization**: always use POSIX-style (`/`) paths in output and JSON.
- **Output stability**: sort all file paths and line groups deterministically.
- **No ANSI styling** in non-human formats (e.g., JSON).
- **No I/O outside of `src/` or `tests/`** unless instructed.

## Commit Standards

- Each commit should pass:  
  - `ruff check && ruff format`  
  - `ty check`  
  - `pytest`

- Prefer conventional commit messages:
  - `feat: add --format json`
  - `fix: handle missing <class> tag in coverage XML`
  - `test: add tests for merge_blank_gap_groups`

## Prohibited

- Do not introduce new dependencies without justification in a comment.
- Do not remove test coverage.
- Do not introduce non-deterministic behavior.

## Compliance

All contributions must adhere to this protocol unless overridden by a specific user instruction or documented exception.
