"""Shared type aliases and enumerations used across showcov."""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class BranchMode(StrEnum):
    """Available strategies when reporting uncovered branch conditions."""

    MISSING_ONLY = "missing-only"
    PARTIAL = "partial"
    ALL = "all"


class SummarySort(StrEnum):
    """Ordering options for coverage summary tables."""

    FILE = "file"
    # Percentages
    STATEMENT_COVERAGE = "stmt_cov"  # ascending (worst first)
    BRANCH_COVERAGE = "br_cov"  # ascending (worst first)
    # Misses / hotness
    MISSED_STATEMENTS = "miss_stmt"  # descending (worst first)
    MISSED_BRANCHES = "miss_br"  # descending (worst first)
    UNCOVERED_LINES = "uncovered_lines"  # descending (worst first)


FULL_COVERAGE: int = 100


__all__ = [
    "FULL_COVERAGE",
    "BranchMode",
    "SummarySort",
]
