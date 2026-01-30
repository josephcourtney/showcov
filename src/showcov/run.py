from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from showcov.model.path_filter import PathFilter
from showcov.model.thresholds import Threshold
from showcov.model.thresholds import evaluate as evaluate_thresholds

if TYPE_CHECKING:
    from showcov.model.report import Report

from dataclasses import replace
from typing import TYPE_CHECKING

from defusedxml import ElementTree

from showcov import logger
from showcov.engine.build import BuildOptions, build_report
from showcov.engine.enrich import enrich_report
from showcov.errors import CoverageXMLNotFoundError, InvalidCoverageXMLError
from showcov.render.render import RenderOptions, render

if TYPE_CHECKING:
    from pathlib import Path

    from showcov.model.path_filter import PathFilter
    from showcov.model.report import Report
    from showcov.model.types import BranchMode, SummarySort

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DATAERR = 65
EXIT_NOINPUT = 66
EXIT_THRESHOLD = 2


def build_and_render(
    *,
    coverage_paths: tuple[Path, ...],
    base_path: Path,
    filters: PathFilter | None,
    sections: set[str],
    diff_base: Path | None,
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
    show_covered: bool = False,
    summary_group: bool = True,
    summary_group_depth: int = 2,
    summary_top: bool = True,
    summary_top_n: int = 10,
    drop_empty_branches: bool,
) -> tuple[Report, str]:
    opts = BuildOptions(
        coverage_paths=coverage_paths,
        base_path=base_path,
        filters=filters,
        sections=sections,
        diff_base=diff_base,
        branches_mode=branches_mode,
        summary_sort=summary_sort,
        want_aggregate_stats=want_stats,
        want_file_stats=want_file_stats,
        want_snippets=want_snippets,
        context_before=context_before,
        context_after=context_after,
        meta_show_paths=show_paths,
        meta_show_line_numbers=show_line_numbers,
    )

    try:
        report: Report = build_report(opts)
        if want_snippets or want_file_stats:
            report = enrich_report(report, opts)
    except CoverageXMLNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except (ElementTree.ParseError, InvalidCoverageXMLError) as exc:
        typer.echo(f"ERROR: failed to parse coverage XML: {exc}", err=True)
        raise typer.Exit(code=EXIT_DATAERR) from exc
    except OSError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except Exception as exc:
        logger.exception("unexpected failure")
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_GENERIC) from exc

    if drop_empty_branches and report.sections.branches is not None and not report.sections.branches.gaps:
        report = replace(report, sections=replace(report.sections, branches=None))

    text = render(
        report,
        fmt=render_fmt,
        options=RenderOptions(
            color=bool(color),
            show_paths=bool(show_paths),
            show_line_numbers=bool(show_line_numbers),
            is_tty=bool(is_tty_like),
            show_covered=bool(show_covered),
            summary_group=bool(summary_group),
            summary_group_depth=int(summary_group_depth),
            summary_top=bool(summary_top),
            summary_top_n=int(summary_top_n),
        ),
    )
    return report, text


def apply_thresholds_or_exit(
    report: Report,
    *,
    fail_under_stmt: float | None,
    fail_under_branches: float | None,
    max_misses: int | None,
) -> None:
    thresholds: list[Threshold] = []
    if fail_under_stmt is not None:
        thresholds.append(Threshold(statement=float(fail_under_stmt)))
    if fail_under_branches is not None:
        thresholds.append(Threshold(branch=float(fail_under_branches)))
    if max_misses is not None:
        thresholds.append(Threshold(misses=int(max_misses)))

    if not thresholds:
        return

    result = evaluate_thresholds(report, thresholds)
    if result.passed:
        return

    for f in result.failures:
        typer.echo(
            f"Threshold failed: {f.metric} {f.comparison} {f.required} (actual {f.actual})",
            err=True,
        )
    raise typer.Exit(code=EXIT_THRESHOLD)
