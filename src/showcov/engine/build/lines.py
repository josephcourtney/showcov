
from __future__ import annotations

from .record_ops import _apply_filters, _deduplicate_statement_records
from showcov.model.records import Record
from ._util import (
    _display_path,
    _group_consecutive,
)
from pathlib import Path
from typing import (
    TYPE_CHECKING,
)
from showcov.model.report import (
    FileCounts,
    LinesSection,
    LineSummary,
    UncoveredFile,
    UncoveredRange,
)
if TYPE_CHECKING:
    from showcov.model.path_filter import PathFilter

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




def _uncovered_line_ranges(stmt_records: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Compute uncovered [start,end] ranges from executable statement records (line,hits)."""
    lines = [ln for ln, hits in stmt_records if hits == 0]
    return _group_consecutive(lines)

