from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from showcov.coverage.discover import resolve_coverage_paths
from showcov.engine.build import BuildOptions, build_report
from showcov.engine.enrich import enrich_report
from showcov.errors import CoverageXMLNotFoundError
from showcov.model.thresholds import Threshold
from showcov.model.thresholds import evaluate as evaluate_thresholds
from showcov.model.types import BranchMode, SummarySort
from showcov.render.render import RenderOptions, render

from ._shared import EXIT_DATAERR, EXIT_NOINPUT, EXIT_OK, EXIT_THRESHOLD, write_output

if TYPE_CHECKING:
    from pathlib import Path

FormatName = Literal["auto", "human", "grep"]
BranchesModeName = Literal["off", "missing", "partial", "all"]


def _resolve_format(fmt: FormatName) -> str:
    f = (fmt or "auto").strip().lower()
    if f == "human":
        return "human"
    if f == "grep":
        return "rg"
    # auto
    return "human" if sys.stdout.isatty() else "rg"


def _resolve_branches_mode(mode: BranchesModeName) -> BranchMode | None:
    m = (mode or "partial").strip().lower()
    if m == "off":
        return None
    if m == "missing":
        return BranchMode.MISSING_ONLY
    if m == "all":
        return BranchMode.ALL
    return BranchMode.PARTIAL


def register(app: typer.Typer) -> None:
    @app.command("report")
    def report_cmd(
        coverage_xml: Annotated[
            list[Path],
            typer.Argument(..., help="One or more Cobertura-style coverage XML files."),
        ],
        report_format: Annotated[
            FormatName,
            typer.Option("--format", help="Output format: auto, human, grep."),
        ] = "auto",
        branches: Annotated[
            BranchesModeName,
            typer.Option(
                "--branches",
                help="Branch reporting: off, missing, partial, all.",
            ),
        ] = "partial",
        fail_under_stmt: Annotated[
            float | None,
            typer.Option("--fail-under-stmt", min=0.0, max=100.0, help="Minimum statement coverage percent."),
        ] = None,
        fail_under_branch: Annotated[
            float | None,
            typer.Option("--fail-under-branch", min=0.0, max=100.0, help="Minimum branch coverage percent."),
        ] = None,
        max_misses: Annotated[
            int | None,
            typer.Option("--max-misses", min=0, help="Maximum allowed uncovered statement lines."),
        ] = None,
        output: Annotated[
            Path | None,
            typer.Option("--output", help="Write output to PATH (use '-' for stdout)."),
        ] = None,
        color: Annotated[
            bool,
            typer.Option("--color", help="Force ANSI color output."),
        ] = False,
        no_color: Annotated[
            bool,
            typer.Option("--no-color", help="Disable ANSI color output."),
        ] = False,
        code: Annotated[
            bool,
            typer.Option(
                "--code/--no-code",
                "--snippets/--no-snippets",
                help="Include source snippets around uncovered ranges.",
            ),
        ] = False,
        context: Annotated[
            int,
            typer.Option(
                "--context", min=0, help="Context lines before/after uncovered ranges (implies --code)."
            ),
        ] = 0,
        line_numbers: Annotated[
            bool,
            typer.Option("--line-numbers", help="Show line numbers in source snippets."),
        ] = False,
        show_paths: Annotated[
            bool,
            typer.Option("--paths/--no-paths", help="Show file paths in output."),
        ] = True,
    ) -> None:
        try:
            cov_paths = resolve_coverage_paths(coverage_xml)
        except CoverageXMLNotFoundError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=EXIT_NOINPUT) from exc

        fmt = _resolve_format(report_format)
        branches_mode = _resolve_branches_mode(branches)

        want_snippets = bool(code or context > 0)
        opts = BuildOptions(
            coverage_paths=tuple(cov_paths),
            base_path=cov_paths[0].parent,
            filters=None,
            sections={"lines", "summary"} | ({"branches"} if branches_mode is not None else set()),
            diff_base=None,
            branches_mode=branches_mode or BranchMode.PARTIAL,
            summary_sort=SummarySort.FILE,
            want_aggregate_stats=True,
            want_file_stats=False,
            want_snippets=want_snippets,
            context_before=int(context),
            context_after=int(context),
            meta_show_paths=bool(show_paths),
            meta_show_line_numbers=bool(line_numbers),
        )

        try:
            report = build_report(opts)
            if opts.want_snippets:
                report = enrich_report(report, opts)
        except OSError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=EXIT_NOINPUT) from exc
        except Exception as exc:  # XML parse errors etc.
            typer.echo(f"ERROR: failed to build report: {exc}", err=True)
            raise typer.Exit(code=EXIT_DATAERR) from exc

        # color policy: only meaningful for human output and when stdout is a tty-like target
        allow_color = (fmt == "human") and (sys.stdout.isatty() and not no_color)
        use_color = bool(color or allow_color) and not no_color

        text = render(
            report,
            fmt=fmt,
            options=RenderOptions(
                color=use_color,
                show_paths=bool(show_paths),
                show_line_numbers=bool(line_numbers),
                is_tty=bool(sys.stdout.isatty()),
            ),
        )
        write_output(text, output)

        thresholds: list[Threshold] = []
        if fail_under_stmt is not None:
            thresholds.append(Threshold(statement=float(fail_under_stmt)))
        if fail_under_branch is not None:
            thresholds.append(Threshold(branch=float(fail_under_branch)))
        if max_misses is not None:
            thresholds.append(Threshold(misses=int(max_misses)))

        if thresholds:
            result = evaluate_thresholds(report, thresholds)
            if not result.passed:
                for f in result.failures:
                    typer.echo(
                        f"Threshold failed: {f.metric} {f.comparison} {f.required} (actual {f.actual})",
                        err=True,
                    )
                raise typer.Exit(code=EXIT_THRESHOLD)

        raise typer.Exit(code=EXIT_OK)


__all__ = ["register"]
