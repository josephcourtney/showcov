"""Shared type aliases and enumerations used across showcov."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TypeAlias

# ---------------------------------------------------------------------------
# Common type aliases
# ---------------------------------------------------------------------------

FilePath: TypeAlias = Path
"""Canonical file path object used throughout the code base."""

CoveragePercent: TypeAlias = int
"""Integer percentage value in the inclusive range ``0`` to ``100``."""

LineRange: TypeAlias = tuple[int, int]
"""Inclusive ``(start, end)`` pair representing uncovered lines."""


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


class Format(StrEnum):
    """Supported output formats."""

    HUMAN = "human"
    RG = "rg"
    JSON = "json"
    AUTO = "auto"


__all__ = [
    "BranchMode",
    "CoveragePercent",
    "FilePath",
    "Format",
    "LineRange",
    "SummarySort",
]
