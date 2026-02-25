from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from coverage import Coverage
from coverage.exceptions import CoverageException, DataError

from showcov.errors import CoverageInputDataError
from showcov.model.report import BranchCondition

if TYPE_CHECKING:
    from pathlib import Path

    from showcov.model.records import Record


class _AnalysisLike(Protocol):
    statements: object
    missing: object

    def has_arcs(self) -> bool: ...

    def branch_stats(self) -> dict[int, tuple[int, int]]: ...

    def missing_branch_arcs(self) -> object: ...

    def executed_branch_arcs(self) -> object: ...


@dataclass(slots=True)
class _LineData:
    hits: int = 0
    branch_counts: tuple[int, int] | None = None
    missing_branches: tuple[int, ...] = ()
    conditions: tuple[BranchCondition, ...] = ()


def _analysis_has_arcs(analysis: _AnalysisLike) -> bool:
    has_arcs = getattr(analysis, "has_arcs", None)
    if callable(has_arcs):
        return bool(has_arcs())
    return bool(has_arcs)


def _iter_sorted_ints(nums: Iterable[int]) -> list[int]:
    return sorted({int(n) for n in nums})


def _branch_dests_by_line(arcs: object) -> dict[int, set[int]]:
    """Normalize coverage.py branch arc structures into {from_line: {to_line, ...}}.

    coverage.py's Analysis APIs may return either:
    - Mapping[int, list[int]] of destinations (common), or
    - Iterable[tuple[int, int]] of (from, to) arcs.
    """
    if isinstance(arcs, Mapping):
        out: dict[int, set[int]] = {}
        for k, dests in arcs.items():
            if isinstance(k, int):
                frm = k
            elif isinstance(k, str):
                try:
                    frm = int(k)
                except ValueError:
                    continue
            else:
                continue
            try:
                out[frm] = {int(d) for d in dests}  # type: ignore[arg-type]
            except (TypeError, ValueError):
                out[frm] = set()
        return out

    out2: dict[int, set[int]] = {}
    for a in arcs or ():  # type: ignore[operator]
        try:
            frm_raw, to_raw = a
            frm = int(frm_raw)
            to = int(to_raw)
        except (TypeError, ValueError):
            continue
        out2.setdefault(frm, set()).add(to)
    return out2


def _build_branch_line_data(
    analysis: _AnalysisLike,
) -> dict[int, tuple[tuple[int, int], tuple[int, ...], tuple[BranchCondition, ...]]]:
    """Return per-line branch info: (branch_counts, missing_branch_idxs, conditions)."""
    stats: dict[int, tuple[int, int]] = analysis.branch_stats()
    missing_by_line = _branch_dests_by_line(analysis.missing_branch_arcs())
    executed_by_line = _branch_dests_by_line(analysis.executed_branch_arcs())

    out: dict[int, tuple[tuple[int, int], tuple[int, ...], tuple[BranchCondition, ...]]] = {}
    for line, pair in stats.items():
        # coverage.py returns (total_exits, taken_exits)
        total, taken = int(pair[0]), int(pair[1])
        if total <= 0:
            continue

        missing_dests = missing_by_line.get(int(line), set())
        executed_dests = executed_by_line.get(int(line), set())
        all_dests = sorted(missing_dests | executed_dests)
        dest_to_idx = {dest: i for i, dest in enumerate(all_dests)}

        missing_idxs = tuple(sorted(dest_to_idx[d] for d in missing_dests if d in dest_to_idx))

        # Per-branch condition coverage (0/100), plus line aggregate.
        conds: list[BranchCondition] = []
        for dest, idx in dest_to_idx.items():
            cov = 100 if dest in executed_dests else 0
            conds.append(BranchCondition(number=int(idx), type="jump", coverage=int(cov)))
        pct = 0 if total == 0 else round(100.0 * float(taken) / float(total))
        conds.append(BranchCondition(number=-1, type="line", coverage=int(pct)))

        out[int(line)] = ((int(taken), int(total)), missing_idxs, tuple(conds))

    return out


def _records_for_file(cov: Coverage, file: str) -> list[Record]:
    try:
        # coverage.py doesn't currently expose the rich branch analysis we need
        # (missing/executed branch arcs) through a fully public API.
        analysis = cast(
            "_AnalysisLike",
            cov._analyze(file),  # noqa: SLF001 # this is relatively stable and there is no public alternative
        )
    except (CoverageException, DataError, OSError, ValueError, TypeError) as exc:
        msg = f"failed to analyze {file}: {exc!s}"
        raise CoverageInputDataError(msg) from exc

    statements = _iter_sorted_ints(getattr(analysis, "statements", ()))
    missing = {int(n) for n in getattr(analysis, "missing", ())}

    per_line: dict[int, _LineData] = {ln: _LineData(hits=0 if ln in missing else 1) for ln in statements}

    if _analysis_has_arcs(analysis):
        try:
            branch_info = _build_branch_line_data(analysis)
        except (CoverageException, DataError, ValueError, TypeError) as exc:
            msg = f"failed to compute branch stats for {file}: {exc!s}"
            raise CoverageInputDataError(msg) from exc

        for ln, (bc, mb, conds) in branch_info.items():
            d = per_line.setdefault(ln, _LineData(hits=1))
            d.branch_counts = bc
            d.missing_branches = mb
            d.conditions = conds

    out: list[Record] = []
    for ln in sorted(per_line):
        d = per_line[ln]
        out.append((
            str(file),
            int(ln),
            int(d.hits),
            d.branch_counts,
            d.missing_branches,
            d.conditions,
        ))
    return out


def collect_coverage_db_records(paths: Sequence[Path]) -> list[Record]:
    """Collect `Record` tuples from Coverage.py SQLite `.coverage` files.

    Note: the SQLite DB only stores executed arcs/lines; we use coverage.py's
    analysis phase to determine executable statements and missing lines.
    """
    out: list[Record] = []

    for p in paths:
        try:
            cov = Coverage(data_file=str(p), branch=True)
            cov.load()
            data = cov.get_data()
        except (CoverageException, DataError, OSError, ValueError) as exc:
            msg = f"failed to read coverage sqlite database {p}: {exc!s}"
            raise CoverageInputDataError(msg) from exc

        for file in sorted(data.measured_files()):
            out.extend(_records_for_file(cov, str(file)))

    return out


__all__ = ["collect_coverage_db_records"]
