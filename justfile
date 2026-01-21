# ======================================================================
# Global shell + environment
# ======================================================================

set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := true
set export := true

# ----------------------------------------------------------------------
# Config (overridable via env/.env)
# ----------------------------------------------------------------------

MODE          := env("MODE", "dev")  # dev | debug | ci
PYTHON_PACKAGE := env("PYTHON_PACKAGE", "showcov")
PY_TESTPATH    := env("PY_TESTPATH", "tests")
PY_SRC         := env("PY_SRC", "src")
VERBOSE        := env("VERBOSE", "0")

# ----------------------------------------------------------------------
# Tool wrappers
# ----------------------------------------------------------------------

UV                  := "uv"
PYTHON              := justfile_directory() + "/.venv/bin/python"
RUFF                := justfile_directory() + "/.venv/bin/ruff"
PYTEST              := justfile_directory() + "/.venv/bin/pytest"
TY                  := justfile_directory() + "/.venv/bin/ty"
SHOWCOV             := justfile_directory() + "/.venv/bin/showcov"
MUTMUT              := justfile_directory() + "/.venv/bin/mutmut"
MKDOCS              := justfile_directory() + "/.venv/bin/mkdocs"
WILY                := justfile_directory() + "/.venv/bin/wily"
WILY_CACHE          := justfile_directory() + "/.wily"
WILY_CONFIG         := justfile_directory() + "/wily.cfg"
VULTURE             := justfile_directory() + "/.venv/bin/vulture"
RADON               := justfile_directory() + "/.venv/bin/radon"
JSCPD               := "npx --yes jscpd@4.0"
DIFF_COVER          := justfile_directory() + "/.venv/bin/diff-cover"
IMPORTLINTER        := justfile_directory() + "/.venv/bin/lint-imports"
IMPORTLINTER_CONFIG := justfile_directory() + "/import-linter.toml"

# ======================================================================
# Meta / Defaults
# ======================================================================

[private]
default: help

# List available recipes; also the default entry point
help:
  @just _log_start help
  @just --list --unsorted --list-prefix "  "
  @just _log_end help


# Print runtime configuration (paths + tool binaries)
env:
  @just _log_start env
  @echo "MODE={{MODE}}"
  @echo "PYTHON_PACKAGE={{PYTHON_PACKAGE}}"
  @echo "PY_TESTPATH={{PY_TESTPATH}}"
  @echo "PY_SRC={{PY_SRC}}"
  @echo "UV={{UV}}"
  @echo "RUFF={{RUFF}}"
  @echo "PYTEST={{PYTEST}}"
  @echo "TY={{TY}}"
  @echo "SHOWCOV={{SHOWCOV}}"
  @echo "MUTMUT={{MUTMUT}}"
  @echo "MKDOCS={{MKDOCS}}"
  @{{UV}} --version || true
  @{{PYTEST}} --version || true
  @{{RUFF}} --version || true
  @echo "WILY={{WILY}}"
  @echo "WILY_CACHE={{WILY_CACHE}}"
  @echo "WILY_CONFIG={{WILY_CONFIG}}"
  @echo "VULTURE={{VULTURE}}"
  @echo "RADON={{RADON}}"
  @echo "JSCPD={{JSCPD}}"
  @echo "DIFF_COVER={{DIFF_COVER}}"
  @just _log_end env

# ----------------------------------------------------------------------
# Logging helpers
# ----------------------------------------------------------------------

_log_start NAME:
  @bash -euo pipefail -c 'if [ "{{VERBOSE}}" != "0" ]; then printf "\n=== START: %s ===\n" "{{NAME}}"; fi'

_log_end NAME:
  @bash -euo pipefail -c 'if [ "{{VERBOSE}}" != "0" ]; then printf "=== END: %s ===\n\n" "{{NAME}}"; fi'

# ----------------------------------------------------------------------
# Quiet runners (brief on success, verbose on failure)
# ----------------------------------------------------------------------

_run NAME CMD:
  @bash -euo pipefail -c '\
    name="$1"; cmd="$2"; \
    set +e; out="$(bash -c "$cmd" 2>&1)"; status=$?; set -e; \
    if [ $status -eq 0 ]; then \
      echo "[1;32m✓ $name[0m"; \
    else \
      echo "[1;31m✗ $name[0m"; \
      echo "$out"; \
      exit $status; \
    fi' -- "{{NAME}}" {{quote(CMD)}}

_run_soft NAME CMD:
  @bash -euo pipefail -c '\
    name="$1"; cmd="$2"; \
    set +e; out="$(bash -c "$cmd" 2>&1)"; status=$?; set -e; \
    if [ $status -eq 0 ]; then \
      echo "[1;32m✓ $name[0m"; \
    else \
      echo "[1;31m✗ $name[0m"; \
      echo "$out"; \
      echo "[1;33m[warn][0m continuing after failure in $name" 1>&2; \
    fi' -- "{{NAME}}" {{quote(CMD)}}




# ======================================================================
# Bootstrap
# ======================================================================

# Bootstrap: refresh .venv via `uv sync`
setup:
  @just _log_start setup
  {{UV}} sync
  @just _log_end setup


# ======================================================================
# Code quality: lint / format / type-check
# ======================================================================

# Code Quality: Lint with `ruff check` and auto-fix where possible
[group('code quality')]
lint:
  @just _log_start lint
  {{RUFF}} check --fix {{PY_SRC}} {{PY_TESTPATH}} || true
  @just _log_end lint

# Code Quality: Check for linting violations with `ruff check` without modifying files
[group('code quality')]
lint-no-fix:
  @just _log_start lint-no-fix
  {{RUFF}} check --no-fix {{PY_SRC}} {{PY_TESTPATH}}
  @just _log_end lint-no-fix

# Code Quality: Lint import architecture (Import Linter)
[group('code quality')]
lint-imports:
  @just _log_start lint-imports
  bash -euo pipefail -c 'if [ ! -x {{IMPORTLINTER}} ]; then echo "[lint-imports] ERROR: lint-imports not found ({{IMPORTLINTER}}); install import-linter dev dep and run '\''just setup'\''"; exit 1; fi; set +e; output="$({{IMPORTLINTER}} --verbose --config {{IMPORTLINTER_CONFIG}} 2>&1)"; status=$?; set -e; if [ "$status" -ne 0 ]; then echo "[lint-imports] FAILED"; echo; echo "$output"; exit "$status"; else echo "[lint-imports] no import-linter contract violations detected."; fi'
  @just _log_end lint-imports

# Code Quality: Format with `ruff format` and auto-fix where possible
[group('code quality')]
format:
  @just _log_start format
  {{RUFF}} format {{PY_SRC}} {{PY_TESTPATH}} || true
  @just _log_end format

# Code Quality: Check for formatting violations with `ruff format` without modifying files
[group('code quality')]
format-no-fix:
  @just _log_start format-no-fix
  {{RUFF}} format --check {{PY_SRC}} {{PY_TESTPATH}}
  @just _log_end format-no-fix

# Code Quality: Typecheck with `ty` (if available)
[group('code quality')]
typecheck:
  @just _log_start typecheck
  bash -euo pipefail -c '\
    if [ -x {{TY}} ]; then \
      {{TY}} check {{PY_SRC}} {{PY_TESTPATH}}; \
      exit 0; \
    fi; \
    if [ "{{MODE}}" = "ci" ]; then \
      echo "[typecheck] ERROR: ty not found ({{TY}}) and MODE=ci requires typechecking"; \
      exit 1; \
    fi; \
    echo "[typecheck] skipping: ty not found ({{TY}}) (MODE={{MODE}})"; \
  '
  @just _log_end typecheck

# Code Quality: dead-code scan
[group('code quality')]
dead-code:
  @just _log_start dead-code
  {{VULTURE}} {{PY_SRC}} {{PY_TESTPATH}} || true
  @just _log_end dead-code

# Code Quality: complexity report
[group('code quality')]
complexity:
  @just _log_start complexity
  {{RADON}} cc -s -a {{PY_SRC}}
  @just _log_end complexity

# Code Quality: raw metrics (optional)
[group('code quality')]
complexity-raw:
  @just _log_start complexity-raw
  {{RADON}} raw {{PY_SRC}}
  @just _log_end complexity-raw

# Code Quality: strict complexity check (fail on high-complexity blocks)
[group('code quality')]
complexity-strict MIN_COMPLEXITY="11":
  @just _log_start complexity-strict
  bash -euo pipefail -c 'echo "[complexity-strict] Failing if any block has cyclomatic complexity >= ${MIN_COMPLEXITY}"; output="$({{RADON}} cc -s -n {{MIN_COMPLEXITY}} {{PY_SRC}} || true)"; if [ -n "$output" ]; then echo "[complexity-strict] Found blocks with complexity >= ${MIN_COMPLEXITY}:"; echo "$output"; exit 1; fi; echo "[complexity-strict] All blocks are below complexity ${MIN_COMPLEXITY}."'
  @just _log_end complexity-strict

# Code Quality: duplication detection
[group('code quality')]
dup:
  @just _log_start dup
  {{JSCPD}} --pattern "{{PY_SRC}}/*/*.py" --pattern "{{PY_SRC}}/*/*/*.py" --pattern "{{PY_SRC}}/*/*/*/*.py" --pattern "{{PY_TESTPATH}}/*/*.py" --pattern "{{PY_TESTPATH}}/*/*/*.py" --pattern "{{PY_TESTPATH}}/*/*/*/*.py" --reporters console
  @just _log_end dup


# ======================================================================
# Security / supply chain
# ======================================================================

# Security: Secret scan with trufflehog (report-only; does not fail if tool missing)
[group('security')]
sec-secrets:
  @just _log_start sec-secrets
  bash -euo pipefail -c 'if command -v trufflehog >/dev/null 2>&1; then tmp_file=$(mktemp); printf ".venv\nbuild\ndist\n" > "$tmp_file"; trufflehog filesystem . --exclude-paths "$tmp_file"; rm -f "$tmp_file"; else echo "[sec-secrets] skipping: trufflehog not found on PATH"; fi'
  @just _log_end sec-secrets

# Security: Dependency scan with pip-audit
[group('security')]
sec-deps:
  @just _log_start sec-deps
  bash -euo pipefail -c 'if [ -x .venv/bin/pip-audit ]; then PIP_NO_CACHE_DIR=1 .venv/bin/pip-audit; else echo "[sec-deps] ERROR: .venv/bin/pip-audit not found; run '\''just setup'\'' to install dev deps"; exit 1; fi'
  @just _log_end sec-deps


# ======================================================================
# Testing
# ======================================================================

# Testing: Run full test suite
[group('testing')]
test-pretty:
  @just _log_start test
  {{PYTEST}} --rich {{PY_TESTPATH}} || true
  @just _log_end test

[group('testing')]
test:
  @just _log_start test
  {{PYTEST}} {{PY_TESTPATH}} || true
  @just _log_end test

# Testing: Run full test suite and fail if any test fails
[group('testing')]
test-strict:
  @just _log_start test-strict
  {{PYTEST}} {{PY_TESTPATH}}
  @just _log_end test-strict

# Testing: Marker-driven test runner with graceful "no tests" handling
[group('testing')]
test-marker MARKER:
  @just _log_start test-marker
  bash -euo pipefail -c 'set +e; {{PYTEST}} {{PY_TESTPATH}} -m "{{MARKER}}"; status=$?; set -e; if [ "$status" -eq 5 ]; then echo "[{{MARKER}}] skipping: no tests marked with {{MARKER}} collected"; elif [ "$status" -ne 0 ]; then exit "$status"; fi'
  @just _log_end test-marker

# Testing: Run tests marked with "unit" and not marked with "slow"
[group('testing')]
test-fast:
  @just _log_start test-fast
  @just test-marker "unit and not slow"
  @just _log_end test-fast

# Testing: Run tests marked with "smoke"
[group('testing')]
test-smoke:
  @just _log_start test-smoke
  @just test-marker "smoke"
  @just _log_end test-smoke

# Testing: Run tests marked with "regression"
[group('testing')]
test-regression:
  @just _log_start test-regression
  @just test-marker "regression"
  @just _log_end test-regression

# Testing: Run tests marked with "performance"
[group('testing')]
test-performance:
  @just _log_start test-performance
  @just test-marker "performance"
  @just _log_end test-performance

# Testing: Run tests marked with "property_based"
[group('testing')]
test-property:
  @just _log_start test-property
  @just test-marker "property_based"
  @just _log_end test-property


# Testing: Run full test suite and report slowest tests
[group('testing')]
test-timed:
  @just _log_start test-timed
  {{PYTEST}} --durations=25 {{PY_TESTPATH}}
  @just _log_end test-timed

# ======================================================================
# Test Quality
# ======================================================================

# Test Quality: Summarize coverage results from last test execution
[group('test quality')]
cov:
  @just _log_start cov
  @bash -euo pipefail -c 'if [ -x {{SHOWCOV}} ]; then {{SHOWCOV}} --sections summary; else echo "[cov-lines] skipping: showcov ({{SHOWCOV}}) not found"; fi'
  @just _log_end cov

# Test Quality: List lines not covered by last test execution
[group('test quality')]
cov-lines:
  @just _log_start cov-lines
  bash -euo pipefail -c 'if [ -x {{SHOWCOV}} ]; then {{SHOWCOV}} --code --context 2,2 || true; else echo "[cov-lines] skipping: showcov ({{SHOWCOV}}) not found"; fi'
  @just _log_end cov-lines

# Test Quality: Run mutation testing on the test suite
[group('test quality')]
mutation *ARGS:
  @just _log_start mutation
  bash -euo pipefail -c 'if [ -x {{MUTMUT}} ]; then {{MUTMUT}} run {{ARGS}}; else echo "[mutmut] skipping: mutmut not found ({{MUTMUT}})"; fi'
  @just _log_end mutation

# Test Quality: Report mutation testing results
[group('test quality')]
mutation-report:
  @just _log_start mutation-report
  bash -euo pipefail -c 'if [ -x {{MUTMUT}} ]; then {{MUTMUT}} results; else echo "[mutation-report] skipping: mutmut not found ({{MUTMUT}})"; fi'
  @just _log_end mutation-report

# Test Quality: Test test flakiness by repeated runs of the test suite
[group('test quality')]
flake N='5':
  @just _log_start flake
  bash -euo pipefail -c 'set +e; rm -f .flake-log.txt; for i in $(seq 1 {{N}}); do echo "=== run $i ===" | tee -a .flake-log.txt; {{PYTEST}} {{PY_TESTPATH}} --maxfail=50 --randomly-seed=last | tee -a .flake-log.txt; done; set -e'
  @just _log_end flake

# Test Quality: coverage of changed lines vs main
[group('test quality')]
diff-cov BRANCH="origin/main":
  @just _log_start diff-cov
  bash -euo pipefail -c 'if [ ! -f .coverage.xml ]; then echo "[diff-cov] .coverage.xml not found; run '\''just test-strict'\'' first"; exit 1; fi; {{DIFF_COVER}} .coverage.xml --compare-branch={{BRANCH}}'
  @just _log_end diff-cov

# Test Quality: strict coverage of changed lines vs main with threshold
[group('test quality')]
diff-cov-strict BRANCH="origin/main" THRESHOLD="90":
  @just _log_start diff-cov-strict
  bash -euo pipefail -c 'if [ ! -f .coverage.xml ]; then echo "[diff-cov-strict] .coverage.xml not found; run '\''just test-strict'\'' first"; exit 1; fi; echo "[diff-cov-strict] Enforcing changed-line coverage >= ${THRESHOLD}% against ${BRANCH}"; {{DIFF_COVER}} .coverage.xml --compare-branch={{BRANCH}} --fail-under={{THRESHOLD}}'
  @just _log_end diff-cov-strict



# ======================================================================
# Metrics
# ======================================================================

# Metrics: build or update wily index incrementally
[group('metrics')]
wily-index:
  @just _log_start wily-index
  bash -euo pipefail -c 'stash_name=""; if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then if [ -n "$(git status --porcelain)" ]; then stash_name="wily:temp:$(date -u +%Y%m%dT%H%M%SZ)"; git stash push -u -m "$stash_name" >/dev/null; trap "git stash pop -q" EXIT; fi; fi; {{WILY}} --config {{WILY_CONFIG}} --cache {{WILY_CACHE}} build {{PY_SRC}} {{PY_TESTPATH}}'
  @just _log_end wily-index

# Metrics: report current metrics from index
[group('metrics')]
wily-metrics FILE="":
  @just _log_start wily-metrics
  @just wily-index
  bash -euo pipefail -c 'file="{{FILE}}"; if [ -z "$file" ]; then file="{{PY_SRC}}/{{PYTHON_PACKAGE}}/__init__.py"; fi; {{WILY}} --config {{WILY_CONFIG}} --cache {{WILY_CACHE}} report "$file"'
  @just _log_end wily-metrics

# Metrics: report stats for all files
[group('metrics')]
wily-stats:
  @just _log_start wily-stats
  @just wily-index
  bash -euo pipefail -c 'mapfile -t files < <(rg --files -g "*.py" {{PY_SRC}} {{PY_TESTPATH}}); if [ "${#files[@]}" -eq 0 ]; then echo "[wily-stats] no Python files found in {{PY_SRC}} or {{PY_TESTPATH}}"; exit 0; fi; {{WILY}} --config {{WILY_CONFIG}} --cache {{WILY_CACHE}} diff --all --no-detail "${files[@]}"'
  @just _log_end wily-stats


# ======================================================================
# Documentation
# ======================================================================

# Documentation: Build documentation using `mkdocs`
[group('documentation')]
build-docs:
  @just _log_start build-docs
  bash -euo pipefail -c 'if [ -x {{MKDOCS}} ]; then {{MKDOCS}} build; else echo "[build-docs] skipping: mkdocs not found ({{MKDOCS}} or on PATH)"; fi'
  @just _log_end build-docs

# Documentation: Serve the documentation site locally
[group('documentation')]
docs:
  @just _log_start docs
  @just build-docs
  bash -euo pipefail -c 'if [ -x {{MKDOCS}} ]; then python3 -m webbrowser http://127.0.0.1:8000; {{MKDOCS}} serve --livereload; else echo "[docs] skipping: mkdocs not found ({{MKDOCS}} or on PATH)"; fi'
  @just _log_end docs


# ======================================================================
# Build, packaging, publishing
# ======================================================================

# Production: Build Python artifacts with `uv build`
[group('production')]
build:
  @just _log_start build
  {{UV}} build
  @just _log_end build

# Production: Publish to PyPI using `uv publish`
[group('production')]
publish:
  @just _log_start publish
  {{UV}} publish
  @just _log_end publish


# ======================================================================
# Running
# ======================================================================

# Run: CLI mode via `python -m {{PYTHON_PACKAGE}}`
[group('run')]
cli:
  @just _log_start cli
  @just setup
  .venv/bin/python -m {{PYTHON_PACKAGE}}
  @just _log_end cli


# ======================================================================
# Cleaning / maintenance
# ======================================================================

# Cleaning: Remove caches/build artifacts and prune uv cache
[group('cleaning')]
clean:
  @just _log_start clean
  find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
  rm -rf .ruff_cache .pytest_cache .mypy_cache .pytype
  rm -rf .coverage .coverage.* coverage.xml htmlcov
  rm -rf dist build
  rm -rf logs
  rm -rf .hypothesis .ropeproject .wily mutants
  {{UV}} cache prune
  @just _log_end clean

# Cleaning: Stash untracked (non-ignored) files (used by `scour`)
[group('cleaning')]
stash-untracked:
  @just _log_start stash-untracked
  bash -euo pipefail -c 'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then msg="scour:untracked:$(date -u +%Y%m%dT%H%M%SZ)"; if git ls-files --others --exclude-standard --directory --no-empty-directory | grep -q .; then git ls-files --others --exclude-standard -z | xargs -0 git stash push -m "$msg" -- >/dev/null; echo "Stashed untracked (non-ignored) files as: $msg"; else echo "No untracked (non-ignored) paths to stash."; fi; else echo "[stash-untracked] not a git repository; skipping"; fi'
  @just _log_end stash-untracked

# Cleaning: Remove git-ignored files/dirs while keeping .venv
[group('cleaning')]
scour:
  @just _log_start scour
  @just clean
  @just stash-untracked
  bash -euo pipefail -c 'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then git clean -fXd -e .venv; else echo "[scour] not a git repository; skipping git clean"; fi'
  @just _log_end scour


# ======================================================================
# Composite flows
# ======================================================================

# Convenience: setup, lint, format, typecheck, build-docs, test, cov
[group('convenience')]
fix:
  @just _log_start fix
  @just _run_soft setup "just setup"
  @just _run_soft lint "just lint"
  @just _run_soft format "just format"
  @just _run_soft typecheck 'just typecheck'
  # @just _run_soft lint-imports 'just lint-imports'
  # @just _run_soft build-docs "just build-docs"
  @just test-pretty
  @just cov
  @just _log_end fix

# ----------------------------------------------------------------------
# MODE-driven orchestration
#
# MODE=dev   : fast, gating on core hygiene; avoids expensive gates by default.
# MODE=debug : minimal gating + increased diagnostics; skips expensive gates.
# MODE=ci    : full enforcement (equivalent to prior `check`).
# ----------------------------------------------------------------------

# Dev: fast-ish gating (no expensive metrics/security gates by default)
[group('dev')]
check-dev:
  @just _log_start check-dev
  @just _run setup "just setup"
  @just _run lint "just lint-no-fix"
  @just _run format "just format-no-fix"
  @just _run typecheck 'just typecheck'
  @just _run lint-imports 'just lint-imports'
  @just _run test "just test"
  @just cov
  @just _log_end check-dev

# Debug: prioritize iteration speed + diagnostics; do not block on heavy gates.
#
# Use `just test-marker <expr>` / `just test-fast` / `just test-smoke` for tighter loops.
[group('debug')]
check-debug:
  @just _log_start check-debug
  @just _run setup "just setup"
  @just _run lint "just lint-no-fix"
  @just _run format "just format-no-fix"
  @just _run typecheck 'just typecheck'
  @just _run test "just test --durations=25" # Run tests in "timed" mode to surface slow tests quickly.
  @just cov

  @just _log_end check-debug

# CI: full enforcement (previous `check` behavior)
[group('ci')]
check-ci:
  @just _log_start check-ci
  @just _run setup "{{UV}} sync"
  @just _run format "{{RUFF}} format --check {{PY_SRC}} {{PY_TESTPATH}}"
  @just _run lint "{{RUFF}} check --no-fix {{PY_SRC}} {{PY_TESTPATH}}"
  @just _run typecheck 'just typecheck'
  @just _run lint-imports 'just lint-imports'
  @just _run test "{{PYTEST}} -q {{PY_TESTPATH}}"
  @just _run metrics-gate 'just metrics-gate'
  @just cov
  @just _run sec-deps 'just sec-deps'
  @just _log_end check-ci

# Canonical entrypoint: dispatch based on MODE
check:
  @just _log_start check
  bash -euo pipefail -c '\
    case "{{MODE}}" in \
      dev)   just check-dev ;; \
      debug) just check-debug ;; \
      ci)    just check-ci ;; \
      *)     echo "[check] ERROR: invalid MODE={{MODE}} (expected: dev|debug|ci)"; exit 2 ;; \
    esac \
  '
  @just _log_end check

# Optional: a convenience alias for full local enforcement without changing MODE
check-full:
  @just _log_start check-full
  MODE=ci just check-ci
  @just _log_end check-full
