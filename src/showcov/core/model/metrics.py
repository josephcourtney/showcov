from __future__ import annotations

from showcov.core.model.types import FULL_COVERAGE


def pct(covered: int, total: int, *, full: float = float(FULL_COVERAGE)) -> float:
    """Return the coverage percentage, defaulting to `full` when no total exists."""
    return full if total == 0 else (covered / total) * full


__all__ = ["pct"]
