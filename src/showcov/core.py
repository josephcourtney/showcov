"""
Prints out all uncovered lines (grouped into contiguous sections) from a coverage XML report.

If no XML filename is given as a command-line argument, the script will try to read it from
a configuration file (pyproject.toml, .coveragerc, or setup.cfg).
"""

import logging
import tomllib
from argparse import Namespace
from configparser import ConfigParser
from configparser import Error as ConfigError
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from defusedxml import ElementTree

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element  # noqa: S405


# Constants
CONSECUTIVE_STEP = 1

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


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


def determine_xml_file(xml_file: Namespace | None = None) -> Path:
    """Determine the coverage XML file path from arguments or config.

    Accepts either a Namespace with attribute `xml_file` or a raw path string/None.
    """
    # Normalize input: allow passing argparse.Namespace or raw string/None.
    if hasattr(xml_file, "xml_file"):
        xml_file = xml_file.xml_file

    if xml_file:
        return Path(xml_file)

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


def gather_uncovered_lines(root: "Element") -> dict[Path, list[int]]:
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
