"""Coverage threshold parsing and evaluation utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from showcov.core.core import UncoveredSection

_THRESHOLD_PATTERN = re.compile(r"^[a-zA-Z_-]+=")
_FULL_PERCENT = 100.0


@dataclass(frozen=True, slots=True)
class Threshold:
    """User-defined coverage thresholds."""

    statement: float | None = None
    branch: float | None = None
    misses: int | None = None

    def is_empty(self) -> bool:
        """Return ``True`` if the threshold does not constrain any metric."""
        return self.statement is None and self.branch is None and self.misses is None


@dataclass(frozen=True, slots=True)
class ThresholdFailure:
    """Details of a failed threshold evaluation."""

    metric: str
    required: float | int
    actual: float | int
    comparison: str


@dataclass(frozen=True, slots=True)
class ThresholdsResult:
    """Outcome of evaluating a collection of thresholds."""

    passed: bool
    failures: list[ThresholdFailure]


def parse_threshold(expression: str) -> Threshold:
    """Return a :class:`Threshold` parsed from *expression*."""
    if not expression or not expression.strip():
        msg = "threshold expression must be non-empty"
        raise ValueError(msg)

    stmt: float | None = None
    br: float | None = None
    miss: int | None = None
    tokens = [token.strip() for token in re.split(r"[,\s]+", expression) if token.strip()]

    for token in tokens:
        if "=" not in token or not _THRESHOLD_PATTERN.match(token):
            msg = f"invalid threshold token: {token!r}"
            raise ValueError(msg)
        key, raw_value = token.split("=", 1)
        key = key.strip().lower()
        value = raw_value.strip().rstrip("%")
        if key in {"stmt", "statement", "statements"}:
            stmt = _parse_percentage(value, existing=stmt, token=token)
        elif key in {"br", "branch", "branches"}:
            br = _parse_percentage(value, existing=br, token=token)
        elif key in {"miss", "misses"}:
            miss = _parse_int(value, existing=miss, token=token)
        else:
            msg = f"unknown threshold metric: {key!r}"
            raise ValueError(msg)

    threshold = Threshold(statement=stmt, branch=br, misses=miss)
    if threshold.is_empty():
        msg = "threshold must specify at least one metric"
        raise ValueError(msg)
    return threshold


def evaluate_thresholds(
    thresholds: Sequence[Threshold],
    *,
    totals: tuple[int, int, int, int],
    sections: Iterable[UncoveredSection] | None = None,
) -> ThresholdsResult:
    """Evaluate *thresholds* against aggregated coverage data."""
    if not thresholds:
        return ThresholdsResult(passed=True, failures=[])

    stmt_total, stmt_hit, br_total, br_hit = totals
    stmt_pct = _FULL_PERCENT if stmt_total == 0 else (stmt_hit / stmt_total) * _FULL_PERCENT
    br_pct = _FULL_PERCENT if br_total == 0 else (br_hit / br_total) * _FULL_PERCENT
    miss_total = _count_misses(sections)

    failures: list[ThresholdFailure] = []

    for threshold in thresholds:
        if threshold.statement is not None and stmt_pct < threshold.statement:
            failures.append(
                ThresholdFailure(
                    metric="statement",
                    required=threshold.statement,
                    actual=stmt_pct,
                    comparison=">=",
                )
            )
        if threshold.branch is not None and br_pct < threshold.branch:
            failures.append(
                ThresholdFailure(
                    metric="branch",
                    required=threshold.branch,
                    actual=br_pct,
                    comparison=">=",
                )
            )
        if threshold.misses is not None and miss_total > threshold.misses:
            failures.append(
                ThresholdFailure(
                    metric="misses",
                    required=threshold.misses,
                    actual=miss_total,
                    comparison="<=",
                )
            )

    return ThresholdsResult(passed=not failures, failures=failures)


def _parse_percentage(value: str, *, existing: float | None, token: str) -> float:
    if existing is not None:
        msg = f"duplicate percentage constraint in {token!r}"
        raise ValueError(msg)
    try:
        percent = float(value)
    except ValueError as exc:
        msg = f"invalid percentage value in {token!r}: {value!r}"
        raise ValueError(msg) from exc
    if percent < 0 or percent > _FULL_PERCENT:
        msg = f"percentage out of range in {token!r}: {percent}"
        raise ValueError(msg)
    return percent


def _parse_int(value: str, *, existing: int | None, token: str) -> int:
    if existing is not None:
        msg = f"duplicate numeric constraint in {token!r}"
        raise ValueError(msg)
    try:
        number = int(value)
    except ValueError as exc:
        msg = f"invalid integer value in {token!r}: {value!r}"
        raise ValueError(msg) from exc
    if number < 0:
        msg = f"numeric threshold must be non-negative in {token!r}: {number}"
        raise ValueError(msg)
    return number


def _count_misses(sections: Iterable[UncoveredSection] | None) -> int:
    if sections is None:
        return 0
    return sum(end - start + 1 for sec in sections for start, end in sec.ranges)


__all__ = [
    "Threshold",
    "ThresholdFailure",
    "ThresholdsResult",
    "evaluate_thresholds",
    "parse_threshold",
]
