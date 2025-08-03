from __future__ import annotations

import logging
import sys
from pathlib import Path

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
from showcov.output import get_formatter
from showcov.path_filter import PathFilter


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path, exists=True))
@click.option("--xml-file", type=click.Path(path_type=Path, exists=True), help="Path to coverage XML file")
@click.option("--no-color", is_flag=True, help="Disable ANSI color codes in output")
@click.option("--with-code", is_flag=True, help="Embed raw source lines for uncovered ranges in JSON output")
@click.option(
    "--context-lines", type=click.IntRange(min=0), default=0, help="Number of context lines to include"
)
@click.option(
    "--format",
    "format_",
    type=click.Choice(["human", "json", "markdown", "sarif"]),
    default="human",
    help="Output format",
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude from output")
@click.option("--output", type=click.Path(path_type=Path), help="Write output to FILE instead of stdout")
def main(
    paths: tuple[Path, ...],
    xml_file: Path | None,
    *,
    no_color: bool = False,
    with_code: bool = False,
    context_lines: int = 0,
    format_: str = "human",
    exclude: tuple[str, ...] = (),
    output: Path | None = None,
) -> None:
    """Show uncovered lines from a coverage XML report."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    colorama_init(autoreset=True)
    try:
        resolved_xml = determine_xml_file(str(xml_file) if xml_file else None)
        uncovered = gather_uncovered_lines_from_xml(resolved_xml)
    except (CoverageXMLNotFoundError, ElementTree.ParseError, OSError):
        logger.exception("failed to read coverage XML")
        sys.exit(1)

    sections = build_sections(uncovered)
    path_filter = PathFilter(paths, exclude)
    sections = path_filter.filter(sections)
    formatter = get_formatter(format_)
    output_text = formatter(
        sections,
        context_lines=context_lines,
        with_code=with_code,
        coverage_xml=resolved_xml,
        color=not no_color,
    )
    if output:
        output.write_text(output_text, encoding="utf-8")
    else:
        click.echo(output_text)


if __name__ == "__main__":
    main()
