"""Utilities and helper functions for implementing CLI-specific functionality."""

from __future__ import annotations

import dataclasses
import datetime
import logging
import sys
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import click
import click_completion
import click_completion.core

from showcov import __version__, logger
from showcov.core import (
    LOG_FORMAT,
    PathFilter,
    UncoveredSection,
    build_sections,
    determine_xml_file,
    gather_uncovered_lines_from_xml,
)
from showcov.output.base import (
    Format,
)

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence


@dataclasses.dataclass(slots=True)
class ShowcovOptions:
    """Collected CLI options after parsing."""

    # --- global flags --------------------------------------------------- #
    debug: bool = False
    quiet: bool = False
    verbose: bool = False
    # colour handling is resolved after runtime detection
    use_color: bool = True

    # --- input ---------------------------------------------------------- #
    xml_file: Path | None = None
    include: list[str] = dataclasses.field(default_factory=list)
    exclude: list[str] = dataclasses.field(default_factory=list)

    # --- output selection / routing ------------------------------------ #
    output_format: str = "auto"
    pager: bool | None = None  # True = force pager, False = force no-pager, None = auto
    output: Path | None = None  # stdout if None

    # --- output styling / content -------------------------------------- #
    show_paths: bool = True
    file_stats: bool = False
    aggregate_stats: bool = False
    show_code: bool = False
    show_line_numbers: bool = False
    context_before: int = 0
    context_after: int = 0


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


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

    click_completion.init()

    if debug:
        logger.debug("debug mode active")


def _resolve_context_option(value: str | None) -> tuple[int, int]:
    """Translate ``--context`` value (``N`` or ``N,M``) into *(before, after)*."""
    if not value:
        return 0, 0
    parts = [p.strip() for p in value.replace(",", " ").split()]
    if len(parts) == 1:
        n = int(parts[0])
        return n, n
    if len(parts) == 2:  # noqa: PLR2004
        return int(parts[0]), int(parts[1])
    msg = "Expect 'N' or 'N,M' for --context"
    raise click.BadParameter(msg)


def parse_flags_to_opts(
    opts: ShowcovOptions,
    *,
    paths: Sequence[str],
    include_: Sequence[str],
    exclude: Sequence[str],
    format_: str,
    pager: bool,
    no_pager: bool,
    force_color: bool,
    no_color: bool,
    line_numbers: bool,
    context_: str | None,
    **kwargs: object,
) -> ShowcovOptions:
    if force_color and no_color:
        msg = "--color/--no-color"
        raise click.BadOptionUsage(msg, "Cannot combine --color and --no-color")
    before, after = _resolve_context_option(context_)
    is_tty = sys.stdout.isatty()

    return dataclasses.replace(
        opts,
        include=[*opts.include, *include_, *paths],
        exclude=[*opts.exclude, *exclude],
        output_format=format_,
        pager=True if pager else False if no_pager else None,
        use_color=force_color or (is_tty and not no_color),
        show_line_numbers=line_numbers,
        context_before=before,
        context_after=after,
        **kwargs,
    )


def resolve_sections(opts: ShowcovOptions) -> tuple[list[UncoveredSection], Path]:
    xml_path = determine_xml_file(str(opts.xml_file) if opts.xml_file else None)
    uncovered = gather_uncovered_lines_from_xml(xml_path)
    sections_all = build_sections(uncovered)
    filtered = PathFilter(opts.include, opts.exclude).filter(sections_all)
    return filtered, xml_path


def determine_format(opts: ShowcovOptions, output: Path | None, *, is_tty: bool) -> Format:
    try:
        fmt = Format.from_str(opts.output_format)
    except ValueError as err:
        raise click.BadParameter(str(err), param_hint="--format") from err

    if fmt is Format.AUTO:
        fmt = Format.HUMAN if is_tty else Format.JSON

    if opts.verbose:
        logger.info("input patterns: %d", len(opts.include))
        logger.info("output format: %s", fmt.value)
        logger.info("destination: %s", output or "stdout")

    return fmt


def write_output(output_text: str, opts: ShowcovOptions) -> None:
    if opts.output and opts.output != Path("-"):
        opts.output.write_text(output_text, encoding="utf-8")
        return

    use_pager = opts.pager if opts.pager is not None else (sys.stdout.isatty() and not opts.quiet)
    if use_pager:
        click.echo_via_pager(output_text)
    else:
        click.echo(output_text)
