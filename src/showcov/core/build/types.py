from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from showcov.core.model.path_filter import PathFilter
from showcov.core.model.types import (
    BranchMode,
    SummarySort,
)
from .records import Record

@dataclass(frozen=True, slots=True)
class BuildOptions:
    coverage_paths: tuple[Path, ...]
    base_path: Path
    filters: PathFilter | None
    sections: set[str]
    branches_mode: BranchMode
    summary_sort: SummarySort
    want_aggregate_stats: bool
    want_file_stats: bool
    want_snippets: bool
    context_before: int
    context_after: int
    records: list[Record]
    # These are presentation flags, but they are required by schema meta.options.
    meta_show_paths: bool = True
    meta_show_line_numbers: bool = True
