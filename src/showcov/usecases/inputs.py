from collections.abc import Sequence
from pathlib import Path

from showcov.adapters.coverage.discover_inputs import resolve_coverage_inputs as _resolve
from showcov.adapters.coverage.input_kind import CoverageInputBackend


def resolve_coverage_inputs(
    cov_paths: Sequence[Path] | None,
    *,
    cwd: Path,
    backend: CoverageInputBackend = CoverageInputBackend.AUTO,
) -> tuple[Path, ...]:
    return _resolve(cov_paths, cwd=cwd, backend=backend)
