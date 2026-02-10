
from __future__ import annotations

from .record_ops import (
    _apply_filters,
    _deduplicate_statement_records,
    _deduplicate_branch_records,
)
from showcov.model.records import Record
from ._util import (
        _display_path,
)
from dataclasses import dataclass
from pathlib import Path
from typing import (
TYPE_CHECKING,
)
from showcov.model.metrics import pct
from showcov.model.report import (
    SummaryCounts,
    SummaryRow,
    SummarySection,
)
from showcov.model.types import (
SummarySort,
)
from .lines import (
    _uncovered_line_ranges,
)
if TYPE_CHECKING:
    from showcov.model.path_filter import PathFilter

TINY_STATEMENT_THRESHOLD = 3
def _summary_counts_stmt(records_for_file: list[tuple[int, int]]) -> tuple[int, int, int]:
    # records are (line,hits) for executable lines
    total = len(records_for_file)
    covered = sum(1 for _line, hits in records_for_file if hits > 0)
    missed = total - covered
    return total, covered, missed


def _summary_counts_br(
    records_for_file: list[tuple[int, tuple[int, int] | None, tuple[int, ...]]],
) -> tuple[int, int, int]:
    total = covered = missed = 0
    for _line, bc, _mb in records_for_file:
        if bc is None:
            continue
        c, t = bc
        total += t
        covered += c
        missed += max(0, t - c)
    return total, covered, missed


def _make_summary_counts(total: int, covered: int, missed: int) -> SummaryCounts:
    return SummaryCounts(
        total=total,
        covered=covered,
        missed=missed,
        percent=float(pct(covered, total)),
    )


def _combine_summary_counts(rows: tuple[SummaryRow, ...], attr: str) -> SummaryCounts:
    total = sum(getattr(r, attr).total for r in rows)
    covered = sum(getattr(r, attr).covered for r in rows)
    missed = sum(getattr(r, attr).missed for r in rows)
    return _make_summary_counts(total, covered, missed)

def _build_summary_section(
    records: list[Record],
    *,
    base: Path,
    filters: PathFilter | None,
    sort: SummarySort,
) -> SummarySection:
    files_all = sorted({r[0] for r in records})
    files = _apply_filters(files_all, filters=filters)

    rows: list[SummaryRow] = [
        _build_summary_row(
            f,
            records,
            base=base,
        )
        for f in files
    ]
    _sort_summary_rows(rows, sort)
    rows_tuple = tuple(rows)

    lines_counts = _combine_summary_counts(rows_tuple, "lines")
    statements_counts = _combine_summary_counts(rows_tuple, "statements")
    branches_counts = _combine_summary_counts(rows_tuple, "branches")

    files_with_branches = sum(1 for r in rows_tuple if r.branches.total > 0)
    return SummarySection(
        files=rows_tuple,
        lines=lines_counts,
        statements=statements_counts,
        branches=branches_counts,
        files_with_branches=int(files_with_branches),
        total_files=len(rows_tuple),
    )

def _build_summary_row(
    file: str,
    records: list[Record],
    *,
    base: Path,
) -> SummaryRow:
    # Per-line branch accounting can come from:
    # - condition-coverage => (covered,total)
    # - missing-branches (coverage.py) => ids of missing branches (may be present without condition-coverage)
    #
    # When merging multiple reports, prefer the largest denominator (best fidelity). If multiple
    # inputs share that denominator, keep the maximum covered count (prevents order-dependent undercount).
    stmt_records = _deduplicate_statement_records(file, records)
    stmt_total, stmt_cov, stmt_miss = _summary_counts_stmt(stmt_records)
    statements = _make_summary_counts(stmt_total, stmt_cov, stmt_miss)

    branch_records = _deduplicate_branch_records(file, records)
    br_total, br_cov, br_miss = _summary_counts_br(branch_records)
    branches = _make_summary_counts(br_total, br_cov, br_miss)

    # Hotness: uncovered statement lines and uncovered ranges
    ranges = _uncovered_line_ranges(stmt_records)
    uncovered_lines = sum((b - a + 1) for a, b in ranges)
    uncovered_ranges = len(ranges)
    lines_total = stmt_total
    lines_covered = lines_total - uncovered_lines
    lines = _make_summary_counts(lines_total, lines_covered, uncovered_lines)

    label = _display_path(file, base=base)
    untested = bool(statements.total > 0 and statements.covered == 0)
    tiny = bool(statements.total > 0 and statements.total <= TINY_STATEMENT_THRESHOLD)

    return SummaryRow(
        file=label,
        lines=lines,
        statements=statements,
        branches=branches,
        untested=untested,
        tiny=tiny,
        uncovered_lines=int(uncovered_lines),
        uncovered_ranges=int(uncovered_ranges),
    )


def _summary_statement_pct(row: SummaryRow) -> float:
    return row.statements.percent


def _summary_branch_pct(row: SummaryRow) -> float:
    return row.branches.percent


def _sort_key_missed_stmt(r: SummaryRow) -> tuple[int, int, str]:
    # bigger missed first; tie-break by uncovered lines then file
    return (-r.statements.missed, -r.uncovered_lines, r.file)


def _sort_key_missed_br(r: SummaryRow) -> tuple[int, int, str]:
    return (-r.branches.missed, -r.uncovered_lines, r.file)


def _sort_key_uncovered_lines(r: SummaryRow) -> tuple[int, int, str]:
    return (-r.uncovered_lines, -r.statements.missed, r.file)


def _sort_summary_rows(rows: list[SummaryRow], sort: SummarySort) -> None:

    # Back-compat alias
    if sort == SummarySort.FILE:
        rows.sort(key=lambda r: r.file)
    elif sort == SummarySort.STATEMENT_COVERAGE:
        rows.sort(key=_summary_statement_pct)
    elif sort == SummarySort.BRANCH_COVERAGE:
        rows.sort(key=_summary_branch_pct)
    elif sort == SummarySort.MISSED_STATEMENTS:
        rows.sort(key=_sort_key_missed_stmt)
    elif sort == SummarySort.MISSED_BRANCHES:
        rows.sort(key=_sort_key_missed_br)
    elif sort == SummarySort.UNCOVERED_LINES:
        rows.sort(key=_sort_key_uncovered_lines)
    else:
        rows.sort(key=_sort_key_missed_stmt)

