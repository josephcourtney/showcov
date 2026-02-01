from __future__ import annotations

from pathlib import Path
from typing import (
TYPE_CHECKING,
TypeAlias,
)
from showcov.core.model.report import (
    BranchCondition,
)
if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from showcov.core.model.path_filter import PathFilter

Record = tuple[
    str,  # file
    int,  # line
    int,  # hits
    tuple[int, int] | None,  # branch_counts
    tuple[int, ...],  # missing_branches
    tuple[BranchCondition, ...],  # conditions
]

BranchLineRec: TypeAlias = tuple[int, tuple[int, int] | None, tuple[int, ...]]



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


def _apply_filters(files: Iterable[str], *, filters: PathFilter | None) -> list[str]:
    if not filters:
        return list(files)
    # Keep in one place: let PathFilter do its rel/raw normalization
    pairs = [(f, None) for f in files]
    kept = filters.filter_files(pairs)
    return [path for path, _ in kept]










