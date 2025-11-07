set shell := ["bash", "-euo", "pipefail", "-c"]

# ---- Python Config ----
export PYTHON_PACKAGE := env("PYTHON_PACKAGE", "sweg")
export PY_TESTPATH := env("PY_TESTPATH", "tests")
export PY_SRC := env("PY_SRC", "src")

# ---- Help ----
# default:
#   @echo "Python recipes:"
#   @echo "  check-tools  setup"
#   @echo "  fmt  fmt-check  lint"
#   @echo "  typecheck  test"
#   @echo "  build  clean"

# ---- Tooling ----
check-tools:
  @command -v uv >/dev/null || { echo "[check-tools] missing: uv" >&2; exit 1; }

setup:
  uv sync

# ---- Format ----
format:
  uv run ruff format {{PY_SRC}} {{PY_TESTPATH}}

format-check:
  uv run ruff format --check {{PY_SRC}} {{PY_TESTPATH}}

# ---- Lint ----
lint:
  uv run ruff check {{PY_SRC}} {{PY_TESTPATH}}

# ---- Typecheck ----
typecheck:
  uv run ty check

# ---- Test ----
test:
  uv run pytest -q {{PY_TESTPATH}}

# ---- Coverage ----
cov:
  showcov report --sections lines,summary --code --color --line-numbers --file-stats --stats --paths

# ---- Build ----
build:
  uv build

# ---- Clean ----
clean:
  rm -rf **/__pycache__
  rm -rf .pytest_cache
  rm -rf .ruff_cache
  rm -rf .coverage
  rm -rf .coverage.*
  rm -rf coverage.xml
  rm -rf dist build
  uv cache prune || true

scour: clean
  rm -rf uv.lock
  rm -rf .venv
  uv cache prune || true

qa: setup lint typecheck format test

