from __future__ import annotations

import logging
import sys
from fnmatch import fnmatch
from pathlib import Path

import click
from colorama import init as colorama_init
from defusedxml import ElementTree

from showcov import logger
from showcov.config import LOG_FORMAT
from showcov.core import (
    CoverageXMLNotFoundError,
    UncoveredSection,
    build_sections,
    determine_xml_file,
    gather_uncovered_lines_from_xml,
)
from showcov.output import get_formatter


def _expand_paths(patterns: tuple[str, ...]) -> list[Path]:
    """Expand files, directories, and globs into concrete paths."""
    expanded: set[Path] = set()
    for pat in patterns:
        try:
            matches = list(Path().glob(pat))
        except NotImplementedError:
            matches = []
        if matches:
            expanded.update(p.resolve() for p in matches)
        else:
            expanded.add(Path(pat).resolve())
    return sorted(expanded)


def _filter_sections(
    sections: list[UncoveredSection],
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
) -> list[UncoveredSection]:
    include_paths = _expand_paths(includes) if includes else []
    if include_paths:
        sections = [
            sec
            for sec in sections
            if any(sec.file == p or (p.is_dir() and sec.file.is_relative_to(p)) for p in include_paths)
        ]
    if excludes:
        sections = [sec for sec in sections if not any(fnmatch(sec.file.as_posix(), pat) for pat in excludes)]
    return sections


@click.command()
@click.argument("paths", nargs=-1, type=str)
@click.option("--xml-file", type=click.Path(path_type=Path), help="Path to coverage XML file")
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
    paths: tuple[str, ...],
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
    except CoverageXMLNotFoundError:
        sys.exit(1)

    try:
        uncovered = gather_uncovered_lines_from_xml(resolved_xml)
    except ElementTree.ParseError:
        logger.exception("Error parsing XML file %s", resolved_xml)
        sys.exit(1)
    except OSError:
        logger.exception("Error opening XML file %s", resolved_xml)
        sys.exit(1)

    sections = build_sections(uncovered)
    sections = _filter_sections(sections, paths, exclude)
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
