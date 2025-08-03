from __future__ import annotations

import datetime
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import click
import click_completion
import click_completion.core
from colorama import init as colorama_init
from defusedxml import ElementTree

from showcov import __version__, logger
from showcov.config import LOG_FORMAT
from showcov.core import (
    CoverageXMLNotFoundError,
    build_sections,
    determine_xml_file,
    gather_uncovered_lines_from_xml,
)
from showcov.output import Format, OutputMeta, get_formatter
from showcov.path_filter import PathFilter

if TYPE_CHECKING:
    from collections.abc import Sequence

# --------------------------------------------------------------------------- #
# Early-exit helpers                                                          #
# --------------------------------------------------------------------------- #


# The `value` argument must stay positional for Click's callback signature.
# Suppress Ruff FBT001 (“Boolean-typed positional argument”) for this case.
def _emit_manpage(ctx: click.Context, _param: click.Option, value: bool) -> None:  # noqa: FBT001
    """Print the manpage and exit (eager option)."""
    if not value or ctx.resilient_parsing:
        return

    help_text = ctx.command.get_help(ctx)
    today = datetime.datetime.now(datetime.UTC).date().strftime("%Y-%m-%d")
    prog = ctx.command.name or "showcov"

    man_text = dedent(
        rf"""
        .TH {prog.upper()} 1 "{today}" "{prog} {__version__}" "User Commands"
        .SH NAME
        {prog} \- show uncovered lines from a coverage XML report
        .SH SYNOPSIS
        {prog} [OPTIONS] [PATHS]...
        .SH DESCRIPTION
        {help_text}
        """
    )
    click.echo(man_text.strip())
    ctx.exit(0)


def _emit_completion(ctx: click.Context, _param: click.Option, shell: str | None) -> None:
    """Print shell-completion script and exit (eager option)."""
    if not shell or ctx.resilient_parsing:
        return

    script = click_completion.core.get_code(shell=shell, prog_name="showcov")
    click.echo(script)
    ctx.exit(0)


# --------------------------------------------------------------------------- #
# Runtime configuration                                                       #
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Runtime:
    """Values that the command's helpers need."""

    is_tty: bool
    use_color: bool
    debug: bool


def _configure_runtime(*, quiet: bool, verbose: bool, no_color: bool) -> Runtime:
    """Set up logging + colorama and return a runtime descriptor."""
    level = logging.ERROR if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT)

    colorama_init(autoreset=True)
    click_completion.init()

    is_tty = sys.stdout.isatty()
    return Runtime(is_tty=is_tty, use_color=is_tty and not no_color, debug=verbose)


# --------------------------------------------------------------------------- #
# Command                                                                     #
# --------------------------------------------------------------------------- #


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(package_name="showcov", prog_name="showcov")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--xml-file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file")
@click.option("--no-color", is_flag=True, help="Disable ANSI color codes in output")
@click.option("--with-code", is_flag=True, help="Embed raw source lines for uncovered ranges in JSON output")
@click.option(
    "--context-lines",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Number of context lines to include",
)
@click.option("--summary-only", is_flag=True, help="Emit only file paths containing uncovered lines")
@click.option("--stats", is_flag=True, help="Show coverage summary statistics")
@click.option("--pager", is_flag=True, help="Force paging even if stdout is redirected")
@click.option("--no-pager", is_flag=True, help="Disable paging of output")
@click.option("--list-files", is_flag=True, help="List files with uncovered code")
@click.option("--debug", is_flag=True, help="Show full tracebacks for errors")
@click.option("-q", "--quiet", is_flag=True, help="Suppress INFO logs, emit only errors")
@click.option("-v", "--verbose", is_flag=True, help="Emit diagnostic logging")
@click.option(
    "--format",
    "format_",
    default="auto",
    show_default=True,
    help="Output format",
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude from output")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to FILE instead of stdout")
# eager early-exit options
@click.option(
    "--man",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_emit_manpage,
    help="Print the manpage and exit",
)
@click.option(
    "--completion",
    type=click.Choice(["zsh", "bash", "fish"], case_sensitive=False),
    is_eager=True,
    expose_value=False,
    callback=_emit_completion,
    help="Print shell-completion script for SHELL and exit",
)
@click.pass_context
def main(
    ctx: click.Context,
    paths: Sequence[Path],
    xml_file: Path | None,
    *,
    no_color: bool,
    with_code: bool,
    context_lines: int,
    summary_only: bool,
    stats: bool,
    pager: bool,
    no_pager: bool,
    list_files: bool,
    debug: bool,
    quiet: bool,
    verbose: bool,
    format_: str,
    exclude: Sequence[str],
    output: Path | None,
) -> None:
    """Show uncovered lines from a coverage XML report."""
    rt = _configure_runtime(quiet=quiet, verbose=verbose, no_color=no_color)

    # ------------------------------------------------------------------ #
    # Resolve coverage XML                                               #
    # ------------------------------------------------------------------ #
    try:
        resolved_xml = determine_xml_file(str(xml_file) if xml_file else None)
    except CoverageXMLNotFoundError as e:
        click.echo(f"ERROR: {e}", err=True)
        if debug:
            raise
        ctx.exit(66)

    # ------------------------------------------------------------------ #
    # Parse XML                                                          #
    # ------------------------------------------------------------------ #
    try:
        uncovered = gather_uncovered_lines_from_xml(resolved_xml)
    except ElementTree.ParseError:
        click.echo(f"ERROR: failed to read coverage XML (invalid format): {xml_file or '<auto>'}", err=True)
        if debug:
            raise
        ctx.exit(65)
    except OSError as e:
        click.echo(f"ERROR: failed to read coverage XML: {e}", err=True)
        if debug:
            raise
        ctx.exit(1)

    # ------------------------------------------------------------------ #
    # Build + filter sections                                            #
    # ------------------------------------------------------------------ #
    sections_all = build_sections(uncovered)
    path_filter = PathFilter(paths, exclude)
    sections = path_filter.filter(sections_all)

    # ------------------------------------------------------------------ #
    # Select format                                                      #
    # ------------------------------------------------------------------ #
    try:
        actual_format = Format.from_str(format_)
    except ValueError as err:
        raise click.BadParameter(str(err), param_hint="--format") from err

    if actual_format is Format.AUTO:
        actual_format = Format.HUMAN if rt.is_tty else Format.JSON

    if verbose:
        logger.info("input paths: %d", len(list(paths)))
        logger.info("uncovered files: %d", len(sections))
        logger.info("uncovered regions: %d", sum(len(sec.ranges) for sec in sections))
        logger.info("output format: %s", actual_format.value)
        logger.info("destination: %s", output or "stdout")

    # ------------------------------------------------------------------ #
    # Render                                                             #
    # ------------------------------------------------------------------ #
    if list_files:
        files = sorted({sec.file.as_posix() for sec in sections})
        output_text: str = "\n".join(files)
    elif summary_only:
        files = sorted({sec.file.as_posix() for sec in sections})
        output_text = json.dumps(files, indent=2) if actual_format is Format.JSON else "\n".join(files)
    else:
        formatter = get_formatter(actual_format)
        meta = OutputMeta(
            context_lines=context_lines,
            with_code=with_code,
            coverage_xml=resolved_xml,
            color=rt.use_color,
        )
        output_text = formatter(sections, meta)

    # No uncovered lines?
    if not sections and not list_files:
        msg = "No uncovered lines found (0 files matched input paths)"
        if output and output != Path("-"):
            output.write_text(msg, encoding="utf-8")
        else:
            click.echo(msg)
        return

    # Append stats footer if requested
    if stats or (actual_format is Format.HUMAN and rt.is_tty and not list_files):
        totals = (
            len(sections),
            sum(len(sec.ranges) for sec in sections),
            sum(end - start + 1 for sec in sections for start, end in sec.ranges),
        )
        footer = (
            f"{totals[0]} files with uncovered lines, {totals[1]} uncovered regions, {totals[2]} total lines"
        )
        output_text = f"{output_text}\n{footer}" if output_text else footer

    # ------------------------------------------------------------------ #
    # Write                                                              #
    # ------------------------------------------------------------------ #
    if output and output != Path("-"):
        output.write_text(output_text, encoding="utf-8")
        return

    if pager and no_pager:
        msg = "Cannot use --pager and --no-pager together"
        raise click.UsageError(msg)
    use_pager = pager if pager or no_pager else False

    click.echo_via_pager(output_text) if use_pager else click.echo(output_text)
