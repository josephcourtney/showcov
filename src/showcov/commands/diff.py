from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from showcov.engine.build import BuildOptions, build_report
from showcov.engine.enrich import enrich_report
from showcov.model.types import BranchMode, SummarySort
from showcov.render.render import RenderOptions, render

from ._shared import EXIT_DATAERR, EXIT_NOINPUT, EXIT_OK, write_output

if TYPE_CHECKING:
    from pathlib import Path

FormatName = Literal["auto", "human", "grep"]


def _resolve_format(fmt: FormatName) -> str:
    f = (fmt or "auto").strip().lower()
    if f == "human":
        return "human"
    if f == "grep":
        return "rg"
    return "human" if sys.stdout.isatty() else "rg"


def register(app: typer.Typer) -> None:
    @app.command("diff")
    def diff_cmd(
        baseline: Annotated[Path, typer.Argument(..., help="Baseline coverage XML.")],
        current: Annotated[Path, typer.Argument(..., help="Current coverage XML.")],
        output_format: Annotated[
            FormatName, typer.Option("--format", help="Output format: auto, human, grep.")
        ] = "auto",
        output: Annotated[
            Path | None,
            typer.Option("--output", help="Write output to PATH (use '-' for stdout)."),
        ] = None,
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

        fmt = _resolve_format(output_format)
        want_snippets = bool(code or context > 0)

        opts = BuildOptions(
            coverage_paths=(current.resolve(),),
            base_path=current.resolve().parent,
            filters=None,
            sections={"diff"},
            diff_base=baseline.resolve(),
            branches_mode=BranchMode.PARTIAL,
            summary_sort=SummarySort.FILE,
            want_aggregate_stats=False,
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
        except Exception as exc:
            typer.echo(f"ERROR: failed to build diff: {exc}", err=True)
            raise typer.Exit(code=EXIT_DATAERR) from exc

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
        raise typer.Exit(code=EXIT_OK)


__all__ = ["register"]
