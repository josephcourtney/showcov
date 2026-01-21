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
    STATEMENT_COVERAGE = "stmt_cov"
    BRANCH_COVERAGE = "br_cov"
    MISSES = "miss"


FULL_COVERAGE: int = 100


__all__ = [
    "FULL_COVERAGE",
    "BranchMode",
    "SummarySort",
]
