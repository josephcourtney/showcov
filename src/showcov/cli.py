import argparse
import json
import logging
import operator
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from colorama import Fore, Style
from colorama import init as colorama_init
from defusedxml import ElementTree

from . import __version__
from .core import (
    CoverageXMLNotFoundError,
    determine_xml_file,
    gather_uncovered_lines,
    group_consecutive_numbers,
    merge_blank_gap_groups,
    parse_large_xml,
)

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

# Constants
CONSECUTIVE_STEP = 1

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
        "--format",
        choices=("human", "json"),
        default="human",
        help="Output format",
    )
    return parser.parse_args()


def print_uncovered_sections(uncovered: dict[Path, list[int]]) -> None:
    """Print uncovered sections from files."""
    for filename in sorted(uncovered.keys(), key=lambda p: p.as_posix()):
        lines_sorted = sorted(uncovered[filename])
        groups = group_consecutive_numbers(lines_sorted)
        groups = sorted(groups, key=operator.itemgetter(0))
        print(f"\n{BOLD}{YELLOW}Uncovered sections in {filename.as_posix()}:{RESET}")

        try:
            with filename.open(encoding="utf-8") as f:
                file_lines = f.readlines()
            groups = merge_blank_gap_groups(groups, file_lines)
        except OSError:
            logger.exception("Could not open %s", filename)
            for grp in groups:
                print(
                    f"  {CYAN}Lines {grp[0]}-{grp[-1]}{RESET}"
                    if len(grp) > 1
                    else f"  {CYAN}Line {grp[0]}{RESET}"
                )
            continue

        for grp in groups:
            header = (
                f"  {BOLD}{CYAN}Lines {grp[0]}-{grp[-1]}:{RESET}"
                if len(grp) > 1
                else f"  {BOLD}{CYAN}Line {grp[0]}:{RESET}"
            )
            print(header)
            for ln in grp:
                content = (
                    file_lines[ln - 1].rstrip("\n") if 1 <= ln <= len(file_lines) else "<line not found>"
                )
                print(f"    {MAGENTA}{ln:4d}{RESET}: {content}")
            print()


def print_json_output(uncovered: dict[Path, list[int]]) -> None:
    """Print uncovered sections in JSON format."""
    data: dict[str, object] = {"version": __version__, "files": []}
    files: list[dict[str, object]] = []
    for filename in sorted(uncovered.keys(), key=lambda p: p.resolve().as_posix()):
        normalized = filename.resolve().as_posix()
        lines_sorted = sorted(uncovered[filename])
        groups = group_consecutive_numbers(lines_sorted)
        groups = sorted(groups, key=operator.itemgetter(0))
        ranges = [{"start": grp[0], "end": grp[-1]} for grp in groups]
        files.append({"file": normalized, "uncovered": ranges})
    data["files"] = files
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

    if not uncovered:
        if args.format == "json":
            print_json_output({})
        else:
            print(f"{GREEN}{BOLD}No uncovered lines found!{RESET}")
        return

    if args.format == "json":
        print_json_output(uncovered)
    else:
        print_uncovered_sections(uncovered)


if __name__ == "__main__":
    main()
