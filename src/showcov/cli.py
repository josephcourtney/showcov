"""Command line interface for ``showcov``."""

from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import sys
import xml.etree.ElementTree as ET  # noqa: S405
from html import escape
from io import StringIO
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import click
from defusedxml import ElementTree
from rich.console import Console
from rich.table import Table

from showcov import __version__, logger
from showcov.core import (
    LOG_FORMAT,
    CoverageXMLNotFoundError,
    PathFilter,
    UncoveredSection,
    build_sections,
    determine_xml_file,
    diff_uncovered_lines,
    gather_uncovered_lines_from_xml,
)
from showcov.core.coverage import (
    BranchCondition,
    BranchGap,
    compute_file_rows,
    gather_uncovered_branches_from_xml,
    read_coverage_xml_file,
)
from showcov.core.coverage import (
    aggregate as aggregate_coverage,
)
from showcov.core.coverage import (
    sort_rows as sort_coverage_rows,
)
from showcov.core.files import normalize_path, read_file_lines
from showcov.output import render_output
from showcov.output.base import Format, OutputMeta
from showcov.output.registry import resolve_formatter
from showcov.output.table import format_table

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_DATAERR = 65
EXIT_NOINPUT = 66
EXIT_CONFIG = 78


# ---------------------------------------------------------------------------
# Dataclass to hold options
# ---------------------------------------------------------------------------
@dataclasses.dataclass(slots=True)
class ShowcovOptions:
    debug: bool = False
    quiet: bool = False
    verbose: bool = False
    use_color: bool = True

    xml_file: Path | None = None
    include: list[str] = dataclasses.field(default_factory=list)
    exclude: list[str] = dataclasses.field(default_factory=list)

    output_format: str = "auto"
    output: Path | None = None

    show_paths: bool = True
    file_stats: bool = False
    aggregate_stats: bool = False
    show_code: bool = False
    show_line_numbers: bool = False
    context_before: int = 0
    context_after: int = 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _emit_manpage(prog: str, cmd: click.Command) -> str:
    """Return roff-formatted man page for *cmd*."""
    help_text = cmd.get_help(click.Context(cmd))
    today = datetime.datetime.now(datetime.UTC).date().strftime("%Y-%m-%d")
    return dedent(
        rf"""
        .TH {prog.upper()} 1 "{today}" "{prog} {__version__}" "User Commands"
        .SH NAME
        {prog} \- show uncovered lines from a coverage XML report
        .SH SYNOPSIS
        {prog} [OPTIONS] [PATHS]...
        .SH DESCRIPTION
        {help_text}
        """
    ).strip()


def _configure_runtime(*, quiet: bool, verbose: bool, debug: bool) -> None:
    """Configure logging based on *quiet*/*verbose*."""
    level = logging.ERROR if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT)

    if debug:
        logger.debug("debug mode active")


def _resolve_context_option(value: str | None) -> tuple[int, int]:
    """Translate ``--context`` value into before/after counts."""
    if not value:
        return 0, 0
    parts = [p.strip() for p in value.replace(",", " ").split()]
    try:
        if len(parts) == 1:
            n = int(parts[0])
            return n, n
        if len(parts) == 2:  # noqa: PLR2004
            return int(parts[0]), int(parts[1])
    except ValueError as err:
        msg = "context must be integers"
        raise click.BadParameter(msg) from err
    msg = "Expect 'N' or 'N,M' for --context"
    raise click.BadParameter(msg)


def _format_condition_display(cond: BranchCondition) -> str:
    """Return a human-readable label for a branch condition."""
    number = cond.number if cond.number >= 0 else None
    typ = (cond.type or "branch").lower()
    if typ == "line" and number is not None:
        label = str(number)
    elif typ == "line":
        label = "line"
    else:
        suffix = f"#{number}" if number is not None else ""
        label = f"{typ}{suffix}"
    if cond.coverage is None:
        return label
    return f"{label} ({cond.coverage}%)"


def _format_branch_code(
    file_path: Path,
    line: int,
    *,
    before: int,
    after: int,
    show_line_numbers: bool,
) -> str:
    """Return formatted source context for a branch line."""
    lines = read_file_lines(file_path)
    if not lines:
        return "<source unavailable>"
    start = max(1, line - before)
    end = min(len(lines), line + after)
    snippet: list[str] = []
    for idx in range(start, end + 1):
        marker = ">" if idx == line else " "
        prefix = f"{idx:>4}: " if show_line_numbers else ""
        text = lines[idx - 1].rstrip("\n")
        snippet.append(f"{marker} {prefix}{text}")
    return "\n".join(snippet)


def _emit_branch_json(
    gaps: Sequence[BranchGap],
    *,
    show_paths: bool,
    xml_path: Path,
) -> None:
    base = xml_path.parent

    def norm(p: Path) -> str:
        return normalize_path(p, base=base).as_posix()

    data = [
        {
            "file": norm(g.file) if show_paths else None,
            "line": g.line,
            "conditions": [
                {"number": c.number, "type": c.type, "coverage": c.coverage} for c in g.conditions
            ],
        }
        for g in gaps
    ]
    if not show_paths:
        for entry in data:
            entry.pop("file", None)
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def _emit_branch_table(
    gaps: Sequence[BranchGap],
    *,
    show_paths: bool,
    show_code: bool,
    line_numbers: bool,
    before: int,
    after: int,
    xml_path: Path,
    use_color: bool,
) -> None:
    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=use_color,
        width=sys.maxsize,
        color_system="standard" if use_color else None,
        no_color=not use_color,
    )
    table = Table(show_header=True, header_style="bold")
    if show_paths:
        table.add_column("File", style="yellow")
    table.add_column("Condition", justify="right", style="cyan")
    table.add_column("Branch Target(s)", style="magenta")
    if show_code:
        table.add_column("Code", style="green")

    base = xml_path.parent.resolve()
    for gap in gaps:
        file_col = normalize_path(gap.file, base=base).as_posix()
        cond_str = ", ".join(_format_condition_display(c) for c in gap.conditions)
        row = ([file_col] if show_paths else []) + [str(gap.line), cond_str]
        if show_code:
            code_block = _format_branch_code(
                gap.file,
                gap.line,
                before=before,
                after=after,
                show_line_numbers=line_numbers,
            )
            row.append(code_block)
        table.add_row(*row)

    console.print()
    console.print("Uncovered Branches")
    console.print(table)
    click.echo(buffer.getvalue())


def _build_summary_table_rows(
    rows: Sequence[tuple],
    *,
    base: Path,
    show_paths: bool,
) -> tuple[list[tuple[str, object, object, object, str, object, object, object, str]], dict[str, int]]:
    def pct(hit: int, total: int) -> str:
        return f"{(hit / total) * 100:.0f}%" if total else "n/a"

    table_rows: list[tuple[str, object, object, object, str, object, object, object, str]] = []
    totals = {"stmt_tot": 0, "stmt_hit": 0, "stmt_miss": 0, "br_tot": 0, "br_hit": 0, "br_miss": 0}
    for fpath, stmt_tot, stmt_hit, stmt_miss, br_tot, br_hit, br_miss in rows:
        label = normalize_path(Path(fpath), base=base).as_posix() if show_paths else Path(fpath).name
        table_rows.append((
            label,
            stmt_tot,
            stmt_hit,
            stmt_miss,
            pct(stmt_hit, stmt_tot),
            br_tot,
            br_hit,
            br_miss,
            pct(br_hit, br_tot),
        ))
        totals["stmt_tot"] += stmt_tot
        totals["stmt_hit"] += stmt_hit
        totals["stmt_miss"] += stmt_miss
        totals["br_tot"] += br_tot
        totals["br_hit"] += br_hit
        totals["br_miss"] += br_miss

    return table_rows, totals


def _format_summary_json(
    rows: Sequence[tuple],
    totals: dict[str, int],
    *,
    base: Path,
    show_paths: bool,
    coverage_xml: Path,
) -> str:
    def pct(hit: int, total: int) -> float | None:
        return round((hit / total) * 100, 2) if total else None

    def label_for(path_str: str) -> str:
        path = Path(path_str)
        if show_paths:
            return normalize_path(path, base=base).as_posix()
        return path.name

    files: list[dict[str, object]] = []
    for fpath, stmt_tot, stmt_hit, stmt_miss, br_tot, br_hit, br_miss in rows:
        files.append({
            "file": label_for(str(fpath)),
            "statements": {
                "total": stmt_tot,
                "hit": stmt_hit,
                "miss": stmt_miss,
                "coverage": pct(stmt_hit, stmt_tot),
            },
            "branches": {
                "total": br_tot,
                "hit": br_hit,
                "miss": br_miss,
                "coverage": pct(br_hit, br_tot),
            },
        })

    payload = {
        "metadata": {
            "coverage_xml": normalize_path(coverage_xml).as_posix(),
            "show_paths": show_paths,
        },
        "files": files,
        "totals": {
            "statements": {
                "total": totals["stmt_tot"],
                "hit": totals["stmt_hit"],
                "miss": totals["stmt_miss"],
                "coverage": pct(totals["stmt_hit"], totals["stmt_tot"]),
            },
            "branches": {
                "total": totals["br_tot"],
                "hit": totals["br_hit"],
                "miss": totals["br_miss"],
                "coverage": pct(totals["br_hit"], totals["br_tot"]),
            },
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_summary_html(
    headers: Sequence[Sequence[str]],
    rows: Sequence[Sequence[object]],
) -> str:
    def header_label(parts: Sequence[str]) -> str:
        label = " ".join(part for part in parts if part).strip()
        return label or "\u00a0"

    html_lines = ["<table>", "  <thead>", "    <tr>"]
    html_lines.extend(f"      <th>{escape(header_label(header))}</th>" for header in headers)
    html_lines.extend(("    </tr>", "  </thead>", "  <tbody>"))
    for row in rows:
        html_lines.append("    <tr>")
        for cell in row:
            value = "" if cell is None else str(cell)
            cell_text = escape(value) if value else "&nbsp;"
            html_lines.append(f"      <td>{cell_text}</td>")
        html_lines.append("    </tr>")
    html_lines.extend(("  </tbody>", "</table>"))
    return "\n".join(html_lines)


def resolve_sections(opts: ShowcovOptions) -> tuple[list[UncoveredSection], Path]:
    xml_path = determine_xml_file(str(opts.xml_file) if opts.xml_file else None)
    uncovered = gather_uncovered_lines_from_xml(xml_path)
    sections_all = build_sections(uncovered)
    logger.debug("coverage xml resolved to %s", xml_path)
    logger.debug("include patterns: %s", opts.include)
    logger.debug("exclude patterns: %s", opts.exclude)
    filtered = PathFilter(opts.include, opts.exclude, base=xml_path.parent).filter(sections_all)
    logger.debug("filtered %d of %d sections", len(filtered), len(sections_all))
    return filtered, xml_path


def write_output(output_text: str, opts: ShowcovOptions) -> None:
    if opts.output and opts.output != Path("-"):
        try:
            if not opts.output.parent.exists():
                raise click.FileError(str(opts.output), hint="directory does not exist")
            opts.output.write_text(output_text, encoding="utf-8")
        except OSError as err:
            raise click.FileError(str(opts.output), hint=str(err)) from err
        return

    click.echo(output_text)


# ---------------------------------------------------------------------------
# CLI group and commands
# ---------------------------------------------------------------------------


@click.group(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
    invoke_without_command=True,
)
@click.option("--version", is_flag=True, is_eager=True, help="Show the version and exit")
@click.option("--debug", is_flag=True, help="Show full tracebacks for errors")
@click.option("-q", "--quiet", is_flag=True, help="Suppress INFO logs, emit only errors")
@click.option("-v", "--verbose", is_flag=True, help="Emit diagnostic logging")
@click.pass_context
def cli(ctx: click.Context, *, version: bool, debug: bool, quiet: bool, verbose: bool) -> None:
    """Showcov - show uncovered lines from a coverage XML report."""
    ctx.obj = ShowcovOptions(debug=debug, quiet=quiet, verbose=verbose)

    if version and ctx.invoked_subcommand is None:
        click.echo(__version__)
        ctx.exit(EXIT_OK)

    if ctx.invoked_subcommand is None:
        show_ctx = show.make_context("show", ctx.args, parent=ctx)
        ctx.invoke(show, **show_ctx.params)


@cli.command()
def version() -> None:
    """Print the version and exit."""
    click.echo(__version__)


@cli.command()
@click.pass_context
def man(ctx: click.Context) -> None:
    """Print the man page and exit."""
    click.echo(_emit_manpage("showcov", cli))
    ctx.exit(EXIT_OK)


COMPLETION_TEMPLATES: Final[dict[str, str]] = {
    "bash": (
        '_grobl_completion() {{ eval "$(env {var}=bash_source {prog} "$@")"; }}\n'
        "complete -F _grobl_completion {prog}"
    ),
    "zsh": 'autoload -U compinit; compinit\neval "$(env {var}=zsh_source {prog})"',
    "fish": "eval (env {var}=fish_source {prog})",
}


def _load_branch_gaps(xml_file: Path | None, *, debug: bool) -> tuple[Path, list[BranchGap]]:
    """Read branch gaps from the given coverage XML, with CLI-style errors."""
    try:
        xml_path = determine_xml_file(str(xml_file) if xml_file else None)
        gaps: list[BranchGap] = gather_uncovered_branches_from_xml(xml_path)
    except (ElementTree.ParseError, ET.ParseError, ValueError):
        click.echo(f"ERROR: failed to read coverage XML (invalid format): {xml_file or '<auto>'}", err=True)
        if debug:
            raise
        sys.exit(EXIT_DATAERR)
    except CoverageXMLNotFoundError as e:
        click.echo(f"ERROR: {e}", err=True)
        if debug:
            raise
        sys.exit(EXIT_NOINPUT)
    else:
        return xml_path, gaps


def _load_summary_rows(
    xml_file: Path | None,
    *,
    include: Sequence[str | Path],
    exclude: Sequence[str | Path],
    sort_key: str,
    debug: bool,
) -> tuple[Path, list[tuple]]:
    try:
        xml_path = determine_xml_file(str(xml_file) if xml_file else None)
    except CoverageXMLNotFoundError as e:
        click.echo(f"ERROR: {e}", err=True)
        if debug:
            raise
        sys.exit(EXIT_NOINPUT)

    root = read_coverage_xml_file(xml_path)
    if root is None:
        click.echo(
            f"ERROR: failed to read coverage XML (invalid format): {xml_file or '<auto>'}",
            err=True,
        )
        if debug:
            msg = "failed to parse coverage XML"
            raise ValueError(msg)
        sys.exit(EXIT_DATAERR)
    else:
        acc = aggregate_coverage([root], include=None, exclude=None)
        rows_raw, _ = compute_file_rows(acc)
        sort_coverage_rows(rows_raw, key=sort_key)
        pf = PathFilter(include, exclude, base=xml_path.parent)
        filtered = [row for row in rows_raw if pf.allow(Path(row[0]))]
        return xml_path, filtered


@cli.command()
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    required=True,
    help="Target shell to generate completion script for",
)
def completions(shell: str) -> None:
    """Print shell completion script for the given shell."""
    prog = "showcov"
    var = "_SHOWCOV_COMPLETE"
    try:
        template = COMPLETION_TEMPLATES[shell]
    except KeyError as err:  # pragma: no cover - defensive
        print(f"Unsupported shell: {shell}", file=sys.stderr)
        raise SystemExit(1) from err
    click.echo(template.format(var=var, prog=prog))


@cli.command(name="show")
@click.argument("paths", nargs=-1, type=click.Path())
@click.option(
    "--cov", "xml_file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file"
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude (can be repeated)")
@click.option("--include", "include_", multiple=True, help="Glob pattern to include (can be repeated)")
@click.option(
    "--format",
    "format_",
    default="auto",
    show_default=True,
    type=click.Choice([fmt.value for fmt in Format], case_sensitive=False),
    help="Output format",
)
@click.option("--color", "force_color", is_flag=True, help="Force ANSI color codes in output")
@click.option("--no-color", is_flag=True, help="Disable ANSI color codes in output")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to FILE instead of stdout")
@click.option("--paths/--no-paths", "show_paths", default=True, help="Include file paths in output")
@click.option("--file-stats/--no-file-stats", default=False, help="Include per-file statistics")
@click.option("--stats/--no-stats", "aggregate_stats", default=False, help="Include aggregate statistics")
@click.option("--code/--no-code", "show_code", default=False, help="Include the uncovered source code lines")
@click.option("--line-numbers", is_flag=True, help="Show line numbers alongside code")
@click.option(
    "--context",
    "context_",
    type=str,
    metavar="N[,M]",
    help="Lines of context to include: N for both sides or N,M for before/after",
)
@click.pass_obj
def show(
    opts: ShowcovOptions,
    *,
    paths: Sequence[str],
    xml_file: Path | None,
    include_: Sequence[str],
    exclude: Sequence[str],
    format_: str,
    force_color: bool,
    no_color: bool,
    output: Path | None,
    show_paths: bool,
    file_stats: bool,
    aggregate_stats: bool,
    show_code: bool,
    line_numbers: bool,
    context_: str | None,
) -> None:
    """Show uncovered lines (default command)."""
    if force_color and no_color:
        msg = "--color/--no-color"
        raise click.BadOptionUsage(msg, "Cannot combine --color and --no-color")

    before, after = _resolve_context_option(context_)
    is_tty = sys.stdout.isatty()

    opts.include.extend(paths)
    opts.include.extend(include_)
    opts.exclude.extend(exclude)
    opts.output_format = format_
    opts.use_color = force_color or (is_tty and not no_color)
    opts.show_line_numbers = line_numbers
    opts.context_before = before
    opts.context_after = after
    opts.xml_file = xml_file
    opts.output = output
    opts.show_code = show_code
    opts.file_stats = file_stats
    opts.aggregate_stats = aggregate_stats
    opts.show_paths = show_paths

    if opts.output_format == "auto" and opts.output and opts.output != Path("-"):
        raise click.BadOptionUsage("--format", "Cannot use --format=auto with --output")  # noqa: EM101

    _configure_runtime(quiet=opts.quiet, verbose=opts.verbose, debug=opts.debug)

    try:
        sections, resolved_xml = resolve_sections(opts)
    except (  # handle both stdlib and defusedxml parse errors + bad root
        ElementTree.ParseError,
        ET.ParseError,
        ValueError,
    ):
        click.echo(f"ERROR: failed to read coverage XML (invalid format): {xml_file or '<auto>'}", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_DATAERR)
    except CoverageXMLNotFoundError as e:
        # No coverage XML specified or found in configuration (or path not found):
        # align with CLI contract/tests to exit with EX_NOINPUT (66).
        click.echo(f"ERROR: {e}", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_NOINPUT)

    fmt, formatter = resolve_formatter(opts.output_format, is_tty=is_tty)
    meta = OutputMeta(
        context_lines=max(opts.context_before, opts.context_after),
        with_code=opts.show_code,
        coverage_xml=resolved_xml,
        color=opts.use_color,
        show_paths=opts.show_paths,
        show_line_numbers=opts.show_line_numbers,
    )
    output_text = render_output(
        sections,
        fmt,
        formatter,
        meta,
        aggregate_stats=opts.aggregate_stats,
        file_stats=opts.file_stats,
    )

    write_output(output_text, opts)


@cli.command(name="branches")
@click.argument("paths", nargs=-1, type=click.Path())
@click.option(
    "--cov", "xml_file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file"
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude (can be repeated)")
@click.option("--include", "include_", multiple=True, help="Glob pattern to include (can be repeated)")
@click.option(
    "--format",
    "format_",
    default="human",
    show_default=True,
    type=click.Choice([fmt.value for fmt in Format if fmt is not Format.AUTO], case_sensitive=False),
    help="Output format (human or json)",
)
@click.option("--paths/--no-paths", "show_paths", default=True, help="Include file paths in output")
@click.option("--code/--no-code", "show_code", default=False, help="Include source context")
@click.option("--line-numbers", is_flag=True, help="Show line numbers with --code output")
@click.option(
    "--context",
    "context_",
    type=str,
    metavar="N[,M]",
    help="Lines of context to include around each branch when using --code",
)
@click.pass_obj
def branches(
    opts: ShowcovOptions,
    *,
    paths: Sequence[str],
    xml_file: Path | None,
    include_: Sequence[str],
    exclude: Sequence[str],
    format_: str,
    show_paths: bool,
    show_code: bool,
    line_numbers: bool,
    context_: str | None,
) -> None:
    """Show lines and specific branch conditions that are uncovered (0%)."""
    _configure_runtime(quiet=opts.quiet, verbose=opts.verbose, debug=opts.debug)

    xml_path, gaps = _load_branch_gaps(xml_file, debug=opts.debug)

    if (context_ or line_numbers) and not show_code:
        msg = "--context/--line-numbers"
        raise click.BadOptionUsage(msg, "--code must be enabled to show context")

    before, after = _resolve_context_option(context_) if show_code else (0, 0)

    # Filter by include/exclude, consistent with `show`
    pf = PathFilter([*paths, *include_], list(exclude), base=xml_path.parent)
    gaps = [g for g in gaps if pf.allow(g.file)]

    if not gaps:
        click.echo("No uncovered branch conditions found")
        return

    if format_ == Format.JSON.value:
        _emit_branch_json(gaps, show_paths=show_paths, xml_path=xml_path)
        return

    _emit_branch_table(
        gaps,
        show_paths=show_paths,
        show_code=show_code,
        line_numbers=line_numbers,
        before=before,
        after=after,
        xml_path=xml_path,
        use_color=opts.use_color,
    )


@cli.command(name="diff")
@click.argument("baseline", type=click.Path(path_type=Path, exists=True))
@click.argument("current", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--format",
    "format_",
    default="auto",
    show_default=True,
    type=click.Choice([fmt.value for fmt in Format], case_sensitive=False),
    help="Output format",
)
@click.option("--output", type=click.Path(path_type=Path), help="Write output to FILE instead of stdout")
@click.pass_obj
def diff(
    opts: ShowcovOptions,
    *,
    baseline: Path,
    current: Path,
    format_: str,
    output: Path | None,
) -> None:
    """Compare two coverage reports."""
    if format_ == "auto" and output and output != Path("-"):
        raise click.BadOptionUsage("--format", "Cannot use --format=auto with --output")  # noqa: EM101

    _configure_runtime(quiet=opts.quiet, verbose=opts.verbose, debug=opts.debug)

    try:
        new_sections, resolved_sections = diff_uncovered_lines(baseline, current)
    except (  # handle both stdlib and defusedxml parse errors + bad root
        ElementTree.ParseError,
        ET.ParseError,
        ValueError,
    ):
        click.echo("ERROR: failed to read coverage XML", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_DATAERR)
    except OSError as e:
        click.echo(f"ERROR: failed to read coverage XML: {e}", err=True)
        if opts.debug:
            raise
        sys.exit(EXIT_GENERIC)

    opts.output_format = format_
    opts.output = output

    fmt, formatter = resolve_formatter(format_, is_tty=sys.stdout.isatty())
    meta = OutputMeta(
        context_lines=0,
        with_code=False,
        coverage_xml=current,
        color=opts.use_color,
        show_paths=True,
        show_line_numbers=False,
    )
    if fmt is Format.JSON:
        base = current.parent
        data = {
            "new": [sec.to_dict(base=base) for sec in new_sections],
            "resolved": [sec.to_dict(base=base) for sec in resolved_sections],
        }
        output_text = json.dumps(data, indent=2, sort_keys=True)
    else:
        parts: list[str] = []
        if new_sections:
            parts.append("New uncovered lines:\n" + render_output(new_sections, fmt, formatter, meta))
        if resolved_sections:
            parts.append(
                "Resolved uncovered lines:\n" + render_output(resolved_sections, fmt, formatter, meta)
            )
        output_text = "No changes in coverage" if not parts else "\n\n".join(parts)

    tmp = dataclasses.replace(opts, output_format=fmt.value)
    write_output(output_text, tmp)


@cli.command(name="summary")
@click.argument("paths", nargs=-1, type=click.Path())
@click.option(
    "--cov", "xml_file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file"
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude (can be repeated)")
@click.option("--include", "include_", multiple=True, help="Glob pattern to include (can be repeated)")
@click.option(
    "--sort",
    "sort_key",
    default="file",
    show_default=True,
    type=click.Choice(["file", "stmt_cov", "br_cov", "miss"], case_sensitive=False),
    help="Column used to sort the table",
)
@click.option("--paths/--no-paths", "show_paths", default=True, help="Show file paths in the output")
@click.option(
    "--format",
    "format_",
    default=Format.HUMAN.value,
    show_default=True,
    type=click.Choice([fmt.value for fmt in Format], case_sensitive=False),
    help="Output format",
)
@click.pass_obj
def summary(
    opts: ShowcovOptions,
    *,
    paths: Sequence[str],
    xml_file: Path | None,
    include_: Sequence[str],
    exclude: Sequence[str],
    sort_key: str,
    show_paths: bool,
    format_: str,
) -> None:
    """Print a statements/branches coverage summary."""
    _configure_runtime(quiet=opts.quiet, verbose=opts.verbose, debug=opts.debug)

    include_patterns: list[str | Path] = []
    include_patterns.extend(paths)
    include_patterns.extend(include_)
    xml_path, rows = _load_summary_rows(
        xml_file,
        include=include_patterns,
        exclude=list(exclude),
        sort_key=sort_key,
        debug=opts.debug,
    )

    if not rows:
        click.echo("No files matched the provided filters")
        return

    base = xml_path.parent.resolve()
    table_rows, totals = _build_summary_table_rows(rows, base=base, show_paths=show_paths)

    spacer = ("", "", "", "", "", "", "", "", "")
    stmt_cov = f"{(totals['stmt_hit'] / totals['stmt_tot']) * 100:.0f}%" if totals["stmt_tot"] else "n/a"
    br_cov = f"{(totals['br_hit'] / totals['br_tot']) * 100:.0f}%" if totals["br_tot"] else "n/a"
    totals_row = (
        "Overall",
        totals["stmt_tot"],
        totals["stmt_hit"],
        totals["stmt_miss"],
        stmt_cov,
        totals["br_tot"],
        totals["br_hit"],
        totals["br_miss"],
        br_cov,
    )

    headers = (
        ("Coverage Report", "", "File"),
        ("Coverage Report", "Statements", "Tot."),
        ("Coverage Report", "Statements", "Hit"),
        ("Coverage Report", "Statements", "Miss"),
        ("Coverage Report", "Statements", "Cov."),
        ("Coverage Report", "Branches", "Tot."),
        ("Coverage Report", "Branches", "Hit"),
        ("Coverage Report", "Branches", "Miss"),
        ("Coverage Report", "Branches", "Cov."),
    )

    fmt, _ = resolve_formatter(format_, is_tty=sys.stdout.isatty())
    if fmt is Format.JSON:
        output_text = _format_summary_json(
            rows,
            totals,
            base=base,
            show_paths=show_paths,
            coverage_xml=xml_path,
        )
        click.echo(output_text)
        return

    display_rows = [*table_rows, spacer, totals_row]
    if fmt is Format.HTML:
        click.echo(_format_summary_html(headers, [*table_rows, totals_row]))
        return

    # Both HUMAN and MARKDOWN formats use the grouped Markdown table layout.
    click.echo(format_table(headers, display_rows))
