import argparse
import json
import logging
import sys
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, cast

from colorama import Fore, Style
from colorama import init as colorama_init
from defusedxml import ElementTree
from jsonschema import validate

from . import __version__
from .core import (
    CoverageXMLNotFoundError,
    UncoveredSection,
    build_sections,
    determine_xml_file,
    gather_uncovered_lines,
    parse_large_xml,
)

# Load JSON schema once
SCHEMA = json.loads(resources.files("showcov.data").joinpath("schema.json").read_text(encoding="utf-8"))

# Initialize colorama
colorama_init(autoreset=True)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element  # noqa: S405

# ANSI color codes (cross-platform)
RESET = Style.RESET_ALL
BOLD = Style.BRIGHT
YELLOW = Fore.YELLOW
CYAN = Fore.CYAN
MAGENTA = Fore.MAGENTA
GREEN = Fore.GREEN
RED = Fore.RED

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def disable_colors() -> None:
    """Disable ANSI color codes."""
    global RESET, BOLD, YELLOW, CYAN, MAGENTA, GREEN, RED  # noqa: PLW0603
    RESET = BOLD = YELLOW = CYAN = MAGENTA = GREEN = RED = ""


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
        help="Include source code lines in JSON output",
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


def print_uncovered_sections(sections: list[UncoveredSection], *, context_lines: int) -> None:
    """Print uncovered sections from files."""
    root = Path.cwd().resolve()
    for section in sections:
        try:
            rel = section.file.resolve().relative_to(root)
        except ValueError:
            rel = section.file.resolve()
        print(f"\n{BOLD}{YELLOW}Uncovered sections in {rel.as_posix()}:{RESET}")

        try:
            with section.file.open(encoding="utf-8") as f:
                file_lines = [ln.rstrip("\n") for ln in f.readlines()]
        except OSError:
            logger.exception("Could not open %s", section.file)
            for start, end in section.ranges:
                text = (
                    f"  {CYAN}Lines {start}-{end}{RESET}" if start != end else f"  {CYAN}Line {start}{RESET}"
                )
                print(text)
            continue

        for start, end in section.ranges:
            header = (
                f"  {BOLD}{CYAN}Lines {start}-{end}:{RESET}"
                if start != end
                else f"  {BOLD}{CYAN}Line {start}:{RESET}"
            )
            print(header)
            start_idx = max(1, start - context_lines)
            end_idx = min(len(file_lines), end + context_lines)
            for ln in range(start_idx, end_idx + 1):
                content = file_lines[ln - 1] if 1 <= ln <= len(file_lines) else "<line not found>"
                if start <= ln <= end:
                    print(f"    {MAGENTA}{ln:4d}{RESET}: {content}")
                else:
                    print(f"    {ln:4d}: {content}")
            print()


def print_json_output(sections: list[UncoveredSection], *, with_code: bool, context_lines: int) -> None:
    """Print uncovered sections in JSON format."""
    data: dict[str, object] = {
        "version": __version__,
        "files": [sec.to_dict(with_code=with_code, context_lines=context_lines) for sec in sections],
    }

    validate(data, SCHEMA)
    print(json.dumps(data, indent=2, sort_keys=True))


def main() -> None:
    """Entry point for the script."""
    args = parse_args()
    if args.no_color or args.format == "json":
        disable_colors()
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

    if not sections:
        if args.format == "json":
            print_json_output([], with_code=args.with_code, context_lines=args.context_lines)
        else:
            print(f"{GREEN}{BOLD}No uncovered lines found!{RESET}")
        return

    if args.format == "json":
        print_json_output(sections, with_code=args.with_code, context_lines=args.context_lines)
    else:
        print_uncovered_sections(sections, context_lines=args.context_lines)


if __name__ == "__main__":
    main()
