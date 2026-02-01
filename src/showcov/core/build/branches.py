from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from showcov.core.model.report import (
    BranchCondition,
    BranchesSection,
    BranchGap,
)
from showcov.core.model.types import (
    FULL_COVERAGE,
    BranchMode,
)
from .records import (
    Record,
    _apply_filters,
)
from ._util import (
    _display_path,
)
if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from showcov.core.model.path_filter import PathFilter

class _BranchAccumulator(TypedDict):
    bc: tuple[int, int] | None
    mb: set[int]
    conds: dict[tuple[str, int], BranchCondition]

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
        return conds if any(is_partial(c) for c in conds) else ()
    # missing-only
    return tuple(c for c in conds if is_missing(c))





