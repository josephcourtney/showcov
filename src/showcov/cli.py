from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from colorama import init as colorama_init
from defusedxml import ElementTree

from showcov import logger
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


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.version_option(package_name="showcov", prog_name="showcov")
@click.option("--xml-file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file")
@click.option("--no-color", is_flag=True, help="Disable ANSI color codes in output")
@click.option("--with-code", is_flag=True, help="Embed raw source lines for uncovered ranges in JSON output")
@click.option(
    "--context-lines",
    type=click.IntRange(min=0),
    default=0,
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
@click.option("--format", "format_", default=Format.AUTO.value, help="Output format")
@click.option("--exclude", multiple=True, help="Glob pattern to exclude from output")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to FILE instead of stdout")
def main(  # noqa: C901, PLR0912, PLR0915, PLR0914
    paths: Sequence[Path],
    xml_file: Path | None,
    *,
    no_color: bool = False,
    with_code: bool = False,
    context_lines: int = 0,
    summary_only: bool = False,
    stats: bool = False,
    pager: bool = False,
    no_pager: bool = False,
    list_files: bool = False,
    debug: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    format_: str = Format.AUTO.value,
    exclude: Sequence[str] = (),
    output: Path | None = None,
) -> None:
    """Show uncovered lines from a coverage XML report."""
    level = logging.ERROR if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT)
    colorama_init(autoreset=True)

    is_tty = sys.stdout.isatty()
    use_color = is_tty and not no_color

    try:
        resolved_xml = determine_xml_file(str(xml_file) if xml_file else None)
        uncovered = gather_uncovered_lines_from_xml(resolved_xml)
    except CoverageXMLNotFoundError as e:
        logger.error("failed to read coverage XML (missing XML file): %s", e)
        if debug:
            raise
        sys.exit(66)
    except ElementTree.ParseError:
        logger.error("failed to read coverage XML (invalid format): %s", xml_file or "<auto>")
        if debug:
            raise
        sys.exit(65)
    except OSError as e:
        logger.error("failed to read coverage XML: %s", e)
        if debug:
            raise
        sys.exit(1)

    sections_all = build_sections(uncovered)
    path_filter = PathFilter(paths, exclude)
    sections = path_filter.filter(sections_all)

    try:
        actual_format = Format.from_str(format_)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--format") from e
    if actual_format is Format.AUTO:
        actual_format = Format.HUMAN if is_tty else Format.JSON

    if verbose:
        logger.info("input paths: %d", len(list(paths)))
        logger.info("uncovered files: %d", len(sections))
        logger.info(
            "uncovered regions: %d",
            sum(len(sec.ranges) for sec in sections),
        )
        logger.info("output format: %s", actual_format.value)
        logger.info("destination: %s", output or "stdout")

    if list_files:
        files = sorted({sec.file.as_posix() for sec in sections})
        output_text = "\n".join(files)
    elif summary_only:
        files = sorted({sec.file.as_posix() for sec in sections})
        output_text = json.dumps(files, indent=2) if actual_format is Format.JSON else "\n".join(files)
    else:
        formatter = get_formatter(actual_format)
        meta = OutputMeta(
            context_lines=context_lines,
            with_code=with_code,
            coverage_xml=resolved_xml,
            color=use_color,
        )
        output_text = formatter(sections, meta)

    if not sections and not list_files:
        msg = "No uncovered lines found (0 files matched input paths)"
        if output and output != Path("-"):
            output.write_text(msg, encoding="utf-8")
        else:
            click.echo(msg)
        return

    total_files = len(sections)
    total_regions = sum(len(sec.ranges) for sec in sections)
    total_lines = sum(end - start + 1 for sec in sections for start, end in sec.ranges)

    if stats or (actual_format is Format.HUMAN and is_tty and not list_files):
        footer = (
            f"{total_files} files with uncovered lines, {total_regions} uncovered regions, "
            f"{total_lines} total lines"
        )
        output_text = f"{output_text}\n{footer}" if output_text else footer

    if output and output != Path("-"):
        output.write_text(output_text, encoding="utf-8")
    else:
        use_pager = False
        if pager:
            use_pager = True
        elif no_pager:
            use_pager = False
        else:
            use_pager = is_tty and actual_format is Format.HUMAN
        if use_pager:
            click.echo_via_pager(output_text)
        else:
            click.echo(output_text)


if __name__ == "__main__":
    main()
