from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from showcov.core.model.types import FULL_COVERAGE

# -----------------------------------------------------------------------------
# Core surface model (what renderers + JSON output consume)
# -----------------------------------------------------------------------------

SectionName = Literal["lines", "branches", "summary"]


@dataclass(frozen=True, slots=True)
class EnvironmentMeta:
    """Execution environment metadata (schema: meta.environment)."""

    coverage_xml: str


@dataclass(frozen=True, slots=True)
class OptionsMeta:
    """Options used to build/enrich the report (schema: meta.options).

    Notes
    -----
    - `context_lines` is the *maximum symmetric* context span, matching the schema.
      If you keep asymmetric before/after internally, store those elsewhere.
    """

    context_lines: int = 0
    with_code: bool = False
    show_paths: bool = True
    show_line_numbers: bool = True
    aggregate_stats: bool = False
    file_stats: bool = False


@dataclass(frozen=True, slots=True)
class ReportMeta:
    """Top-level report meta (schema: meta)."""

    environment: EnvironmentMeta
    options: OptionsMeta


# -----------------------------------------------------------------------------
# Lines section
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceLine:
    """A single line of source text associated with an uncovered range."""

    code: str
    line: int | None = None
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class UncoveredRange:
    """Inclusive [start, end] uncovered span (1-indexed line numbers)."""

    start: int
    end: int
    source: tuple[SourceLine, ...] | None = None

    def __post_init__(self) -> None:
        """Validate that the range boundaries are sane."""
        if self.start < 1 or self.end < 1:
            msg = "UncoveredRange.start/end must be >= 1"
            raise ValueError(msg)
        if self.end < self.start:
            msg = "UncoveredRange.end must be >= start"
            raise ValueError(msg)

    @property
    def line_count(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True, slots=True)
class FileCounts:
    """Optional per-file counts for the lines section (schema: uncovered_file.counts)."""

    uncovered: int
    total: int

    def __post_init__(self) -> None:
        """Validate that counts are non-negative."""
        if self.uncovered < 0:
            msg = "FileCounts.uncovered must be >= 0"
            raise ValueError(msg)
        if self.total < 0:
            msg = "FileCounts.total must be >= 0"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class UncoveredFile:
    """Uncovered ranges for a file (schema: uncovered_file).

    Notes
    -----
    - `file` is optional in the schema; it can be omitted when paths are hidden.
      Use `None` to represent omission.
    """

    uncovered: tuple[UncoveredRange, ...]
    file: str | None = None
    counts: FileCounts | None = None


@dataclass(frozen=True, slots=True)
class LineSummary:
    """Optional aggregate lines summary (schema: lines.summary)."""

    uncovered: int

    def __post_init__(self) -> None:
        """Validate that the uncovered total is non-negative."""
        if self.uncovered < 0:
            msg = "LineSummary.uncovered must be >= 0"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class LinesSection:
    """Lines section (schema: sections.lines)."""

    files: tuple[UncoveredFile, ...]
    summary: LineSummary | None = None


# -----------------------------------------------------------------------------
# Branches section
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BranchCondition:
    number: int
    type: str | None
    coverage: int | None  # 0..100 or None when unknown

    def __post_init__(self) -> None:
        """Validate coverage percentages are within bounds."""
        if self.coverage is not None and not (0 <= self.coverage <= FULL_COVERAGE):
            msg = "BranchCondition.coverage must be in [0, 100] or None"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class BranchGap:
    """A line with uncovered/partial branch conditions (schema: branch_gap)."""

    line: int
    conditions: tuple[BranchCondition, ...]
    file: str | None = None

    def __post_init__(self) -> None:
        """Validate that the branch line number is positive."""
        if self.line < 1:
            msg = "BranchGap.line must be >= 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class BranchesSection:
    """Branches section (schema: sections.branches)."""

    gaps: tuple[BranchGap, ...]


# -----------------------------------------------------------------------------
# Summary section
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SummaryCounts:
    total: int
    covered: int
    missed: int

    def __post_init__(self) -> None:
        """Validate that counts are non-negative and consistent."""
        if self.total < 0 or self.covered < 0 or self.missed < 0:
            msg = "SummaryCounts fields must be >= 0"
            raise ValueError(msg)
        # Not strictly required, but keeps data sane.
        if self.covered + self.missed != self.total:
            msg = "SummaryCounts requires covered + missed == total"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SummaryRow:
    file: str
    statements: SummaryCounts
    branches: SummaryCounts
    # Derived / actionable fields
    statement_pct: float = 100.0
    branch_pct: float | None = None  # None when branches.total == 0
    uncovered_lines: int = 0
    uncovered_ranges: int = 0
    # Lightweight tags
    untested: bool = False  # statements.total > 0 and statements.covered == 0
    tiny: bool = False  # statements.total is very small (heuristic)


@dataclass(frozen=True, slots=True)
class SummaryTotals:
    statements: SummaryCounts
    branches: SummaryCounts


@dataclass(frozen=True, slots=True)
class SummarySection:
    files: tuple[SummaryRow, ...]
    totals: SummaryTotals
    # Extra summary metadata (presentation/trust)
    files_with_branches: int = 0
    total_files: int = 0


# -----------------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReportSections:
    """Typed container for the optional sections.

    Only include sections that were requested/built.
    """

    lines: LinesSection | None = None
    branches: BranchesSection | None = None
    summary: SummarySection | None = None

    def present(self) -> tuple[SectionName, ...]:
        out: list[SectionName] = []
        if self.lines is not None:
            out.append("lines")
        if self.branches is not None:
            out.append("branches")
        if self.summary is not None:
            out.append("summary")
        return tuple(out)


@dataclass(frozen=True, slots=True)
class Report:
    """Unified report surface consumed by renderers and JSON output."""

    meta: ReportMeta
    sections: ReportSections
