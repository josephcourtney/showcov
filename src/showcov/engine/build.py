from __future__ import annotations

import collections.abc as cabc
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias, TypedDict

from showcov.coverage.parse import iter_line_records
from showcov.coverage.xml_reader import read_root
from showcov.model.report import (
    BranchCondition,
    BranchesSection,
    BranchGap,
    DiffSection,
    EnvironmentMeta,
    FileCounts,
    LinesSection,
    LineSummary,
    OptionsMeta,
    Report,
    ReportMeta,
    ReportSections,
    SummaryCounts,
    SummaryRow,
    SummarySection,
    SummaryTotals,
    UncoveredFile,
    UncoveredRange,
)
from showcov.model.types import FULL_COVERAGE, BranchMode, SummarySort

if TYPE_CHECKING:
    from collections.abc import Iterable

    from showcov.model.path_filter import PathFilter

Record = tuple[
    str,  # file
    int,  # line
    int,  # hits
    tuple[int, int] | None,  # branch_counts
    tuple[int, ...],  # missing_branches
    tuple[BranchCondition, ...],  # conditions
]


@dataclass(frozen=True, slots=True)
class BuildOptions:
    coverage_paths: tuple[Path, ...]
    base_path: Path
    filters: PathFilter | None
    sections: set[str]
    diff_base: Path | None
    branches_mode: BranchMode
    summary_sort: SummarySort
    want_aggregate_stats: bool
    want_file_stats: bool
    want_snippets: bool
    context_before: int
    context_after: int
    # These are presentation flags, but they are required by schema meta.options.
    meta_show_paths: bool = True
    meta_show_line_numbers: bool = True


TINY_STATEMENT_THRESHOLD = 3


class _BranchAccumulator(TypedDict):
    bc: tuple[int, int] | None
    mb: set[int]
    # key: (type,labelled-number) -> merged condition
    conds: dict[tuple[str, int], BranchCondition]


def _display_path(path: str, *, base: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(base.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError):
            return p.as_posix()
    return p.as_posix()


def _group_consecutive(nums: Iterable[int]) -> list[tuple[int, int]]:
    it = iter(sorted(set(nums)))
    out: list[tuple[int, int]] = []
    try:
        start = prev = next(it)
    except StopIteration:
        return out
    for n in it:
        if n == prev + 1:
            prev = n
            continue
        out.append((start, prev))
        start = prev = n
    out.append((start, prev))
    return out


def _collect_records(
    coverage_paths: Sequence[Path],
) -> list[Record]:
    """Collect normalized line records across all XML inputs.

    Returns tuples: (file, line, hits, branch_counts, missing_branches, conditions)
    """
    out: list[Record] = []
    for p in coverage_paths:
        root = read_root(p)
        out.extend(
            (rec.file, rec.line, rec.hits, rec.branch_counts, rec.missing_branches, rec.conditions)
            for rec in iter_line_records(root)
        )
    return out


def _apply_filters(files: Iterable[str], *, filters: PathFilter | None) -> list[str]:
    if not filters:
        return list(files)
    # Keep in one place: let PathFilter do its rel/raw normalization
    pairs = [(f, None) for f in files]
    kept = filters.filter_files(pairs)
    return [path for path, _ in kept]


def _build_lines_section(
    records: list[Record],
    *,
    base: Path,
    filters: PathFilter | None,
    want_aggregate_stats: bool,
    want_file_stats: bool,
) -> LinesSection:
    by_file: dict[str, list[tuple[int, int]]] = {}
    uncovered_total = 0

    files_all = sorted({r[0] for r in records})
    files = _apply_filters(files_all, filters=filters)

    # collect uncovered lines per file
    for file in files:
        # Use merged max-hits across all inputs so multi-report merges only mark
        # a statement line uncovered if every input missed it.
        stmt_records = _deduplicate_statement_records(file, records)
        lines = [line for line, hits in stmt_records if hits == 0]
        if not lines:
            by_file[file] = []
            continue
        ranges = _group_consecutive(lines)
        by_file[file] = ranges
        uncovered_total += sum((b - a + 1) for a, b in ranges)

    out_files: list[UncoveredFile] = []
    for file in files:
        ranges = tuple(UncoveredRange(start=a, end=b) for a, b in by_file.get(file, []))
        if not ranges:
            continue
        label = _display_path(file, base=base)
        counts = FileCounts(uncovered=sum(r.line_count for r in ranges), total=0) if want_file_stats else None
        out_files.append(UncoveredFile(file=label, uncovered=ranges, counts=counts))

    summary = LineSummary(uncovered=uncovered_total) if want_aggregate_stats else None
    return LinesSection(files=tuple(out_files), summary=summary)


def _build_branches_section(
    records: list[Record],
    *,
    base: Path,
    filters: PathFilter | None,
    mode: BranchMode,
) -> BranchesSection:
    files_all = sorted({r[0] for r in records})
    files = set(_apply_filters(files_all, filters=filters))
    accum = _aggregate_branch_records(records, files=files)

    gaps: list[BranchGap] = []
    for (f, line), data in sorted(accum.items()):
        all_conds = tuple(data["conds"].values())
        shown = _select_branch_conditions(all_conds, mode=mode)
        if not shown:
            continue
        # Stable ordering: non-line first, then line aggregate last
        shown_sorted = tuple(
            sorted(
                shown,
                key=lambda c: (
                    1 if (c.type or "").lower() == "line" else 0,
                    (c.type or "").lower(),
                    c.number,
                ),
            )
        )
        gaps.append(
            BranchGap(
                file=_display_path(f, base=base),
                line=line,
                conditions=shown_sorted,
            )
        )

    return BranchesSection(gaps=tuple(gaps))


def _aggregate_branch_records(
    records: list[Record],
    *,
    files: set[str],
) -> dict[tuple[str, int], _BranchAccumulator]:
    by_key: dict[tuple[str, int], _BranchAccumulator] = {}
    for f, line, _hits, bc, mb, conds in records:
        if f not in files:
            continue
        key = (f, line)
        d = by_key.setdefault(key, {"bc": None, "mb": set(), "conds": {}})

        # keep the branch_counts with the largest denominator (best fidelity)
        if bc is not None:
            prev = d["bc"]
            if prev is None or bc[1] > prev[1]:
                d["bc"] = bc

        if mb:
            bucket = d["mb"]
            if not isinstance(bucket, set):
                msg = (
                    "internal error: missing branches bucket for "
                    f"{f}:{line} is {type(bucket).__name__} instead of set"
                )
                raise TypeError(msg)
            bucket.update(mb)

        # merge rich conditions (including synthetic missing + line aggregate)
        cond_map = d["conds"]
        # ensure missing branches always show up as explicit "branch"/None, even if conds is empty
        for b in mb:
            k = ("branch", int(b))
            cond_map.setdefault(k, BranchCondition(number=int(b), type="branch", coverage=None))

        for c in conds:
            k = ((c.type or "branch").lower(), int(c.number))
            existing = cond_map.get(k)
            cond_map[k] = _merge_branch_condition(existing, c) if existing else c
    return by_key


def _merge_branch_condition(existing: BranchCondition, new: BranchCondition) -> BranchCondition:
    """Merge two conditions for the same (type,number).

    Strategy: preserve missing (None) if either side is missing; otherwise take the minimum
    percentage so merged reports show the worst coverage across inputs.
    """
    cov = None if existing.coverage is None or new.coverage is None else min(existing.coverage, new.coverage)
    typ = existing.type or new.type
    return BranchCondition(number=existing.number, type=typ, coverage=cov)


def _select_branch_conditions(
    conds: tuple[BranchCondition, ...],
    *,
    mode: BranchMode,
) -> tuple[BranchCondition, ...]:
    if not conds:
        return ()

    def is_missing(c: BranchCondition) -> bool:
        return c.coverage is None or c.coverage == 0

    def is_partial(c: BranchCondition) -> bool:
        return c.coverage is None or c.coverage < FULL_COVERAGE

    if mode == BranchMode.ALL:
        return conds
    if mode == BranchMode.PARTIAL:
        return tuple(c for c in conds if is_partial(c))
    # missing-only
    return tuple(c for c in conds if is_missing(c))


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


def _pct(covered: int, total: int) -> float:
    return 100.0 if total == 0 else (covered / total) * 100.0


def _uncovered_line_ranges(stmt_records: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Compute uncovered [start,end] ranges from executable statement records (line,hits)."""
    lines = [ln for ln, hits in stmt_records if hits == 0]
    return _group_consecutive(lines)


def _build_summary_section(
    records: list[Record],
    *,
    base: Path,
    filters: PathFilter | None,
    sort: SummarySort,
    baseline_records: list[Record] | None = None,
) -> SummarySection:
    files_all = sorted({r[0] for r in records})
    files = _apply_filters(files_all, filters=filters)

    # Optional baseline rows for deltas (keyed by display label for stability).
    baseline_by_file: dict[str, SummaryRow] = {}
    if baseline_records is not None:
        base_files_all = sorted({r[0] for r in baseline_records})
        base_files = _apply_filters(base_files_all, filters=filters)
        base_rows = [_build_summary_row(f, baseline_records, base=base) for f in base_files]
        baseline_by_file = {r.file: r for r in base_rows}

    rows: list[SummaryRow] = [
        _build_summary_row(
            f,
            records,
            base=base,
            baseline=baseline_by_file.get(_display_path(f, base=base)),
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


def _deduplicate_statement_records(
    file: str,
    records: list[Record],
) -> list[tuple[int, int]]:
    stmt_by_line: dict[int, int] = {}
    for ff, line, hits, _bc, _mb, _conds in records:
        if ff != file:
            continue
        stmt_by_line[line] = max(stmt_by_line.get(line, -1), hits)
    return [(ln, stmt_by_line[ln]) for ln in sorted(stmt_by_line)]


BranchLineRec: TypeAlias = tuple[int, tuple[int, int] | None, tuple[int, ...]]


def _deduplicate_branch_records(
    file: str,
    records: list[Record],
) -> list[BranchLineRec]:
    br_by_line: dict[int, tuple[int, int]] = {}
    missing_by_line: dict[int, set[int]] = {}
    max_idx_by_line: dict[int, int] = {}

    for ff, line, _hits, bc, mb, conds in records:
        if ff != file:
            continue
        if bc is not None:
            prev = br_by_line.get(line)
            if prev is None or bc[1] > prev[1] or (bc[1] == prev[1] and bc[0] > prev[0]):
                br_by_line[line] = bc
        if mb:
            bucket = missing_by_line.setdefault(line, set())
            bucket.update(mb)
            max_idx_by_line[line] = max(max_idx_by_line.get(line, -1), *mb)

        for c in conds:
            if c.number >= 0 and (c.type or "").lower() != "line":
                max_idx_by_line[line] = max(max_idx_by_line.get(line, -1), c.number)

    lines = sorted(set(br_by_line) | set(missing_by_line))
    out: list[BranchLineRec] = []
    for ln in lines:
        bc_sel = br_by_line.get(ln)
        missing = tuple(sorted(missing_by_line.get(ln, set())))

        if bc_sel is None and missing:
            # Heuristic: only as good as the source XML's numbering completeness.
            max_idx = max_idx_by_line.get(ln, max(missing))
            total = max(len(missing), max_idx + 1)
            covered = max(0, total - len(missing))
            bc_sel = (covered, total)

        out.append((ln, bc_sel, missing))

    return out


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
    stmt_pct = _pct(statements.covered, statements.total)
    br_pct = None if branches.total == 0 else _pct(branches.covered, branches.total)
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


@dataclass(frozen=True, slots=True)
class _SummaryDeltas:
    miss_stmt: int | None
    miss_br: int | None
    uncovered: int | None


def _compute_summary_deltas(
    *,
    statements: SummaryCounts,
    branches: SummaryCounts,
    uncovered_lines: int,
    baseline: SummaryRow | None,
) -> _SummaryDeltas:
    if baseline is None:
        return _SummaryDeltas(miss_stmt=None, miss_br=None, uncovered=None)
    return _SummaryDeltas(
        miss_stmt=int(statements.missed - baseline.statements.missed),
        miss_br=int(branches.missed - baseline.branches.missed),
        uncovered=int(uncovered_lines - baseline.uncovered_lines),
    )


def _build_summary_row(
    file: str,
    records: list[Record],
    *,
    base: Path,
    baseline: SummaryRow | None = None,
) -> SummaryRow:
    # Per-line branch accounting can come from:
    # - condition-coverage => (covered,total)
    # - missing-branches (coverage.py) => ids of missing branches (may be present without condition-coverage)
    #
    # When merging multiple reports, prefer the largest denominator (best fidelity). If multiple
    # inputs share that denominator, keep the maximum covered count (prevents order-dependent undercount).
    stmt_records = _deduplicate_statement_records(file, records)
    st_total, st_covered, st_missed = _summary_counts_stmt(stmt_records)
    statements = SummaryCounts(total=st_total, covered=st_covered, missed=st_missed)

    branch_records = _deduplicate_branch_records(file, records)
    br_total, br_covered, br_missed = _summary_counts_br(branch_records)
    branches = SummaryCounts(total=br_total, covered=br_covered, missed=br_missed)

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
    deltas = _compute_summary_deltas(
        statements=statements,
        branches=branches,
        uncovered_lines=uncovered_lines,
        baseline=baseline,
    )

    return SummaryRow(
        file=label,
        statements=statements,
        branches=branches,
        statement_pct=derived.statement_pct,
        branch_pct=derived.branch_pct,
        uncovered_lines=derived.uncovered_lines,
        uncovered_ranges=derived.uncovered_ranges,
        delta_missed_statements=deltas.miss_stmt,
        delta_missed_branches=deltas.miss_br,
        delta_uncovered_lines=deltas.uncovered,
        untested=derived.untested,
        tiny=derived.tiny,
    )


def _summary_statement_pct(row: SummaryRow) -> float:
    st = row.statements
    return float(FULL_COVERAGE) if st.total == 0 else float(FULL_COVERAGE) * st.covered / st.total


def _summary_branch_pct(row: SummaryRow) -> float:
    bt = row.branches
    return float(FULL_COVERAGE) if bt.total == 0 else float(FULL_COVERAGE) * bt.covered / bt.total


def _sort_key_missed_stmt(r: SummaryRow) -> tuple[int, int, str]:
    # bigger missed first; tie-break by uncovered lines then file
    return (-r.statements.missed, -r.uncovered_lines, r.file)


def _sort_key_missed_br(r: SummaryRow) -> tuple[int, int, str]:
    return (-r.branches.missed, -r.uncovered_lines, r.file)


def _sort_key_uncovered_lines(r: SummaryRow) -> tuple[int, int, str]:
    return (-r.uncovered_lines, -r.statements.missed, r.file)


def _summary_row_file_key(r: SummaryRow | cabc.Mapping[str, object] | Sequence[object]) -> str:
    # Newer/alternate row representation: dataclass/obj with .file
    if hasattr(r, "file"):
        return str(r.file)

    # Dict-like row
    if isinstance(r, cabc.Mapping):
        file_value = r.get("file")  # type: ignore[arg-type]
        if file_value is None:
            return ""
        return str(file_value)

    # Table row: list/tuple where first column is the file
    if isinstance(r, Sequence) and not isinstance(r, (str, bytes)):
        if not r:
            return ""
        first = r[0]
        # Sometimes first cell could itself be an object with .file
        return str(getattr(first, "file", first))

    msg = f"Unsupported summary row type: {type(r)!r}"
    raise TypeError(msg)


def _sort_summary_rows(rows: list[SummaryRow], sort: SummarySort) -> None:

    # Back-compat alias
    if sort == SummarySort.MISSES:
        sort = SummarySort.MISSED_STATEMENTS
    if sort == SummarySort.FILE:
        rows.sort(key=_summary_row_file_key)
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


def _ranges_to_set(files: Sequence[UncoveredFile]) -> set[tuple[str, int, int]]:
    out: set[tuple[str, int, int]] = set()
    for f in files:
        file = f.file or ""
        out.update((file, r.start, r.end) for r in f.uncovered)
    return out


def _build_diff_section(
    *,
    base_lines: LinesSection,
    cur_lines: LinesSection,
) -> DiffSection:
    base_set = _ranges_to_set(base_lines.files)
    cur_set = _ranges_to_set(cur_lines.files)

    new_set = cur_set - base_set
    res_set = base_set - cur_set

    def pack(items: set[tuple[str, int, int]]) -> tuple[UncoveredFile, ...]:
        by_file: dict[str, list[UncoveredRange]] = {}
        for file, a, b in items:
            by_file.setdefault(file, []).append(UncoveredRange(start=a, end=b))
        out: list[UncoveredFile] = []
        for file in sorted(by_file):
            rs = tuple(sorted(by_file[file], key=lambda r: (r.start, r.end)))
            out.append(UncoveredFile(file=file or None, uncovered=rs))
        return tuple(out)

    return DiffSection(new=pack(new_set), resolved=pack(res_set))


def build_report(opts: BuildOptions) -> Report:
    records = _collect_records(opts.coverage_paths)

    # Meta per schema
    meta = ReportMeta(
        environment=EnvironmentMeta(coverage_xml=", ".join(str(p) for p in opts.coverage_paths)),
        options=OptionsMeta(
            context_lines=max(opts.context_before, opts.context_after),
            with_code=bool(opts.want_snippets),
            show_paths=bool(opts.meta_show_paths),
            show_line_numbers=bool(opts.meta_show_line_numbers),
            aggregate_stats=bool(opts.want_aggregate_stats),
            file_stats=bool(opts.want_file_stats),
        ),
    )

    # Lines (built only when needed: lines or diff)
    lines: LinesSection | None = (
        _build_lines_section(
            records,
            base=opts.base_path,
            filters=opts.filters,
            want_aggregate_stats=opts.want_aggregate_stats,
            want_file_stats=opts.want_file_stats,
        )
        if ("lines" in opts.sections or "diff" in opts.sections)
        else None
    )

    # Branches
    branches = (
        _build_branches_section(records, base=opts.base_path, filters=opts.filters, mode=opts.branches_mode)
        if "branches" in opts.sections
        else None
    )

    # Diff
    diff: DiffSection | None = None
    if "diff" in opts.sections:
        if opts.diff_base is None:
            msg = "diff section requested but diff_base is None"
            raise ValueError(msg)
        base_root = read_root(opts.diff_base)
        base_records: list[Record] = [
            (r.file, r.line, r.hits, r.branch_counts, r.missing_branches, r.conditions)
            for r in iter_line_records(base_root)
        ]
        base_lines_sec = _build_lines_section(
            base_records,
            base=opts.base_path,
            filters=opts.filters,
            want_aggregate_stats=False,
            want_file_stats=False,
        )
        cur_lines_sec = (
            _build_lines_section(
                records,
                base=opts.base_path,
                filters=opts.filters,
                want_aggregate_stats=False,
                want_file_stats=False,
            )
            if lines is None
            else LinesSection(files=lines.files, summary=None)
        )
        diff = _build_diff_section(base_lines=base_lines_sec, cur_lines=cur_lines_sec)

    # If baseline exists and summary requested, also compute baseline records for deltas.
    baseline_records: list[Record] | None = None
    if opts.diff_base is not None and "summary" in opts.sections:
        base_root = read_root(opts.diff_base)
        baseline_records = [
            (r.file, r.line, r.hits, r.branch_counts, r.missing_branches, r.conditions)
            for r in iter_line_records(base_root)
        ]

    # Assemble present sections only
    sections = ReportSections(
        lines=lines if "lines" in opts.sections else None,
        branches=branches,
        summary=(
            _build_summary_section(
                records,
                base=opts.base_path,
                filters=opts.filters,
                sort=opts.summary_sort,
                baseline_records=baseline_records,
            )
            if "summary" in opts.sections
            else None
        ),
        diff=diff,
    )

    return Report(meta=meta, sections=sections)


__all__ = ["BuildOptions", "build_report"]
