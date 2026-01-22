from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from showcov.model.report import BranchCondition

if TYPE_CHECKING:
    from collections.abc import Iterator

    from showcov.coverage.types import ElementLike

_COND_RE = re.compile(r"(?P<pct>\d+)\s*%\s*\(\s*(?P<covered>\d+)\s*/\s*(?P<total>\d+)\s*\)")


@dataclass(frozen=True, slots=True)
class LineRecord:
    file: str
    line: int
    hits: int
    # branch accounting from condition-coverage if present: (covered, total)
    branch_counts: tuple[int, int] | None = None
    # missing branch indices if present (coverage.py uses "missing-branches")
    missing_branches: tuple[int, ...] = ()
    conditions: tuple[BranchCondition, ...] = ()


def parse_condition_coverage(text: str) -> tuple[int, int] | None:
    """Parse Cobertura condition-coverage: '50% (1/2)' -> (covered,total)."""
    if not text:
        return None
    m = _COND_RE.search(text.strip())
    if not m:
        return None
    covered = int(m.group("covered"))
    total = int(m.group("total"))
    return covered, total


def _parse_missing_branches(text: str | None) -> tuple[int, ...]:
    if not text:
        return ()
    items: list[int] = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        try:
            items.append(int(part))
        except ValueError:
            continue
    return tuple(items)


def parse_conditions(line_elem: ElementLike) -> tuple[BranchCondition, ...]:
    """Parse <line> branch sub-elements (if present) into BranchCondition records.

    Cobertura may include:
      <line ... branch="true" condition-coverage="50% (1/2)">
        <conditions>
          <condition number="0" type="jump" coverage="0%"/>
        </conditions>
      </line>

    Many generators omit <conditions>; in that case we emit a synthetic condition.
    """
    out: list[BranchCondition] = []
    seen_numbers: set[int] = set()

    # explicit <conditions>/<condition>
    for cond in line_elem.findall(".//condition"):
        try:
            num = int(cond.get("number", "-1") or "-1")
        except ValueError:
            num = -1
        typ = cond.get("type")
        cov_raw = cond.get("coverage")
        cov: int | None = None
        if cov_raw:
            s = cov_raw.strip().rstrip("%")
            try:
                cov = int(float(s))
            except ValueError:
                cov = None
        out.append(BranchCondition(number=num, type=typ, coverage=cov))
        seen_numbers.add(num)

    missing = _parse_missing_branches(line_elem.get("missing-branches"))
    # represent missing branch ids explicitly as unknown coverage
    # (but avoid duping an explicit condition number if present)
    for b in missing:
        if b in seen_numbers:
            continue
        out.append(BranchCondition(number=b, type="branch", coverage=None))

    cc = parse_condition_coverage(line_elem.get("condition-coverage", "") or "")
    if cc is not None:
        covered, total = cc
        pct = 0 if total == 0 else round(100.0 * covered / total)
        out.append(BranchCondition(number=-1, type="line", coverage=pct))

    return tuple(out)


def iter_line_records(root: ElementLike) -> Iterator[LineRecord]:
    """Yield normalized line records from a Cobertura-style XML tree."""
    # Cobertura: coverage/packages/package/classes/class@filename and class/lines/line
    for cls in root.findall(".//class"):
        filename = cls.get("filename")
        if not filename:
            continue
        for line_elem in cls.findall("./lines/line"):
            n_raw = line_elem.get("number")
            hits_raw = line_elem.get("hits")
            if not n_raw or hits_raw is None:
                continue
            try:
                n = int(n_raw)
                hits = int(hits_raw)
            except ValueError:
                continue

            cc = parse_condition_coverage(line_elem.get("condition-coverage", "") or "")
            missing = _parse_missing_branches(line_elem.get("missing-branches"))
            conds = parse_conditions(line_elem)
            yield LineRecord(
                file=filename,
                line=n,
                hits=hits,
                branch_counts=cc,
                missing_branches=missing,
                conditions=conds,
            )


__all__ = [
    "LineRecord",
    "iter_line_records",
    "parse_condition_coverage",
    "parse_conditions",
]
