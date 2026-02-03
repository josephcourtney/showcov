from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from showcov.model.metrics import pct
from showcov.model.types import FULL_COVERAGE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from showcov.model.report import LinesSection, Report

_THRESHOLD_PATTERN = re.compile(r"^[a-zA-Z_-]+=")


@dataclass(frozen=True, slots=True)
class Threshold:
    """User-defined coverage thresholds.

    Fields
    ------
    statement:
        Minimum statement coverage percentage (0..100).
    branch:
        Minimum branch coverage percentage (0..100).
    misses:
        Maximum allowed uncovered statement lines (sum of uncovered ranges).
    """

    statement: float | None = None
    branch: float | None = None
    misses: int | None = None

    def is_empty(self) -> bool:
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
    """Parse a threshold expression like 'statements=90,branches=80,misses=10'."""
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


def evaluate(report: Report, thresholds: Sequence[Threshold]) -> ThresholdsResult:
    """Evaluate thresholds against a built Report.

    Requirements
    ------------
    - Statement/branch percentage thresholds require the summary section.
    - Misses threshold requires the lines section.

    Notes
    -----
    Misses are counted as uncovered statement lines (sum of UncoveredRange.line_count),
    not branch misses.
    """
    if not thresholds:
        return ThresholdsResult(passed=True, failures=[])

    failures: list[ThresholdFailure] = []

    need_stmt = any(t.statement is not None for t in thresholds)
    need_br = any(t.branch is not None for t in thresholds)
    need_miss = any(t.misses is not None for t in thresholds)

    stmt_pct: float | None = None
    br_pct: float | None = None
    miss_total: int | None = None

    if need_stmt or need_br:
        summary = report.sections.summary
        if summary is None:
            msg = "threshold evaluation requires the summary section in the report"
            raise ValueError(msg)

        st = summary.totals.statements
        bt = summary.totals.branches

        stmt_pct = pct(st.covered, st.total)
        br_pct = pct(bt.covered, bt.total)

    if need_miss:
        lines = report.sections.lines
        if lines is None:
            msg = "misses threshold evaluation requires the lines section in the report"
            raise ValueError(msg)
        miss_total = _count_line_misses(lines)

    if need_stmt:
        failures.extend(_evaluate_statement_thresholds(thresholds, stmt_pct))
    if need_br:
        failures.extend(_evaluate_branch_thresholds(thresholds, br_pct))
    if need_miss:
        failures.extend(_evaluate_miss_thresholds(thresholds, miss_total))

    return ThresholdsResult(passed=not failures, failures=failures)


def _evaluate_statement_thresholds(
    thresholds: Sequence[Threshold], stmt_pct: float | None
) -> list[ThresholdFailure]:
    actual = _require_percentage(stmt_pct, "statement")
    failures: list[ThresholdFailure] = []
    for t in thresholds:
        if t.statement is None:
            continue
        if actual < t.statement:
            failures.append(
                ThresholdFailure(
                    metric="statement",
                    required=t.statement,
                    actual=actual,
                    comparison=">=",
                )
            )
    return failures


def _evaluate_branch_thresholds(
    thresholds: Sequence[Threshold], br_pct: float | None
) -> list[ThresholdFailure]:
    actual = _require_percentage(br_pct, "branch")
    failures: list[ThresholdFailure] = []
    for t in thresholds:
        if t.branch is None:
            continue
        if actual < t.branch:
            failures.append(
                ThresholdFailure(
                    metric="branch",
                    required=t.branch,
                    actual=actual,
                    comparison=">=",
                )
            )
    return failures


def _evaluate_miss_thresholds(
    thresholds: Sequence[Threshold], miss_total: int | None
) -> list[ThresholdFailure]:
    actual = _require_count(miss_total, "miss")
    failures: list[ThresholdFailure] = []
    for t in thresholds:
        if t.misses is None:
            continue
        if actual > t.misses:
            failures.append(
                ThresholdFailure(
                    metric="misses",
                    required=t.misses,
                    actual=actual,
                    comparison="<=",
                )
            )
    return failures


def _require_percentage(value: float | None, metric: str) -> float:
    if value is None:
        msg = f"internal error: {metric} percentage was not computed for threshold evaluation"
        raise RuntimeError(msg)
    return value


def _require_count(value: int | None, metric: str) -> int:
    if value is None:
        msg = f"internal error: {metric} count was not computed for threshold evaluation"
        raise RuntimeError(msg)
    return value


def _parse_percentage(value: str, *, existing: float | None, token: str) -> float:
    if existing is not None:
        msg = f"duplicate percentage constraint in {token!r}"
        raise ValueError(msg)
    try:
        percent = float(value)
    except ValueError as exc:
        msg = f"invalid percentage value in {token!r}: {value!r}"
        raise ValueError(msg) from exc
    if percent < 0 or percent > float(FULL_COVERAGE):
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


def _count_line_misses(lines_section: LinesSection) -> int:
    # Typed as `LinesSection` from model.report, but kept unimported to avoid cycles.
    total = 0
    for f in lines_section.files:
        for r in f.uncovered:
            total += r.line_count
    return total


__all__ = [
    "Threshold",
    "ThresholdFailure",
    "ThresholdsResult",
    "evaluate",
    "parse_threshold",
]
