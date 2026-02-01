from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import click.utils as click_utils
import typer

from showcov.cli._shared import resolve_use_color
from showcov.cli.exit_codes import (
    EXIT_DATAERR,
    EXIT_GENERIC,
    EXIT_NOINPUT,
    EXIT_OK,
    EXIT_THRESHOLD,
)
from showcov.core.model.path_filter import PathFilter
from showcov.core.model.thresholds import Threshold
from showcov.core.model.types import BranchMode, SummarySort
from showcov.core.pipeline import (
    DataError,
    NoInputError,
    SystemIOError,
    ThresholdError,
    UnexpectedError,
    build_and_render_text,
    evaluate_thresholds_or_raise,
)
from showcov.inputs.discover import resolve_coverage_paths
from showcov.io import write_output

if TYPE_CHECKING:
    from showcov.core.model.report import Report

_BOOL_TRUE = True
_BOOL_FALSE = False


def _is_tty_stdout() -> bool:
    try:
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except OSError:
        return False


def _build_report_and_text(
    *,
    coverage_paths: tuple[Path, ...],
    filters: PathFilter | None,
    sections: set[str],
    want_snippets: bool,
    context: int,
    sort: SummarySort,
    group_depth: int,
    is_tty_like: bool,
    use_color: bool,
) -> tuple[Report, str]:
    base_path = Path.cwd()
    try:
        return build_and_render_text(
            coverage_paths=tuple(coverage_paths),
            base_path=base_path,
            filters=filters,
            sections=sections,
            branches_mode=BranchMode.PARTIAL,
            summary_sort=sort,
            want_stats=("lines" in sections),
            want_file_stats=False,
            want_snippets=want_snippets,
            context_before=context,
            context_after=context,
            show_paths=True,
            show_line_numbers=True,
            render_fmt="human",
            is_tty_like=is_tty_like,
            color=use_color,
            show_covered=False,
            summary_group=True,
            summary_group_depth=group_depth,
            drop_empty_branches=True,
        )
    except NoInputError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except SystemIOError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_NOINPUT) from exc
    except DataError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_DATAERR) from exc
    except UnexpectedError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=EXIT_GENERIC) from exc


def report_cmd(
    include: Annotated[
        list[str] | None,
        typer.Option(
            "-i",
            "--include",
            help="Include glob patterns (repeatable).",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "-x",
            "--exclude",
            help="Exclude glob patterns (repeatable).",
        ),
    ] = None,
    coverage: Annotated[
        list[Path] | None,
        typer.Argument(help="Coverage XML file(s). If omitted, discovery is used."),
    ] = None,
    # Section toggles (simpler than --sections)
    lines: Annotated[
        bool,
        typer.Option("--lines/--no-lines", help="Show uncovered statement lines."),
    ] = _BOOL_TRUE,
    branches: Annotated[
        bool,
        typer.Option("--branches/--no-branches", help="Show partially covered branch lines."),
    ] = _BOOL_TRUE,
    summary: Annotated[
        bool,
        typer.Option("--summary/--no-summary", help="Show summary and directory rollups."),
    ] = _BOOL_TRUE,
    # Code/snippets (replaces --snippets)
    code: Annotated[
        bool,
        typer.Option("--code/--no-code", help="Include source snippets for uncovered lines."),
    ] = _BOOL_FALSE,
    context: Annotated[
        int,
        typer.Option(
            "-C",
            "--context",
            help="Context lines around uncovered lines (implies --code when > 0).",
            min=0,
        ),
    ] = 0,
    # Summary knobs
    sort: Annotated[
        SummarySort,
        typer.Option(
            "--sort",
            help="Sort order for summary.",
            case_sensitive=False,
        ),
    ] = SummarySort.MISSED_STATEMENTS,
    group_depth: Annotated[
        int,
        typer.Option(
            "--group-depth",
            help="Directory rollup depth for summary (e.g., 2 groups by top two path parts).",
            min=1,
        ),
    ] = 2,
    # Thresholds (keep the same semantics)
    fail_under_stmt: Annotated[
        float | None,
        typer.Option("--fail-under-stmt", help="Fail if statement coverage % is below this value"),
    ] = None,
    fail_under_branches: Annotated[
        float | None,
        typer.Option("--fail-under-branches", help="Fail if branch coverage % is below this value"),
    ] = None,
    max_misses: Annotated[
        int | None,
        typer.Option("--max-misses", help="Fail if total uncovered statement lines exceeds this value"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write output to PATH (use '-' for stdout)."),
    ] = None,
    color: Annotated[
        bool,
        typer.Option("--color", help="Force color output"),
    ] = _BOOL_FALSE,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable color output"),
    ] = _BOOL_FALSE,
) -> None:
    include = include or []
    exclude = exclude or []

    coverage_paths = resolve_coverage_paths(coverage, cwd=Path.cwd())

    sections: set[str] = set()
    if lines:
        sections.add("lines")
    if branches:
        sections.add("branches")
    if summary:
        sections.add("summary")

    # If user disables everything, default to summary (least surprising).
    if not sections:
        sections = {"summary"}

    filters = (
        PathFilter(include=tuple(include), exclude=tuple(exclude), base=Path.cwd())
        if (include or exclude)
        else None
    )

    want_snippets = bool(code or context > 0)

    is_tty_like = _is_tty_stdout() and (output is None or output == Path("-"))
    ansi_allowed = not click_utils.should_strip_ansi(sys.stdout)
    color_allowed = bool(is_tty_like and ansi_allowed)
    use_color = resolve_use_color(color=color, no_color=no_color, color_allowed=color_allowed)

    # We intentionally simplify: single console text output, no JSON, no rg/human split, no color flags.
    # For now we still render through the existing renderer (human), but we don't expose its complexity.

    report, text = _build_report_and_text(
        coverage_paths=tuple(coverage_paths),
        filters=filters,
        sections=sections,
        want_snippets=want_snippets,
        context=int(context),
        sort=sort,
        group_depth=int(group_depth),
        is_tty_like=is_tty_like,
        use_color=use_color,
    )

    _enforce_thresholds(
        report,
        fail_under_stmt=fail_under_stmt,
        fail_under_branches=fail_under_branches,
        max_misses=max_misses,
    )
    write_output(text, output)
    raise typer.Exit(code=EXIT_OK)


def _enforce_thresholds(
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

    try:
        evaluate_thresholds_or_raise(report, thresholds=thresholds)
    except ThresholdError as exc:
        for failure in exc.result.failures:
            typer.echo(
                (
                    "Threshold failed: "
                    f"{failure.metric} {failure.comparison} {failure.required}"
                    f" (actual {failure.actual})"
                ),
                err=True,
            )
        raise typer.Exit(code=EXIT_THRESHOLD) from exc


def register(app: typer.Typer) -> None:
    app.command("report")(report_cmd)


__all__ = ["register"]
