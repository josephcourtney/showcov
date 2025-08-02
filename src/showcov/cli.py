import argparse
import sys
from typing import TYPE_CHECKING, cast

from defusedxml import ElementTree

from showcov import logger
from showcov.core import (
    CoverageXMLNotFoundError,
    build_sections,
    determine_xml_file,
    gather_uncovered_lines,
    parse_large_xml,
)
from showcov.output import get_formatter

if TYPE_CHECKING:
    from pathlib import Path
    from xml.etree.ElementTree import Element  # noqa: S405


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Show uncovered lines from a coverage XML report.")
    parser.add_argument("xml_file", nargs="?", help="Path to coverage XML file")
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in output",
    )
    parser.add_argument(
        "--with-code",
        action="store_true",
        help="Embed raw source lines for uncovered ranges in JSON output",
    )
    parser.add_argument(
        "--context-lines",
        type=int,
        default=0,
        help="Number of context lines to include around uncovered sections",
    )
    parser.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="Output format",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the script."""
    args = parse_args()
    try:
        xml_file: Path = determine_xml_file(args.xml_file)
    except CoverageXMLNotFoundError:
        sys.exit(1)

    try:
        root = parse_large_xml(xml_file)
        if root is None:
            logger.error("Failed to parse coverage XML file: %s", xml_file)
            sys.exit(1)
    except ElementTree.ParseError:
        logger.exception("Error parsing XML file %s", xml_file)
        sys.exit(1)
    except OSError:
        logger.exception("Error opening XML file %s", xml_file)
        sys.exit(1)

    uncovered = gather_uncovered_lines(cast("Element", root))
    sections = build_sections(uncovered)

    formatter = get_formatter(args.format)
    output = formatter(
        sections,
        context_lines=args.context_lines,
        with_code=args.with_code,
        coverage_xml=xml_file,
        color=not args.no_color,
    )
    print(output)


if __name__ == "__main__":
    main()
