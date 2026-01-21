from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from showcov.errors import CoverageXMLNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence


def resolve_coverage_paths(cov_paths: Sequence[Path] | None) -> tuple[Path, ...]:
    """Resolve coverage XML inputs.

    Rules
    -----
    - If `cov_paths` are provided: they must exist.
    - Else: try `coverage.xml` in the current working directory.
    """
    paths = tuple(cov_paths or ())
    if paths:
        missing = [p for p in paths if not p.exists()]
        if missing:
            msg = f"coverage XML not found: {', '.join(str(p) for p in missing)}"
            raise CoverageXMLNotFoundError(msg)
        return tuple(p.resolve() for p in paths)

    default = Path("coverage.xml")
    if default.exists():
        return (default.resolve(),)

    msg = "no coverage XML provided (use --cov) and coverage.xml not found"
    raise CoverageXMLNotFoundError(msg)


__all__ = ["resolve_coverage_paths"]
