# Global shell
set shell := ["zsh", "-euo", "pipefail", "-c"]

# Load .env if present (kept out of VCS)
set dotenv-load := true

# Show fewer internals in `just --list`
set allow-duplicate-recipes := false

# Defaults / Help
[private]
default: help

# Human-friendly task list
help:
  @just --list --unsorted --list-prefix "  "

# Echo effective configuration (useful for debugging CI/parity)
env:
  @echo "PYTHON_PACKAGE={{PYTHON_PACKAGE}}"
  @echo "PY_TESTPATH={{PY_TESTPATH}}"
  @echo "PY_SRC={{PY_SRC}}"
  @echo "UV={{UV}}"
  @echo "RUFF={{RUFF}}"
  @echo "PYTEST={{PYTEST}}"
  @echo "TYPES={{TYPES}}"
  @echo "NOX={{NOX}}"
  @echo "SHOWCOV={{SHOWCOV}}"

# Config (overridable via env/.env)
export PYTHON_PACKAGE := env("PYTHON_PACKAGE", file_stem(justfile_directory()))
export PY_TESTPATH    := env("PY_TESTPATH", "tests")
export PY_SRC         := env("PY_SRC", "src")
export VERBOSE        := env("VERBOSE", "0")

# Tool wrappers
UV      := "uv"
RUFF    := "./.venv/bin/ruff"
PYTEST  := "./.venv/bin/pytest"
TYPES   := "./.venv/bin/ty"
NOX     := "./.venv/bin/nox"
SHOWCOV := "./.venv/bin/showcov"

# Bootstrap: set up venv and update versions (soft: skip if uv missing)
setup:
  @if command -v {{UV}} >/dev/null 2>&1; then \
     {{UV}} sync --dev; \
   else \
     echo "[setup] skipping: uv ({{UV}}) not found"; \
   fi

# Bootstrap: set up venv obeying lockfile (soft: skip if uv missing)
setup-frozen:
   else \
     echo "[setup-frozen] skipping: uv ({{UV}}) not found"; \
   fi

# Format (best-effort helper)
format *ARGS:
  @if command -v {{RUFF}} >/dev/null 2>&1; then \
     {{RUFF}} format {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}} || true; \
   else \
     echo "[format] skipping: ruff ({{RUFF}}) not found"; \
   fi

# Check formatting (soft: skip if ruff missing)
format-no-fix *ARGS:
  @if command -v {{RUFF}} >/dev/null 2>&1; then \
     {{RUFF}} format --check {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}}; \
   else \
     echo "[format-no-fix] skipping: ruff ({{RUFF}}) not found"; \
   fi

# Lint (best-effort helper)
lint *ARGS:
  @if command -v {{RUFF}} >/dev/null 2>&1; then \
     {{RUFF}} check {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}} || true; \
   else \
     echo "[lint] skipping: ruff ({{RUFF}}) not found"; \
   fi

# Check lint rule compliance (soft: skip if ruff missing)
lint-no-fix *ARGS:
  @if command -v {{RUFF}} >/dev/null 2>&1; then \
     {{RUFF}} check --no-fix {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}}; \
   else \
     echo "[lint-no-fix] skipping: ruff ({{RUFF}}) not found"; \
   fi

# Typecheck (soft: skip if type checker missing)
typecheck *ARGS:
  @if command -v {{TYPES}} >/dev/null 2>&1; then \
     {{TYPES}} check {{ARGS}}; \
   else \
     echo "[typecheck] skipping: type checker ({{TYPES}}) not found"; \
   fi

# Test: prefer nox, fall back to pytest, otherwise skip
test *ARGS:
  @if command -v {{NOX}} >/dev/null 2>&1; then \
     {{NOX}} --session tests -- {{ARGS}}; \
   elif command -v {{PYTEST}} >/dev/null 2>&1; then \
     echo "[test] nox ({{NOX}}) not found; falling back to pytest ({{PYTEST}}) without nox sessions"; \
     {{PYTEST}} {{PY_TESTPATH}} {{ARGS}}; \
   else \
     echo "[test] skipping: neither nox ({{NOX}}) nor pytest ({{PYTEST}}) found"; \
   fi

# Test with coverage: prefer nox+coverage, fall back to plain pytest
test-full *ARGS:
  @if command -v {{NOX}} >/dev/null 2>&1; then \
     {{NOX}} --session tests -- --cov={{PYTHON_PACKAGE}} --cov-report=xml --cov-branch {{ARGS}}; \
   elif command -v {{PYTEST}} >/dev/null 2>&1; then \
     echo "[test-full] nox ({{NOX}}) not found; running pytest ({{PYTEST}}) without coverage"; \
     {{PYTEST}} {{PY_TESTPATH}} {{ARGS}}; \
   else \
     echo "[test-full] skipping: neither nox ({{NOX}}) nor pytest ({{PYTEST}}) found"; \
   fi

# Show coverage summary (soft: skip if showcov or coverage missing)
cov-summary *ARGS: test-full
  @if command -v {{SHOWCOV}} >/dev/null 2>&1; then \
     if [ -f coverage.xml ]; then \
       {{SHOWCOV}} --sections summary --format human {{ARGS}} || true; \
     else \
       echo "[cov-summary] skipping: coverage.xml not found (no coverage data)"; \
     fi; \
   else \
     echo "[cov-summary] skipping: showcov ({{SHOWCOV}}) not found"; \
   fi

# List uncovered lines (helper, soft)
cov *ARGS: test-full
  @if command -v {{SHOWCOV}} >/dev/null 2>&1; then \
     if [ -f coverage.xml ]; then \
       {{SHOWCOV}} --code --context 2,2 {{ARGS}} || true; \
     else \
       echo "[cov] skipping: coverage.xml not found (no coverage data)"; \
     fi; \
   else \
     echo "[cov] skipping: showcov ({{SHOWCOV}}) not found"; \
   fi

# Build (soft: skip if uv missing)
build *ARGS:
  @if command -v {{UV}} >/dev/null 2>&1; then \
     {{UV}} build {{ARGS}}; \
   else \
     echo "[build] skipping: uv ({{UV}}) not found"; \
   fi

# Build source distribution
sdist:
  @if command -v {{UV}} >/dev/null 2>&1; then \
     {{UV}} build --sdist; \
   else \
     echo "[sdist] skipping: uv ({{UV}}) not found"; \
   fi

# Build wheel
wheel:
  @if command -v {{UV}} >/dev/null 2>&1; then \
     {{UV}} build --wheel; \
   else \
     echo "[wheel] skipping: uv ({{UV}}) not found"; \
   fi

# Build Documentation (soft: skip if mkdocs missing)
build-docs:
  @if [ -x ./.venv/bin/mkdocs ]; then \
     ./.venv/bin/mkdocs build; \
   elif command -v mkdocs >/dev/null 2>&1; then \
     mkdocs build; \
   else \
     echo "[build-docs] skipping: mkdocs not found (neither ./.venv/bin/mkdocs nor mkdocs on PATH)"; \
   fi

# Build Documentation and serve locally (soft)
docs: build-docs
  @if [ -x ./.venv/bin/mkdocs ]; then \
     ./.venv/bin/mkdocs serve & \
       python3 -m webbrowser http://127.0.0.1:8000; \
   elif command -v mkdocs >/dev/null 2>&1; then \
     mkdocs serve & \
       python3 -m webbrowser http://127.0.0.1:8000; \
   else \
     echo "[docs] skipping: mkdocs not found (neither ./.venv/bin/mkdocs nor mkdocs on PATH)"; \
   fi

# Clean temporary files and caches (soft uv cache prune)
clean:
  @rm -rf **/__pycache__ || true
  @rm -rf .ruff_cache .pytest_cache .mypy_cache .pytype || true
  @rm -rf .coverage .coverage.* coverage.xml htmlcov || true
  @rm -rf dist build || true
  @if command -v {{UV}} >/dev/null 2>&1; then \
     {{UV}} cache prune || true; \
   else \
     echo "[clean] uv ({{UV}}) not found; skipping uv cache prune"; \
   fi

[private]
stash-untracked:
  @set -euo pipefail
  @if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
     ts="$(date -u +%Y%m%dT%H%M%SZ)"; \
     msg="scour:untracked:$ts"; \
     if git ls-files --others --exclude-standard --directory --no-empty-directory | grep -q .; then \
       git ls-files --others --exclude-standard -z \
         | xargs -0 git stash push -m "$msg" -- >/dev/null; \
       echo "Stashed untracked (non-ignored) files as: $msg"; \
     else \
       echo "No untracked (non-ignored) paths to stash."; \
     fi; \
   else \
     echo "[stash-untracked] not a git repository; skipping"; \
   fi

# Remove all files and directories that are ignored by git, except .venv
scour: clean stash-untracked
  @if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
     # -X: ignored only; -d: include dirs; -f: force; -e: exclude .venv \
     git clean -fXd -e .venv; \
   else \
     echo "[scour] not a git repository; skipping git clean"; \
   fi

# Pipelines

# CI-style check (but soft: skips missing tool steps instead of erroring)
check: setup-frozen lint-no-fix typecheck format-no-fix cov-summary

# Developer "fix" pipeline: autoformat, typecheck, docs build, and tests with soft fallbacks
fix: setup lint format typecheck build-docs test

