from __future__ import annotations

from typing import TypeAlias

from showcov.model.report import BranchCondition

Record: TypeAlias = tuple[
    str,  # file
    int,  # line
    int,  # hits
    tuple[int, int] | None,  # branch_counts
    tuple[int, ...],  # missing_branches
    tuple[BranchCondition, ...],  # conditions
]

__all__ = ["Record"]
