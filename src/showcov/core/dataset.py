"""Unified coverage dataset and section builders."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from defusedxml import ElementTree as ET  # noqa: N817

from showcov.core.core import (
    UncoveredSection,
    build_sections,
    group_consecutive_numbers,
    merge_blank_gap_groups,
)
from showcov.core.coverage import (
    FULL_COVERAGE,
    BranchCondition,
    BranchGap,
    parse_condition_coverage,
    read_coverage_xml_file,
)
from showcov.core.exceptions import InvalidCoverageXMLError
from showcov.core.files import normalize_path, read_file_lines
from showcov.core.types import BranchMode, FilePath, LineRange, SummarySort

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
    from xml.etree.ElementTree import Element as XmlElement  # noqa: S405

    from showcov.core.path_filter import PathFilter


@dataclass(slots=True)
class LineCoverage:
    """Aggregated coverage information for a single line."""

    hits: int = 0
    branches_covered: int = 0
    branches_total: int = 0
    _conditions: dict[tuple[int, str | None], BranchCondition] = field(
        default_factory=dict,
        repr=False,
    )

    def update(
        self,
        *,
        hits: int,
        branches_covered: int,
        branches_total: int,
        conditions: Sequence[BranchCondition],
    ) -> None:
        """Merge coverage data from a single XML entry into this record."""
        self.hits = max(self.hits, hits)
        self.branches_covered = max(self.branches_covered, branches_covered)
        self.branches_total = max(self.branches_total, branches_total)

        for cond in conditions:
            key = (cond.number, cond.type)
            existing = self._conditions.get(key)
            best = _max_coverage(existing.coverage if existing else None, cond.coverage)
            self._conditions[key] = BranchCondition(
                number=cond.number,
                type=cond.type,
                coverage=best,
            )

    def iter_conditions(self) -> Iterator[BranchCondition]:
        yield from sorted(
            self._conditions.values(),
            key=lambda c: (
                (c.type or ""),
                c.number,
            ),
        )

    def iter_conditions_for_mode(self, mode: BranchMode) -> Iterator[BranchCondition]:
        if mode is BranchMode.ALL:
            yield from self.iter_conditions()
            return
        for cond in self.iter_conditions():
            coverage = cond.coverage
            if mode is BranchMode.MISSING_ONLY and (coverage or 0) != 0:
                continue
            if mode is BranchMode.PARTIAL and coverage is not None and coverage >= FULL_COVERAGE:
                continue
            yield cond


@dataclass(slots=True)
class FileCoverage:
    """Aggregated coverage information for a file."""

    path: FilePath
    lines: dict[int, LineCoverage] = field(default_factory=dict)

    def line(self, line_no: int) -> LineCoverage:
        return self.lines.setdefault(line_no, LineCoverage())

    def uncovered_lines(self) -> list[int]:
        return sorted(ln for ln, cov in self.lines.items() if cov.hits == 0)

    def branch_gaps(self, mode: BranchMode) -> list[BranchGap]:
        gaps: list[BranchGap] = []
        for line_no in sorted(self.lines):
            cov = self.lines[line_no]
            if cov.branches_total == 0:
                continue
            conds = list(cov.iter_conditions_for_mode(mode))
            if not conds and mode is not BranchMode.ALL:
                continue
            gaps.append(BranchGap(file=self.path, line=line_no, conditions=conds))
        return gaps


def _max_coverage(first: int | None, second: int | None) -> int | None:
    if first is None:
        return second
    if second is None:
        return first
    return max(first, second)


def _compile_filters(include: str | None, exclude: str | None) -> Callable[[Path], bool]:
    inc = re.compile(include) if include else None
    exc = re.compile(exclude) if exclude else None

    def allow(path: Path) -> bool:
        text = str(path)
        if inc and not inc.search(text):
            return False
        return not (exc and exc.search(text))

    return allow


def _iter_conditions(line_elem: XmlElement) -> list[BranchCondition]:
    conds = line_elem.find("conditions")
    out: list[BranchCondition] = []
    if conds is not None:
        for c in conds.findall("condition"):
            num_raw = c.get("number")
            try:
                number = int(num_raw) if num_raw is not None else -1
            except ValueError:
                number = -1
            typ = c.get("type")
            cov_text = (c.get("coverage") or "").strip().rstrip("%")
            try:
                coverage = int(cov_text)
            except ValueError:
                coverage = None
            out.append(BranchCondition(number=number, type=typ, coverage=coverage))

    missing = (line_elem.get("missing-branches") or "").strip()
    if not missing:
        return out
    for token in (t.strip() for t in missing.split(",")):
        if not token:
            continue
        try:
            number = int(token)
        except ValueError:
            continue
        out.append(BranchCondition(number=number, type="line", coverage=None))
    return out


@dataclass(slots=True)
class CoverageDataset:
    """Aggregated coverage data built from one or more XML reports."""

    base_path: FilePath | None = None
    files: dict[FilePath, FileCoverage] = field(default_factory=dict)

    @classmethod
    def from_roots(
        cls,
        roots: Sequence[XmlElement],
        *,
        base_path: FilePath | None = None,
        include: str | None = None,
        exclude: str | None = None,
    ) -> CoverageDataset:
        dataset = cls(base_path=base_path)
        for root in roots:
            dataset.add_root(root, include=include, exclude=exclude)
        return dataset

    @classmethod
    def from_xml_files(
        cls,
        files: Iterable[Path],
        *,
        base_path: FilePath | None = None,
        include: str | None = None,
        exclude: str | None = None,
    ) -> CoverageDataset:
        roots: list[XmlElement] = []
        for path in files:
            root = read_coverage_xml_file(path)
            if root is None:
                msg = f"{path}: failed to parse coverage XML"
                raise ET.ParseError(msg)
            roots.append(root)
        return cls.from_roots(roots, base_path=base_path, include=include, exclude=exclude)

    def add_root(
        self,
        root: XmlElement,
        *,
        include: str | None = None,
        exclude: str | None = None,
    ) -> None:
        if root.tag != "coverage":
            msg = f"Invalid root element: expected <coverage>, got <{root.tag}>"
            raise InvalidCoverageXMLError(msg)

        allow = _compile_filters(include, exclude)

        for cls_elem in root.findall(".//class"):
            filename = cls_elem.get("filename")
            if not filename:
                continue
            path = Path(filename).resolve()
            if not allow(path):
                continue

            for line_elem in cls_elem.findall("lines/line"):
                try:
                    line_no = int(line_elem.get("number", "0"))
                except ValueError:
                    continue
                hits_raw = line_elem.get("hits", "0") or "0"
                try:
                    hits = int(hits_raw)
                except ValueError:
                    continue

                branches_covered = branches_total = 0
                if line_elem.get("branch") == "true":
                    parsed = parse_condition_coverage(line_elem.get("condition-coverage") or "")
                    if parsed is not None:
                        branches_covered, branches_total = parsed

                conditions = _iter_conditions(line_elem)

                file_cov = self.files.setdefault(path, FileCoverage(path=path))
                file_cov.line(line_no).update(
                    hits=hits,
                    branches_covered=branches_covered,
                    branches_total=branches_total,
                    conditions=conditions,
                )

    def iter_files(self) -> Iterator[FileCoverage]:
        for path in sorted(self.files, key=self._sort_key):
            yield self.files[path]

    def _sort_key(self, path: FilePath) -> tuple[int, str]:
        normalized = normalize_path(path, base=self.base_path)
        return (0, normalized.as_posix())

    @staticmethod
    def get_source_lines(path: FilePath) -> list[str]:
        return read_file_lines(path)

    def display_path(self, path: FilePath) -> str:
        return normalize_path(path, base=self.base_path).as_posix()


@dataclass(slots=True)
class Report:
    """Container for the unified report surface."""

    meta: Mapping[str, Any]
    sections: Mapping[str, Any]
    attachments: Mapping[str, Any] = field(default_factory=dict)


def build_dataset(root: XmlElement, *, base_path: FilePath | None = None) -> CoverageDataset:
    """Build a :class:`CoverageDataset` from a single parsed coverage XML root."""
    dataset = CoverageDataset(base_path=base_path)
    dataset.add_root(root)
    return dataset


def build_lines(dataset: CoverageDataset, filters: PathFilter | None = None) -> list[UncoveredSection]:
    """Return uncovered line sections for *dataset* respecting *filters*."""
    uncovered: dict[FilePath, list[int]] = {}
    for file_cov in dataset.iter_files():
        if filters is not None and not filters.allow(file_cov.path):
            continue
        missing = file_cov.uncovered_lines()
        if not missing:
            continue
        uncovered[file_cov.path] = missing

    if not uncovered:
        return []

    sections: list[UncoveredSection] = []
    for path in sorted(uncovered, key=dataset.display_path):
        lines = uncovered[path]
        groups = group_consecutive_numbers(lines)
        source_lines = dataset.get_source_lines(path)
        if source_lines:
            groups = merge_blank_gap_groups(groups, source_lines)
        ranges: list[LineRange] = [(grp[0], grp[-1]) for grp in groups]
        sections.append(UncoveredSection(path, ranges))
    return sections


def build_branches(
    dataset: CoverageDataset,
    filters: PathFilter | None = None,
    mode: BranchMode | str = BranchMode.PARTIAL,
) -> list[BranchGap]:
    """Return branch gaps according to *mode* for the dataset."""
    if isinstance(mode, str):
        try:
            mode = BranchMode(mode)
        except ValueError as exc:
            choices = ", ".join(sorted(m.value for m in BranchMode))
            msg = f"mode must be one of [{choices}], got {mode!r}"
            raise ValueError(msg) from exc

    gaps: list[BranchGap] = []
    for file_cov in dataset.iter_files():
        if filters is not None and not filters.allow(file_cov.path):
            continue
        for gap in file_cov.branch_gaps(mode):
            if mode is not BranchMode.ALL and not gap.conditions:
                continue
            gaps.append(
                BranchGap(
                    file=gap.file,
                    line=gap.line,
                    conditions=list(gap.conditions),
                )
            )
    return gaps


def build_summary(
    dataset: CoverageDataset,
    sort: SummarySort | str = SummarySort.FILE,
) -> tuple[list[tuple], tuple[int, int, int, int]]:
    """Return summary rows and totals for *dataset*."""
    rows: list[tuple] = []
    stmt_totals = stmt_hits = br_totals = br_hits = 0

    for file_cov in dataset.iter_files():
        stmt_tot = len(file_cov.lines)
        stmt_hit = sum(1 for cov in file_cov.lines.values() if cov.hits > 0)
        br_tot = sum(cov.branches_total for cov in file_cov.lines.values())
        br_hit = sum(cov.branches_covered for cov in file_cov.lines.values())

        rows.append((
            dataset.display_path(file_cov.path),
            stmt_tot,
            stmt_hit,
            stmt_tot - stmt_hit,
            br_tot,
            br_hit,
            br_tot - br_hit,
        ))

        stmt_totals += stmt_tot
        stmt_hits += stmt_hit
        br_totals += br_tot
        br_hits += br_hit

    if isinstance(sort, str):
        try:
            sort = SummarySort(sort)
        except ValueError as exc:
            choices = ", ".join(sorted(item.value for item in SummarySort))
            msg = f"sort must be one of [{choices}], got {sort!r}"
            raise ValueError(msg) from exc

    key_funcs = {
        SummarySort.FILE: lambda row: (row[0],),
        SummarySort.STATEMENT_COVERAGE: lambda row: (
            -((100 * row[2] / row[1]) if row[1] else -1),
            row[0],
        ),
        SummarySort.BRANCH_COVERAGE: lambda row: (
            -((100 * row[5] / row[4]) if row[4] else -1),
            row[0],
        ),
        SummarySort.MISSES: lambda row: (-(row[3] + row[6]), row[0]),
    }

    rows.sort(key=key_funcs[sort])
    return rows, (stmt_totals, stmt_hits, br_totals, br_hits)


def build_diff(
    base_dataset: CoverageDataset,
    current_dataset: CoverageDataset,
) -> dict[str, list[UncoveredSection]]:
    """Return diff between two datasets as new/resolved sections."""

    def _line_map(dataset: CoverageDataset) -> dict[FilePath, set[int]]:
        mapping: dict[FilePath, set[int]] = {}
        for file_cov in dataset.iter_files():
            missing = file_cov.uncovered_lines()
            if missing:
                mapping[file_cov.path] = set(missing)
        return mapping

    base_lines = _line_map(base_dataset)
    cur_lines = _line_map(current_dataset)

    new_uncovered: dict[FilePath, list[int]] = {}
    resolved: dict[FilePath, list[int]] = {}

    for path, lines in cur_lines.items():
        prev = base_lines.get(path, set())
        added = sorted(lines - prev)
        if added:
            new_uncovered[path] = added

    for path, lines in base_lines.items():
        now = cur_lines.get(path, set())
        removed = sorted(lines - now)
        if removed:
            resolved[path] = removed

    return {
        "new": build_sections(new_uncovered),
        "resolved": build_sections(resolved),
    }


# Backwards compatibility: retain legacy diff helper for existing callers.
__all__ = [
    "CoverageDataset",
    "FileCoverage",
    "LineCoverage",
    "Report",
    "build_branches",
    "build_dataset",
    "build_diff",
    "build_lines",
    "build_summary",
]
