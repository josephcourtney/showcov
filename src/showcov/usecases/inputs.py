from collections.abc import Sequence
from pathlib import Path

from showcov.adapters.coverage.discover import resolve_coverage_paths as _resolve


def resolve_coverage_inputs(cov_paths: Sequence[Path] | None, *, cwd: Path) -> tuple[Path, ...]:
    return _resolve(cov_paths, cwd=cwd)
