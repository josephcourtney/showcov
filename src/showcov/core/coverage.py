"""Coverage XML aggregation utilities (pure core, no UI).

This module provides reusable helpers to:
  * discover coverage XML files
  * parse per-line stats (including branch condition coverage)
  * aggregate per-file statement/branch totals & hits
  * compute per-file summary rows and overall totals

The functions are intentionally UI-agnostic so they can be consumed by
CLI commands or output formatters without pulling in Rich or Click.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree as ET

from showcov.core.files import normalize_path

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Iterable, Mapping, Sequence


# --------------------------- Models ------------------------------------------
@dataclass(frozen=True)
class LineAgg:
    hits: int = 0
    br_cov: int = 0
    br_tot: int = 0


@dataclass
class FileAgg:
    lines: dict[int, LineAgg]  # lineno -> agg


FULL_COVERAGE = 100


# --------------------------- Branch gap models -------------------------------
@dataclass(frozen=True)
class BranchCondition:
    number: int
    type: str | None
    coverage: int | None  # percentage, 0..100 (None when unknown)


@dataclass(frozen=True)
class BranchGap:
    file: Path
    line: int
    conditions: list[BranchCondition]  # only uncovered (coverage == 0)


# --------------------------- Discovery/Parsing -------------------------------
def find_coverage_xml_paths(root: Path, patterns: Sequence[str]) -> list[Path]:
    """Return a de-duplicated list of coverage XML files under *root*."""
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in patterns:
        for p in root.rglob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def read_coverage_xml_file(path: Path) -> ET.Element | None:
    """Parse a coverage XML file, returning its root element or ``None``."""
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        return None


def read_all_coverage_roots(root: Path, patterns: Sequence[str]) -> list[ET.Element]:
    """Parse all coverage XML files matching *patterns* under *root*."""
    roots: list[ET.Element] = []
    for path in find_coverage_xml_paths(root, patterns):
        r = read_coverage_xml_file(path)
        if r is not None:
            roots.append(r)
    return roots


_cond_re = re.compile(r"\(?\s*(\d+)\s*/\s*(\d+)\s*\)?")


def parse_condition_coverage(text: str) -> tuple[int, int] | None:
    """Parse condition-coverage values like '50% (1/2)', '(1/2)', or '1/2'."""
    m = _cond_re.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def iter_lines(root: ET.Element) -> Iterable[tuple[str, int, int, int, int]]:
    """Yield per-line stats: (filename, lineno, hits, br_covered, br_total)."""
    for cls in root.findall(".//class"):
        fname = cls.get("filename", "")
        lines_node = cls.find("lines")
        if not fname or lines_node is None:
            continue
        for ln in lines_node.findall("line"):
            try:
                lineno = int(ln.get("number", "0"))
            except ValueError:
                continue
            hits = int(ln.get("hits", "0") or 0)
            br_cov = 0
            br_tot = 0
            if ln.get("branch") == "true":
                cc = ln.get("condition-coverage") or ""
                parsed = parse_condition_coverage(cc)
                if parsed is not None:
                    br_cov, br_tot = parsed
            yield fname, lineno, hits, br_cov, br_tot


def _parse_missing_branches(line_elem: ET.Element) -> list[BranchCondition]:
    """Fallback parser that uses ``missing-branches`` when no <conditions> exist."""
    attr = (line_elem.get("missing-branches") or "").strip()
    if not attr:
        return []
    tokens = [tok.strip() for tok in attr.split(",") if tok.strip()]
    out: list[BranchCondition] = []
    for raw in tokens:
        try:
            idx = int(raw)
            typ = "line"
        except ValueError:
            idx = -1
            typ = raw
        out.append(BranchCondition(number=idx, type=typ, coverage=None))
    return out


def _parse_uncovered_conditions(line_elem: ET.Element) -> list[BranchCondition]:
    """Return branch conditions on this line that are not fully covered."""
    out: list[BranchCondition] = []
    conds = line_elem.find("conditions")
    if conds is not None:
        for c in conds.findall("condition"):
            # Coverage attribute is typically like "0%" or "100%"
            cov_text = (c.get("coverage") or "").strip().rstrip("%")
            try:
                pct = int(cov_text)
            except ValueError:
                continue
            if pct >= FULL_COVERAGE:
                continue
            num = c.get("number")
            typ = c.get("type")
            try:
                idx = int(num) if num is not None else -1
            except ValueError:
                idx = -1
            out.append(BranchCondition(number=idx, type=typ, coverage=pct))
    if out:
        return out
    return _parse_missing_branches(line_elem)


def gather_uncovered_branches_from_xml(xml_file: Path) -> list[BranchGap]:
    """Extract lines and specific branch conditions that are uncovered (0%)."""
    try:
        tree = ET.parse(xml_file)
    except ET.ParseError as exc:
        msg = f"{xml_file}: failed to parse coverage XML: {exc}"
        raise ET.ParseError(msg) from exc
    root = tree.getroot()
    if root is None or root.tag != "coverage":
        msg = f"Invalid root element: expected <coverage>, got <{getattr(root, 'tag', None)}>"
        raise ValueError(msg)

    gaps: list[BranchGap] = []
    for cls in root.findall(".//class"):
        fname = cls.get("filename") or ""
        fpath = Path(fname).resolve()
        lines_node = cls.find("lines")
        if lines_node is None:
            continue
        for ln in lines_node.findall("line"):
            if ln.get("branch") != "true":
                continue
            # Only care about branch lines with not-fully-covered conditions
            conds = _parse_uncovered_conditions(ln)
            if not conds:
                continue
            try:
                lineno = int(ln.get("number", "0"))
            except ValueError:
                continue
            gaps.append(BranchGap(file=fpath, line=lineno, conditions=conds))
    return gaps


# --------------------------- Aggregation -------------------------------------
def _compile_filters(include: str | None, exclude: str | None) -> Callable[[Path], bool]:
    inc = re.compile(include) if include else None
    exc = re.compile(exclude) if exclude else None

    def ok(p: Path) -> bool:
        s = str(p)
        if inc and not inc.search(s):
            return False
        return not (exc and exc.search(s))

    return ok


def aggregate(
    roots: Sequence[ET.Element],
    include: str | None,
    exclude: str | None,
) -> dict[str, FileAgg]:
    """Aggregate per-line stats across multiple coverage roots.

    For each file+line:
      * hits      = max(hits across reports)
      * br_cov    = max(covered branches across reports)
      * br_tot    = max(total branches across reports)
    """
    ok = _compile_filters(include, exclude)
    acc: dict[str, FileAgg] = {}
    for root in roots:
        for fname, lineno, hits, br_cov, br_tot in iter_lines(root):
            fpath = Path(fname).resolve()
            if not ok(fpath):
                continue
            key = str(fpath)
            fa = acc.setdefault(key, FileAgg(lines={}))
            la = fa.lines.get(lineno, LineAgg())
            fa.lines[lineno] = LineAgg(
                hits=max(la.hits, hits),
                br_cov=max(la.br_cov, br_cov),
                br_tot=max(la.br_tot, br_tot),
            )
    return acc


# --------------------------- Summarisation -----------------------------------
def compute_file_rows(
    acc: Mapping[str, FileAgg],
) -> tuple[list[tuple], tuple[int, int, int, int]]:
    """Return per-file rows and global (stmt_tot, stmt_hit, br_tot, br_hit)."""
    rows_raw: list[tuple] = []
    sum_stmt_tot = sum_stmt_hit = sum_br_tot = sum_br_hit = 0
    for fpath, fa in acc.items():
        stmt_tot = len(fa.lines)
        stmt_hit = sum(1 for la in fa.lines.values() if la.hits > 0)
        br_tot = sum(la.br_tot for la in fa.lines.values())
        br_hit = sum(la.br_cov for la in fa.lines.values())
        rows_raw.append((fpath, stmt_tot, stmt_hit, stmt_tot - stmt_hit, br_tot, br_hit, br_tot - br_hit))
        sum_stmt_tot += stmt_tot
        sum_stmt_hit += stmt_hit
        sum_br_tot += br_tot
        sum_br_hit += br_hit
    return rows_raw, (sum_stmt_tot, sum_stmt_hit, sum_br_tot, sum_br_hit)


def sort_rows(
    rows_raw: list[tuple],
    *,
    key: str = "file",
) -> None:
    """Sort *rows_raw* in-place by one of: file | stmt_cov | br_cov | miss."""

    def stmt_cov(row: tuple) -> float | None:
        tot, hit = row[1], row[2]
        return (100.0 * hit / tot) if tot else None

    def br_cov(row: tuple) -> float | None:
        tot, hit = row[4], row[5]
        return (100.0 * hit / tot) if tot else None

    keyfuncs = {
        "file": lambda r: (Path(r[0]), r[0]),
        "stmt_cov": lambda r: (-(stmt_cov(r) or -1), r[0]),
        "br_cov": lambda r: (-(br_cov(r) or -1), r[0]),
        "miss": lambda r: (-(r[3] + r[6]), r[0]),
    }
    rows_raw.sort(key=keyfuncs[key])


def relativize(path_str: str, *, rel_to: Path | None) -> str:
    """Return *path_str* made relative to *rel_to* when possible."""
    p = Path(path_str)
    if rel_to is None:
        return p.as_posix()
    return normalize_path(p, base=rel_to).as_posix()


__all__ = [
    "BranchCondition",
    "BranchGap",
    "FileAgg",
    "LineAgg",
    "aggregate",
    "compute_file_rows",
    "find_coverage_xml_paths",
    "gather_uncovered_branches_from_xml",
    "iter_lines",
    "parse_condition_coverage",
    "read_all_coverage_roots",
    "read_coverage_xml_file",
    "relativize",
    "sort_rows",
]
