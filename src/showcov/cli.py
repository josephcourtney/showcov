"""Command line interface for ``showcov``."""

from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import sys
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import click
from defusedxml import ElementTree

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
from showcov.output import render_output
from showcov.output.base import Format, OutputMeta
from showcov.output.registry import resolve_formatter

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


@click.command()
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    required=True,
    help="Target shell to generate completion script for",
)
def completions(shell: str) -> None:
    """Print shell completion script for the given shell."""
    prog = "grobl"
    var = "_GROBL_COMPLETE"
    try:
        template = COMPLETION_TEMPLATES[shell]
    except KeyError as err:  # pragma: no cover - defensive
        print(f"Unsupported shell: {shell}", file=sys.stderr)
        raise SystemExit(1) from err
    print(template.format(var=var, prog=prog))


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
