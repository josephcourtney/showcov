"""
Prints out all uncovered lines (grouped into contiguous sections) from a coverage XML report.

If no XML filename is given as a command-line argument, the script will try to read it from
a configuration file (pyproject.toml, .coveragerc, or setup.cfg).
"""

import argparse
import logging
import operator
import sys
import tomllib
from configparser import ConfigParser
from configparser import Error as ConfigError
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast

from colorama import Fore, Style
from colorama import init as colorama_init
from defusedxml import ElementTree

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


class CoverageXMLNotFoundError(Exception):
    """Coverage XML file not found."""


def _get_xml_from_config(config_path: Path, section: str, option: str) -> str | None:
    """Extract an XML path from the configuration file."""
    config = ConfigParser()
    try:
        config.read(config_path)
    except (OSError, ConfigError, ValueError) as e:
        logger.warning("Failed to parse %s: %s", config_path, e)
        return None

    return (
        config.get(section, option)
        if config.has_section(section) and config.has_option(section, option)
        else None
    )


def _get_xml_from_pyproject(pyproject: Path) -> str | None:
    """Extract the XML coverage file path from pyproject.toml."""
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning("Failed to parse %s: %s", pyproject, e)
        return None

    tool = data.get("tool", {})
    coverage_cfg = tool.get("coverage", {})
    return coverage_cfg.get("xml_report") or coverage_cfg.get("xml", {}).get("output")


def get_config_xml_file() -> str | None:
    """Look for an XML filename in configuration files."""
    config_files = [
        (Path("./pyproject.toml").resolve(), _get_xml_from_pyproject),
        (Path("./.coveragerc").resolve(), lambda p: _get_xml_from_config(p, "xml", "output")),
        (Path("./setup.cfg").resolve(), lambda p: _get_xml_from_config(p, "coverage:xml", "output")),
    ]

    for path, extractor in config_files:
        if path.exists():
            xml_file = extractor(path)
            if xml_file:
                logger.info("Using coverage XML file from config: %s", xml_file)
                return xml_file

    return None


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Show uncovered lines from a coverage XML report.")
    parser.add_argument("xml_file", nargs="?", help="Path to coverage XML file")
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in output",
    )
    return parser.parse_args()


def determine_xml_file(args: argparse.Namespace | None = None) -> Path:
    """Determine the coverage XML file path from arguments or config."""
    if args is None:
        args = parse_args()
    if args.xml_file:
        return Path(args.xml_file)

    config_xml = get_config_xml_file()
    if config_xml:
        return Path(config_xml)

    msg = "No coverage XML file specified or found in configuration."
    raise CoverageXMLNotFoundError(msg)


def group_consecutive_numbers(numbers: list[int]) -> list[list[int]]:
    """Group consecutive numbers into sublists."""
    groups: list[list[int]] = []
    group: list[int] = []

    for num in numbers:
        if group and num != group[-1] + CONSECUTIVE_STEP:
            groups.append(group)
            group = []
        group.append(num)

    if group:
        groups.append(group)
    return groups


def merge_blank_gap_groups(groups: list[list[int]], file_lines: list[str]) -> list[list[int]]:
    """Merge adjacent groups if the gap between them contains only blank lines."""
    if not groups:
        return groups

    merged: list[list[int]] = [groups[0]]
    for grp in groups[1:]:
        last_grp = merged[-1]
        gap_start = last_grp[-1] + 1
        gap_end = grp[0] - 1

        if gap_start <= gap_end and all(not file_lines[i - 1].strip() for i in range(gap_start, gap_end + 1)):
            merged[-1].extend(grp)
        else:
            merged.append(grp)

    return merged


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


def _gather_uncovered_lines(root: "Element") -> dict[Path, list[int]]:
    """Gather uncovered lines per file from the parsed XML tree."""
    uncovered: dict[Path, list[int]] = {}

    # Get all source roots from the XML
    source_elements = root.findall(".//sources/source")
    source_roots = [Path(src.text).resolve() for src in source_elements if src.text]

    for cls in root.findall(".//class"):
        filename_str = cls.get("filename")
        if not filename_str:
            continue

        # Try resolving with the source root
        filename = Path(filename_str)
        resolved_path = next(
            (src / filename for src in source_roots if (src / filename).exists()),
            filename,  # fallback to relative path if none match
        ).resolve()

        for line in cls.findall("lines/line"):
            try:
                hits = int(line.get("hits", "0"))
                line_no = int(line.get("number", "0"))
            except (ValueError, TypeError):
                continue

            if hits == 0:
                uncovered.setdefault(resolved_path, []).append(line_no)

    return uncovered


def parse_large_xml(file_path: Path) -> Optional["Element"]:
    """Efficiently parse large XML files with iterparse."""
    context = ElementTree.iterparse(file_path, events=("start", "end"))
    for event, elem in context:
        if event == "end" and elem.tag == "coverage":
            return elem  # Return root element early to save memory
    return None


def main() -> None:
    """Entry point for the script."""
    args = parse_args()
    if args.no_color:
        disable_colors()
    try:
        xml_file: Path = determine_xml_file(args)
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

    uncovered = _gather_uncovered_lines(cast("Element", root))

    if not uncovered:
        print(f"{GREEN}{BOLD}No uncovered lines found!{RESET}")
        return

    print_uncovered_sections(uncovered)


if __name__ == "__main__":
    main()
