from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.adapters.render.render import RenderOptions, render
from showcov.usecases.pipeline import build_report_from_coverage

if TYPE_CHECKING:
    from pathlib import Path

    from showcov.model.path_filter import PathFilter
    from showcov.model.report import Report
    from showcov.model.types import BranchMode, SummarySort


def build_and_render_text(
    *,
    coverage_paths: tuple[Path, ...],
    base_path: Path,
    filters: PathFilter | None,
    sections: set[str],
    branches_mode: BranchMode,
    summary_sort: SummarySort,
    want_stats: bool,
    want_file_stats: bool,
    want_snippets: bool,
    context_before: int,
    context_after: int,
    show_paths: bool,
    show_line_numbers: bool,
    render_fmt: str,
    is_tty_like: bool,
    color: bool,
    show_covered: bool,
    summary_group: bool,
    summary_max_depth: int | None,
    drop_empty_branches: bool,
) -> tuple[Report, str]:
    report = build_report_from_coverage(
        coverage_paths=coverage_paths,
        base_path=base_path,
        filters=filters,
        sections=sections,
        branches_mode=branches_mode,
        summary_sort=summary_sort,
        want_stats=want_stats,
        want_file_stats=want_file_stats,
        want_snippets=want_snippets,
        context_before=context_before,
        context_after=context_after,
        show_paths=show_paths,
        show_line_numbers=show_line_numbers,
        drop_empty_branches=drop_empty_branches,
    )

    render_opts = RenderOptions(
        color=color,
        show_paths=show_paths,
        show_line_numbers=show_line_numbers,
        is_tty=is_tty_like,
        show_covered=show_covered,
        summary_group=summary_group,
        summary_max_depth=summary_max_depth,
    )
    return report, render(report, fmt=render_fmt, options=render_opts)


__all__ = ["build_and_render_text"]
