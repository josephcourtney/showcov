from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from showcov.errors import CoverageXMLNotFoundError
from showcov.model.types import BranchMode, SummarySort

from ._shared import (
    EXIT_NOINPUT,
    EXIT_OK,
    OutputFormat,
    apply_thresholds_or_exit,
    build_and_render,
    compute_io_policy,
    resolve_coverage_paths,
    write_output,
)

BranchesModeName = Literal["off", "missing", "partial", "all"]


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
            OutputFormat,
            typer.Option("--format", help="Output format: auto, human, grep."),
        ] = OutputFormat.AUTO,
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
        *,
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
            cov_paths = resolve_coverage_paths(coverage_xml, cwd=Path.cwd())
        except CoverageXMLNotFoundError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=EXIT_NOINPUT) from exc

        branches_mode = _resolve_branches_mode(branches)

        render_fmt, is_tty_like, color_allowed = compute_io_policy(fmt=report_format, output=output)
        use_color = bool(color or color_allowed) and not no_color

        want_snippets = bool(code or context > 0)
        sections = {"lines", "summary"} | ({"branches"} if branches_mode is not None else set())
        report, text = build_and_render(
            coverage_paths=tuple(cov_paths),
            base_path=cov_paths[0].parent,
            filters=None,
            sections=sections,
            diff_base=None,
            branches_mode=branches_mode or BranchMode.PARTIAL,
            summary_sort=SummarySort.FILE,
            want_stats=True,
            want_file_stats=False,
            want_snippets=want_snippets,
            context_before=int(context),
            context_after=int(context),
            show_paths=bool(show_paths),
            show_line_numbers=bool(line_numbers),
            render_fmt=render_fmt,
            is_tty_like=is_tty_like,
            color=use_color,
            drop_empty_branches=False,
        )
        write_output(text, output)

        apply_thresholds_or_exit(
            report,
            fail_under_stmt=fail_under_stmt,
            fail_under_branches=fail_under_branch,
            max_misses=max_misses,
        )

        raise typer.Exit(code=EXIT_OK)


__all__ = ["register"]
