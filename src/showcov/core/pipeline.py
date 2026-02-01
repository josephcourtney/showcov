from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from defusedxml import ElementTree

from showcov._meta import logger
from showcov.core.build import BuildOptions, build_report
from showcov.core.enrich import enrich_report
from showcov.core.model.thresholds import Threshold, ThresholdsResult
from showcov.core.model.thresholds import evaluate as evaluate_thresholds
from showcov.errors import CoverageXMLNotFoundError, InvalidCoverageXMLError
from showcov.inputs.records import collect_cobertura_records
from showcov.render.render import RenderOptions, render

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from showcov.core.build.records import Record
    from showcov.core.model.path_filter import PathFilter
    from showcov.core.model.report import Report
    from showcov.core.model.types import BranchMode, SummarySort


class PipelineError(Exception):
    """Base class for errors emitted by the pipeline."""


class NoInputError(PipelineError):
    """Coverage XML input was missing or could not be discovered."""


class DataError(PipelineError):
    """Coverage XML data is malformed or could not be parsed."""


class SystemIOError(PipelineError):
    """Filesystem IO error while building the report."""


class ThresholdError(PipelineError):
    """Threshold evaluation failed."""

    def __init__(self, result: ThresholdsResult) -> None:
        super().__init__("threshold failed")
        self.result = result


class UnexpectedError(PipelineError):
    """Unexpected failure while building or rendering."""


def _make_build_options(
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
    records: list[Record],
    show_paths: bool,
    show_line_numbers: bool,
) -> BuildOptions:
    return BuildOptions(
        coverage_paths=coverage_paths,
        base_path=base_path,
        filters=filters,
        sections=sections,
        branches_mode=branches_mode,
        summary_sort=summary_sort,
        want_aggregate_stats=want_stats,
        want_file_stats=want_file_stats,
        want_snippets=want_snippets,
        context_before=context_before,
        context_after=context_after,
        records=records,
        meta_show_paths=show_paths,
        meta_show_line_numbers=show_line_numbers,
    )


def _render_options(
    *,
    color: bool,
    show_paths: bool,
    show_line_numbers: bool,
    is_tty_like: bool,
    show_covered: bool,
    summary_group: bool,
    summary_group_depth: int,
) -> RenderOptions:
    return RenderOptions(
        color=color,
        show_paths=show_paths,
        show_line_numbers=show_line_numbers,
        is_tty=is_tty_like,
        show_covered=show_covered,
        summary_group=summary_group,
        summary_group_depth=summary_group_depth,
    )


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
    summary_group_depth: int,
    drop_empty_branches: bool,
) -> tuple[Report, str]:
    try:
        records = collect_cobertura_records(coverage_paths)
        opts = _make_build_options(
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
            records=records,
            show_paths=show_paths,
            show_line_numbers=show_line_numbers,
        )

        report = build_report(opts)
        if want_snippets or want_file_stats:
            report = enrich_report(report, opts)
    except CoverageXMLNotFoundError as exc:
        raise NoInputError(str(exc)) from exc
    except (ElementTree.ParseError, InvalidCoverageXMLError) as exc:
        msg = f"failed to parse coverage XML: {exc}"
        raise DataError(msg) from exc
    except OSError as exc:
        raise SystemIOError(str(exc)) from exc
    except Exception as exc:
        logger.exception("unexpected failure")
        raise UnexpectedError(str(exc)) from exc

    if drop_empty_branches and report.sections.branches is not None and not report.sections.branches.gaps:
        report = replace(report, sections=replace(report.sections, branches=None))

    render_opts = _render_options(
        color=color,
        show_paths=show_paths,
        show_line_numbers=show_line_numbers,
        is_tty_like=is_tty_like,
        show_covered=show_covered,
        summary_group=summary_group,
        summary_group_depth=summary_group_depth,
    )
    rendered = render(report, fmt=render_fmt, options=render_opts)
    return report, rendered


def evaluate_thresholds_or_raise(
    report: Report,
    *,
    thresholds: Sequence[Threshold],
) -> None:
    """Raise ThresholdError if any configured thresholds fail."""
    if not thresholds:
        return
    result = evaluate_thresholds(report, thresholds)
    if result.passed:
        return
    raise ThresholdError(result)


__all__ = [
    "DataError",
    "NoInputError",
    "PipelineError",
    "SystemIOError",
    "ThresholdError",
    "UnexpectedError",
    "build_and_render_text",
    "evaluate_thresholds_or_raise",
]
