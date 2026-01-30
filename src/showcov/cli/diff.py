from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from showcov.io import (
    OutputFormat,
    compute_io_policy,
    write_output,
)
from showcov.model.types import BranchMode, SummarySort
from showcov.run import (
    EXIT_NOINPUT,
    EXIT_OK,
    build_and_render,
)


def register(app: typer.Typer) -> None:
    @app.command("diff")
    def diff_cmd(
        baseline: Annotated[Path, typer.Argument(..., help="Baseline coverage XML.")],
        current: Annotated[Path, typer.Argument(..., help="Current coverage XML.")],
        output_format: Annotated[
            OutputFormat,
            typer.Option("--format", help="Output format: auto, human, rg, json."),
        ] = OutputFormat.AUTO,
        output: Annotated[
            Path | None,
            typer.Option("--output", help="Write output to PATH (use '-' for stdout)."),
        ] = None,
        *,
        color: Annotated[bool, typer.Option("--color", help="Force ANSI color output.")] = False,
        no_color: Annotated[bool, typer.Option("--no-color", help="Disable ANSI color output.")] = False,
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
        if not baseline.exists():
            typer.echo(f"ERROR: coverage XML not found: {baseline}", err=True)
            raise typer.Exit(code=EXIT_NOINPUT)
        if not current.exists():
            typer.echo(f"ERROR: coverage XML not found: {current}", err=True)
            raise typer.Exit(code=EXIT_NOINPUT)

        want_snippets = bool(code or context > 0)
        render_fmt, is_tty_like, color_allowed = compute_io_policy(fmt=output_format, output=output)
        use_color = bool(color or color_allowed) and not no_color

        _report, text = build_and_render(
            coverage_paths=(current.resolve(),),
            base_path=current.resolve().parent,
            filters=None,
            sections={"diff"},
            diff_base=baseline.resolve(),
            branches_mode=BranchMode.PARTIAL,
            summary_sort=SummarySort.FILE,
            want_stats=False,
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
        raise typer.Exit(code=EXIT_OK)


__all__ = ["register"]
