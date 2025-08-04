"""
Prints out all uncovered lines (grouped into contiguous sections) from a coverage XML report.

If no XML filename is given as a command-line argument, the script will try to read it from
a configuration file (pyproject.toml, .coveragerc, or setup.cfg).
"""

from __future__ import annotations

import operator
import tomllib
import xml.etree.ElementTree as ET  # noqa: S405
from configparser import ConfigParser
from configparser import Error as ConfigError
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from defusedxml import ElementTree
from more_itertools import consecutive_groups

from showcov import logger
from showcov.core.files import detect_line_tag, normalize_path, read_file_lines

if TYPE_CHECKING:
    from types import SimpleNamespace
    from xml.etree.ElementTree import Element  # noqa: S405


class CoverageXMLNotFoundError(Exception):
    """Coverage XML file not found."""


@dataclass(slots=True)
class UncoveredSection:
    """Structured representation of uncovered code for a single file.

    Parameters
    ----------
    file:
        Path to the source file.
    ranges:
        List of ``(start, end)`` tuples representing uncovered line ranges.
    """

    file: Path
    ranges: list[tuple[int, int]]

    def to_dict(
        self,
        *,
        with_code: bool = False,
        context_lines: int = 0,
        base: Path | None = None,
    ) -> dict[str, object]:
        """Convert the section into a JSON-serialisable dictionary.

        Parameters
        ----------
        with_code:
            Include raw source lines within each uncovered range. When
            ``context_lines`` is greater than zero, the returned lines will
            also include that many lines of surrounding context.
        context_lines:
            Number of context lines to include before and after each uncovered
            range when ``with_code`` is ``True``.
        """
        if context_lines < 0:
            msg = "context_lines must be non-negative"
            raise ValueError(msg)

        file_str = normalize_path(self.file, base=base).as_posix()

        uncovered_entries: list[dict[str, object]] = []

        file_lines: list[str] = read_file_lines(self.file) if with_code else []

        for start, end in self.ranges:
            entry: dict[str, object] = {"start": start, "end": end}
            if with_code and file_lines:
                start_idx = max(1, start - context_lines)
                end_idx = min(len(file_lines), end + context_lines)
                source = []
                for i in range(start_idx, end_idx + 1):
                    code = file_lines[i - 1] if 1 <= i <= len(file_lines) else "<line not found>"
                    tag = detect_line_tag(file_lines, i - 1) if 1 <= i <= len(file_lines) else None
                    line_entry: dict[str, object] = {"line": i, "code": code}
                    if tag:
                        line_entry["tag"] = tag
                    source.append(line_entry)
                entry["source"] = source
            uncovered_entries.append(entry)

        return {"file": file_str, "uncovered": uncovered_entries}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> UncoveredSection:
        """Create an :class:`UncoveredSection` from a dictionary."""
        file = Path(str(data["file"]))
        items = cast("list[dict[str, object]]", data.get("uncovered", []))
        ranges = [(int(item["start"]), int(item["end"])) for item in items]
        return cls(file.resolve(), ranges)


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


def determine_xml_file(xml_file: SimpleNamespace | str | None = None) -> Path:
    """Determine the coverage XML file path from arguments or config.

    Accepts either a SimpleNamespace with attribute `xml_file`, a raw path string, or ``None``.
    """
    # Normalize input: allow passing types.SimpleNamespace or raw string/None.
    if hasattr(xml_file, "xml_file"):
        xml_file = cast("str | None", xml_file.xml_file)

    if xml_file:
        path = Path(xml_file).resolve()
        if not path.is_file():
            msg = f"Coverage XML file not found: {path}"
            raise CoverageXMLNotFoundError(msg)
        return path

    # avoid circular import
    from showcov.core import get_config_xml_file as _get_config_xml_file  # noqa: PLC0415

    config_xml = _get_config_xml_file()
    if config_xml:
        path = Path(config_xml).resolve()
        if not path.is_file():
            msg = f"Coverage XML file not found: {path}"
            raise CoverageXMLNotFoundError(msg)
        return path

    msg = "No coverage XML file specified or found in configuration."
    raise CoverageXMLNotFoundError(msg)


def group_consecutive_numbers(numbers: list[int]) -> list[list[int]]:
    """Group consecutive numbers into sublists."""
    return [list(grp) for grp in consecutive_groups(numbers)]


def merge_blank_gap_groups(groups: list[list[int]], file_lines: list[str]) -> list[list[int]]:
    """Merge adjacent groups if the gap between them contains only blank lines."""
    if not groups:
        return groups

    merged: list[list[int]] = [groups[0]]
    for grp in groups[1:]:
        last_grp = merged[-1]
        gap_start = last_grp[-1] + 1
        gap_end = grp[0] - 1

        if gap_start <= gap_end and all(
            i - 1 < len(file_lines) and not file_lines[i - 1].strip() for i in range(gap_start, gap_end + 1)
        ):
            merged[-1].extend(grp)
        else:
            merged.append(grp)

    return merged


def gather_uncovered_lines(root: Element) -> dict[Path, list[int]]:
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
                lines = uncovered.setdefault(resolved_path, [])
                if line_no not in lines:
                    lines.append(line_no)

    return uncovered


def build_sections(uncovered: dict[Path, list[int]]) -> list[UncoveredSection]:
    """Convert mapping of uncovered line numbers to structured sections."""
    sections: list[UncoveredSection] = []
    for filename in sorted(uncovered.keys(), key=lambda p: p.as_posix()):
        lines_sorted = sorted(uncovered[filename])
        groups = group_consecutive_numbers(lines_sorted)
        file_lines = read_file_lines(filename)
        if file_lines:
            groups = merge_blank_gap_groups(groups, file_lines)
        ranges = [(grp[0], grp[-1]) for grp in sorted(groups, key=operator.itemgetter(0))]
        sections.append(UncoveredSection(filename, ranges))
    return sections


def _parse_coverage_xml(xml_file: Path) -> ET.ElementTree[ET.Element]:
    return ET.parse(xml_file)  # noqa: S314


def _get_coverage_root(tree: ET.ElementTree[ET.Element]) -> ET.Element:
    root = tree.getroot()
    if root is None or root.tag != "coverage":
        msg = f"Invalid root element: expected <coverage>, got <{getattr(root, 'tag', None)}>"
        raise ValueError(msg)
    return root


def _extract_uncovered_by_file(root: ET.Element) -> dict[Path, list[int]]:
    uncovered: dict[Path, list[int]] = {}

    for class_elt in root.findall(".//class"):
        filename = class_elt.get("filename")
        if not filename:
            continue

        path = Path(filename)
        lines = [
            int(line.get("number")) for line in class_elt.findall("lines/line") if line.get("hits") == "0"
        ]

        if lines:
            uncovered.setdefault(path, []).extend(lines)

    return uncovered


def gather_uncovered_lines_from_xml(xml_file: Path) -> dict[Path, list[int]]:
    """Extract uncovered line numbers for each source file from coverage XML."""
    try:
        tree = _parse_coverage_xml(xml_file)
        root = _get_coverage_root(tree)
        return _extract_uncovered_by_file(root)
    except ET.ParseError as exc:
        msg = f"{xml_file}: failed to parse coverage XML: {exc}"
        raise ET.ParseError(msg) from exc
    except OSError as exc:
        msg = f"{xml_file}: could not read file: {exc}"
        raise OSError(msg) from exc


def diff_uncovered_lines(
    baseline_xml: Path, current_xml: Path
) -> tuple[list[UncoveredSection], list[UncoveredSection]]:
    """Return new and resolved uncovered sections between two coverage reports.

    Parameters
    ----------
    baseline_xml:
        Path to the baseline coverage XML report.
    current_xml:
        Path to the current coverage XML report.

    Returns
    -------
    tuple[list[UncoveredSection], list[UncoveredSection]]
        Two lists of :class:`UncoveredSection` objects.  The first contains
        sections that are newly uncovered in ``current_xml`` compared to the
        baseline.  The second contains sections that were uncovered in the
        baseline but have since been resolved.
    """
    baseline = gather_uncovered_lines_from_xml(baseline_xml)
    current = gather_uncovered_lines_from_xml(current_xml)

    new_uncovered: dict[Path, list[int]] = {}
    resolved: dict[Path, list[int]] = {}

    for file, lines in current.items():
        prev = set(baseline.get(file, []))
        added = sorted(set(lines) - prev)
        if added:
            new_uncovered[file] = added

    for file, lines in baseline.items():
        now = set(current.get(file, []))
        removed = sorted(set(lines) - now)
        if removed:
            resolved[file] = removed

    return build_sections(new_uncovered), build_sections(resolved)


def parse_large_xml(file_path: Path) -> Element | None:
    """Efficiently parse large XML files with iterparse."""
    context = ElementTree.iterparse(file_path, events=("start", "end"))
    for event, elem in context:
        if event == "end" and elem.tag == "coverage":
            return elem  # Return root element early to save memory
    return None
