from __future__ import annotations

from typing import TYPE_CHECKING

from showcov.adapters.render.render import RenderOptions
from showcov.usecases.reporting import build_and_render_text

if TYPE_CHECKING:
    from pathlib import Path

    from showcov.model.path_filter import PathFilter
    from showcov.model.report import Report
    from showcov.model.types import BranchMode, SummarySort


def generate_report_and_text(
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
    render_fmt: str = "human",
    render_options: RenderOptions | None = None,
    drop_empty_branches: bool = True,
) -> tuple[Report, str]:
    """Build and render a report with the given pipeline settings."""
    render_opts = render_options or RenderOptions()
    return build_and_render_text(
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
        show_paths=render_opts.show_paths,
        show_line_numbers=render_opts.show_line_numbers,
        render_fmt=render_fmt,
        is_tty_like=render_opts.is_tty,
        color=render_opts.color,
        show_covered=render_opts.show_covered,
        summary_group=render_opts.summary_group,
        summary_max_depth=render_opts.summary_max_depth,
        drop_empty_branches=drop_empty_branches,
    )


def generate_text_report(
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
    render_fmt: str = "human",
    render_options: RenderOptions | None = None,
    drop_empty_branches: bool = True,
) -> str:
    """Return just the rendered report text."""
    _, text = generate_report_and_text(
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
        render_fmt=render_fmt,
        render_options=render_options,
        drop_empty_branches=drop_empty_branches,
    )
    return text


__all__ = [
    "generate_report_and_text",
    "generate_text_report",
]
