from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from showcov.coverage.discover import resolve_coverage_paths
from showcov.errors import CoverageXMLNotFoundError
from showcov.io import (
    OutputFormat,
    compute_io_policy,
    write_output,
)
from showcov.model.types import BranchMode, SummarySort
from showcov.run import (
    EXIT_NOINPUT,
    EXIT_OK,
    apply_thresholds_or_exit,
    build_and_render,
)

BranchesModeName = Literal["off", "missing", "partial", "all"]

_ALLOWED_SECTIONS: set[str] = {"lines", "branches", "summary"}


def _parse_sections(raw: list[str], *, default: set[str]) -> set[str]:
    """Parse --sections tokens (repeatable and/or comma-separated) into a set."""
    if not raw:
        return set(default)

    out: set[str] = set()
    for token in raw:
        for part in (token or "").replace(",", " ").split():
            name = part.strip().lower()
            if not name:
                continue
            if name not in _ALLOWED_SECTIONS:
                allowed = ", ".join(sorted(_ALLOWED_SECTIONS))
                msg = f"unknown section {name!r}. Expected one of: {allowed}"
                raise typer.BadParameter(msg)
            out.add(name)

    return out or set(default)


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
        *,
        coverage_xml: Annotated[
            list[Path] | None,
            typer.Argument(
                help=(
                    "Zero or more Cobertura-style coverage XML files. "
                    "If omitted, try to discover from pyproject.toml and common filenames."
                ),
            ),
        ] = None,
        report_format: Annotated[
            OutputFormat,
            typer.Option("--format", help="Output format: auto, human, rg, json."),
        ] = OutputFormat.AUTO,
        sections: Annotated[
            list[str] | None,
            typer.Option(
                "--section",
                "--sections",
                help="Sections to include (repeatable or comma-separated): lines, branches, summary.",
            ),
        ] = None,
        lines: Annotated[
            bool,
            typer.Option(
                "--lines",
                help="Enable line reporting.",
            ),
        ] = False,
        branches: Annotated[
            BranchesModeName,
            typer.Option(
                "--branches",
                help="Branch reporting: off, missing, partial, all.",
            ),
        ] = "off",
        sort: Annotated[
            SummarySort,
            typer.Option(
                "--sort",
                help="Summary sort: file, stmt_cov, br_cov, miss_stmt, miss_br, uncovered_lines.",
            ),
        ] = SummarySort.MISSED_STATEMENTS,
        baseline: Annotated[
            Path | None,
            typer.Option(
                "--baseline",
                help=("Baseline coverage XML to compute summary deltas (current - baseline)."),
            ),
        ] = None,
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
        ] = False,
        show_covered: Annotated[
            bool,
            typer.Option(
                "--show-covered/--no-show-covered",
                help="Include fully covered files in the summary table.",
            ),
        ] = False,
        summary_group: Annotated[
            bool,
            typer.Option(
                "--summary-group/--no-summary-group",
                help="Show directory rollups above the file summary table.",
            ),
        ] = True,
        summary_group_depth: Annotated[
            int,
            typer.Option(
                "--summary-group-depth", min=1, help="Directory depth for rollups (e.g., 2 => src/pkg)."
            ),
        ] = 2,
        summary_top: Annotated[
            bool,
            typer.Option(
                "--summary-top/--no-summary-top",
                help="Show 'Top offenders' blocks above the summary table.",
            ),
        ] = True,
        summary_top_n: Annotated[
            int,
            typer.Option("--summary-top-n", min=1, help="Number of rows in each 'Top offenders' block."),
        ] = 10,
    ) -> None:
        if sections is None:
            sections = []
        try:
            cov_paths = resolve_coverage_paths(coverage_xml, cwd=Path.cwd())
        except CoverageXMLNotFoundError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=EXIT_NOINPUT) from exc

        branches_mode = _resolve_branches_mode(branches)

        render_fmt, is_tty_like, color_allowed = compute_io_policy(fmt=report_format, output=output)
        use_color = bool(color or color_allowed) and not no_color

        # In non-TTY auto mode, output resolves to rg/rg style; default should include line data.
        default_lines = bool(lines or render_fmt == "rg")

        want_snippets = bool(code or context > 0)
        default_sections = (
            {"summary"}
            | ({"lines"} if default_lines else set())
            | ({"branches"} if branches_mode is not None else set())
        )
        sections_set = _parse_sections(sections, default=default_sections)

        # If baseline is provided, it is used for summary deltas; diff section still requires "diff" in sections.
        if baseline is not None and not baseline.exists():
            msg = f"--baseline coverage XML not found: {baseline}"
            raise typer.BadParameter(msg)

        # Validate section/mode consistency.
        if "branches" in sections_set and branches_mode is None:
            msg = "sections include 'branches' but --branches=off disables branch reporting"
            raise typer.BadParameter(msg)

        # Thresholds require specific sections to exist in the built report.
        if (fail_under_stmt is not None or fail_under_branch is not None) and "summary" not in sections_set:
            msg = "threshold evaluation for --fail-under-* requires 'summary' in --sections"
            raise typer.BadParameter(msg)
        if max_misses is not None and "lines" not in sections_set:
            msg = "threshold evaluation for --max-misses requires 'lines' in --sections"
            raise typer.BadParameter(msg)

        report, text = build_and_render(
            coverage_paths=tuple(cov_paths),
            base_path=cov_paths[0].parent,
            filters=None,
            sections=sections_set,
            diff_base=(baseline.resolve() if baseline is not None else None),
            branches_mode=branches_mode or BranchMode.PARTIAL,
            summary_sort=sort,
            want_stats=bool("lines" in sections_set),
            want_file_stats=False,
            want_snippets=want_snippets,
            context_before=int(context),
            context_after=int(context),
            show_paths=bool(show_paths),
            show_line_numbers=bool(line_numbers),
            render_fmt=render_fmt,
            is_tty_like=is_tty_like,
            color=use_color,
            show_covered=bool(show_covered),
            summary_group=bool(summary_group),
            summary_group_depth=int(summary_group_depth),
            summary_top=bool(summary_top),
            summary_top_n=int(summary_top_n),
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
