from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from defusedxml import ElementTree

from showcov.core.model.report import BranchCondition
from showcov.errors import InvalidCoverageXMLError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from showcov.inputs.types import ElementLike


@dataclass(frozen=True, slots=True)
class LineRecord:
    file: str
    line: int
    hits: int
    branch_counts: tuple[int, int] | None = None
    missing_branches: tuple[int, ...] = ()
    conditions: tuple[BranchCondition, ...] = ()


def read_root(path: Path) -> ElementLike:
    """Parse coverage XML and return the root element."""
    root = ElementTree.parse(path).getroot()
    tag = (root.tag or "").split("}")[-1]
    if tag.lower() != "coverage":
        msg = f"unexpected root tag {root.tag!r} in {path}"
        raise InvalidCoverageXMLError(msg)
    return root


_COND_RE = re.compile(r"(?P<pct>\d+)\s*%\s*\(\s*(?P<covered>\d+)\s*/\s*(?P<total>\d+)\s*\)")


def parse_condition_coverage(text: str) -> tuple[int, int] | None:
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
    out: list[int] = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return tuple(out)


def parse_conditions(line_elem: ElementLike) -> tuple[BranchCondition, ...]:
    out: list[BranchCondition] = []
    seen_numbers: set[int] = set()

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


def iter_line_records(root: ElementLike) -> Iterable[LineRecord]:
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
    "read_root",
]
