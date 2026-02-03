
from __future__ import annotations

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
    SummaryTotals,
)
from showcov.model.types import (
SummarySort,
)
from .records import (
Record,
_apply_filters,
_deduplicate_statement_records,
_deduplicate_branch_records,
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

    totals = _aggregate_summary_totals(rows_tuple)
    files_with_branches = sum(1 for r in rows_tuple if r.branches.total > 0)
    return SummarySection(
        files=rows_tuple,
        totals=totals,
        files_with_branches=int(files_with_branches),
        total_files=len(rows_tuple),
    )

@dataclass(frozen=True, slots=True)
class _SummaryDerived:
    uncovered_lines: int
    uncovered_ranges: int
    statement_pct: float
    branch_pct: float | None
    untested: bool
    tiny: bool


def _compute_summary_derived(
    *,
    statements: SummaryCounts,
    branches: SummaryCounts,
    uncovered_lines: int,
    uncovered_ranges: int,
) -> _SummaryDerived:
    stmt_pct = pct(statements.covered, statements.total)
    br_pct = None if branches.total == 0 else pct(branches.covered, branches.total)
    untested = bool(statements.total > 0 and statements.covered == 0)
    tiny = bool(statements.total > 0 and statements.total <= TINY_STATEMENT_THRESHOLD)
    return _SummaryDerived(
        uncovered_lines=int(uncovered_lines),
        uncovered_ranges=int(uncovered_ranges),
        statement_pct=float(stmt_pct),
        branch_pct=(None if br_pct is None else float(br_pct)),
        untested=bool(untested),
        tiny=bool(tiny),
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
    statements = SummaryCounts(*_summary_counts_stmt(stmt_records))

    branch_records = _deduplicate_branch_records(file, records)
    branches = SummaryCounts(*_summary_counts_br(branch_records))

    # Hotness: uncovered statement lines and uncovered ranges
    ranges = _uncovered_line_ranges(stmt_records)
    uncovered_lines = sum((b - a + 1) for a, b in ranges)
    uncovered_ranges = len(ranges)

    derived = _compute_summary_derived(
        statements=statements,
        branches=branches,
        uncovered_lines=uncovered_lines,
        uncovered_ranges=uncovered_ranges,
    )

    label = _display_path(file, base=base)

    return SummaryRow(
        file=label,
        statements=statements,
        branches=branches,
        statement_pct=derived.statement_pct,
        branch_pct=derived.branch_pct,
        uncovered_lines=derived.uncovered_lines,
        uncovered_ranges=derived.uncovered_ranges,
        untested=derived.untested,
        tiny=derived.tiny,
    )


def _summary_statement_pct(row: SummaryRow) -> float:
    st = row.statements
    return pct(st.covered, st.total)


def _summary_branch_pct(row: SummaryRow) -> float:
    bt = row.branches
    return pct(bt.covered, bt.total)


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


def _aggregate_summary_totals(rows: tuple[SummaryRow, ...]) -> SummaryTotals:
    st_total = sum(r.statements.total for r in rows)
    st_cov = sum(r.statements.covered for r in rows)
    st_miss = sum(r.statements.missed for r in rows)
    br_total = sum(r.branches.total for r in rows)
    br_cov = sum(r.branches.covered for r in rows)
    br_miss = sum(r.branches.missed for r in rows)
    return SummaryTotals(
        statements=SummaryCounts(total=st_total, covered=st_cov, missed=st_miss),
        branches=SummaryCounts(total=br_total, covered=br_cov, missed=br_miss),
    )

